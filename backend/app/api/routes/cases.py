"""Case routes — list, fetch, update status."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.security import get_current_user, require_manager_or_admin, normalize_role
from app.db.session import get_db
from app.db.repositories.case_repo import CaseRepository
from app.db.repositories.transaction_repo import TransactionRepository
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.biometric_repo import BiometricChallengeRepository
from app.schemas.biometric import BiometricChallengeResponse
from app.services.hardware.biometric_workflow import biometric_workflow, utcnow
from app.services.hardware.fingerprint import HardwareBusyError, HardwareUnavailableError
from app.services.str_report import render_str, str_filename

router = APIRouter()


def _actor(user: dict) -> dict:
    """Compact actor identity stored in the immutable audit record."""
    return {
        "id": str(user.get("_id", "unknown")),
        "name": user.get("name", user.get("email", "Unknown")),
        "role": normalize_role(user.get("role")),
    }


def _get_recommendation_action(recommendation):
    """Return Agent 6's operational action while supporting legacy cases."""
    if not isinstance(recommendation, dict):
        return recommendation
    return (
        recommendation.get("case_action")
        or recommendation.get("decision")
        or recommendation.get("action")
    )


async def _audit(
    db,
    case_id: str,
    action: str,
    user: Optional[dict] = None,
    metadata: Optional[dict] = None,
):
    await AuditRepository(db).record(
        case_id=case_id,
        action=action,
        performed_by=_actor(user) if user else None,
        metadata=metadata or {},
    )


async def _authorised_case_for_biometric_download(db, case_id: str, current_user: dict) -> dict:
    """Apply the primary application's existing case visibility rules."""
    case = await CaseRepository(db).get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if normalize_role(current_user.get("role")) == "officer" and case.get("assigned_officer_id") != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="This case is not assigned to you")
    return case



class StatusUpdate(BaseModel):
    status: str
    analyst_notes: str = ""


class OverrideRequest(BaseModel):
    decision: str
    reason: str


class MoreEvidenceRequest(BaseModel):
    request: str


class AssignRequest(BaseModel):
    officer_id: str

class FalsePositiveRequest(BaseModel):
    reason: str
    notes: str = ""


@router.get("/")
async def list_cases(
    status:   Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None, description="Manager/admin only: filter by officer id"),
    limit:    int            = Query(50, le=200),
    skip:     int            = Query(0),
    current_user=Depends(get_current_user),
):
    """
    PHASE 8 — role-based visibility:
      - officer (incl. legacy 'analyst' role): only cases assigned to them
      - manager / admin: all cases; managers/admins may filter with `assigned_to`
    """
    db   = await get_db()
    repo = CaseRepository(db)

    role = normalize_role(current_user.get("role"))
    if role == "officer":
        assigned_officer_id = str(current_user.get("_id"))
    else:
        assigned_officer_id = assigned_to  # None = all cases

    return await repo.list_all(
        status=status, priority=priority,
        assigned_officer_id=assigned_officer_id,
        limit=limit, skip=skip,
    )


@router.get("/summary")
async def cases_summary(current_user=Depends(get_current_user)):
    db   = await get_db()
    repo = CaseRepository(db)
    by_priority = await repo.count_by_priority()
    by_status   = await repo.count_by_status()
    return {"by_priority": by_priority, "by_status": by_status}


@router.get("/false-positive-stats")
async def false_positive_stats(current_user=Depends(get_current_user)):
    """Return aggregate false-positive feedback metrics for monitoring."""
    db = await get_db()
    return await CaseRepository(db).false_positive_stats()


@router.post("/{case_id}/false-positive")
async def mark_false_positive(
    case_id: str,
    body: FalsePositiveRequest,
    current_user=Depends(get_current_user),
):
    """Record authorised compliance feedback that a case was a false positive."""
    role = normalize_role(current_user.get("role"))
    if role not in ("officer", "manager", "admin"):
        raise HTTPException(status_code=403, detail="Compliance officer access required")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="False-positive reason is required")

    db = await get_db()
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Preserve officer visibility rules: an officer can only submit feedback
    # on a case assigned to them. Managers/admins may submit for any case.
    if role == "officer" and case.get("assigned_officer_id") != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="This case is not assigned to you")

    feedback = {
        "reason": body.reason.strip(),
        "notes": body.notes.strip(),
        "reviewer_id": current_user.get("_id"),
        "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    updated = await repo.record_false_positive(case_id, feedback)
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")

    await _audit(
        db,
        case_id,
        "false_positive_recorded",
        current_user,
        {"reason": feedback["reason"], "notes": feedback["notes"]},
    )

    return {"case_id": case_id, "false_positive": True, "feedback": feedback}


@router.get("/{case_id}/audit")
async def get_case_audit(
    case_id: str,
    limit: int = Query(100, le=200),
    skip: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
):
    """Read-only audit history for a case."""
    db = await get_db()
    case = await CaseRepository(db).get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    role = normalize_role(current_user.get("role"))
    if role == "officer" and case.get("assigned_officer_id") != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="This case is not assigned to you")

    return await AuditRepository(db).list_for_case(
        case_id, limit=limit, skip=skip
    )


@router.get("/{case_id}")
async def get_case(case_id: str, current_user=Depends(get_current_user)):
    db   = await get_db()
    repo = CaseRepository(db)
    doc  = await repo.get_by_id(case_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Case not found")

    # PHASE 8 — an officer may only open a case assigned to them.
    # Managers/admins can open anything.
    role = normalize_role(current_user.get("role"))
    if role == "officer":
        if doc.get("assigned_officer_id") != str(current_user.get("_id")):
            raise HTTPException(status_code=403, detail="This case is not assigned to you")

    return doc


@router.post("/{case_id}/assign")
async def assign_case(
    case_id: str,
    body: AssignRequest,
    current_user=Depends(require_manager_or_admin),
):
    """Manager/admin assigns (or reassigns) a case to an officer."""
    db = await get_db()
    case_repo = CaseRepository(db)
    user_repo = UserRepository(db)

    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    officer = await user_repo.get_by_id(body.officer_id)
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    if normalize_role(officer.get("role")) not in ("officer",):
        raise HTTPException(status_code=400, detail="Cases can only be assigned to users with the officer role")

    assigned_by_id = str(current_user.get("_id"))
    assigned_by_name = current_user.get("name", current_user.get("email", "Unknown"))

    updated = await case_repo.assign_officer(
        case_id,
        officer_id=str(officer["_id"]),
        officer_name=officer.get("name") or officer.get("email"),
        assigned_by_id=assigned_by_id,
        assigned_by_name=assigned_by_name,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")

    await _audit(
        db,
        case_id,
        "case_assigned",
        current_user,
        {
            "assigned_officer_id": str(officer["_id"]),
            "assigned_officer_name": officer.get("name") or officer.get("email"),
        },
    )

    return {
        "case_id": case_id,
        "assigned_officer_id": str(officer["_id"]),
        "assigned_officer_name": officer.get("name") or officer.get("email"),
    }



@router.post("/{case_id}/review/accept")
async def accept_recommendation(
    case_id: str,
    current_user=Depends(get_current_user),
):
    """Accept Agent 6's recommendation as the human final decision."""
    db = await get_db()
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    recommendation = case.get("recommendation") or case.get("investigation", {}).get("recommendation", {})
    action = _get_recommendation_action(recommendation)
    if not action:
        raise HTTPException(status_code=400, detail="No AI recommendation exists for this case")

    now = datetime.now(timezone.utc).isoformat()
    review = {
        "status": "accepted",
        "action": "accept",
        "reviewer_id": current_user.get("_id"),
        "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
        "previous_recommendation": action,
        "final_decision": action,
        "reason": "AI recommendation accepted by compliance officer.",
        "timestamp": now,
        "biometric_verified": False,
    }
    updated = await repo.record_human_review(case_id, review)
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")
    await _audit(
        db,
        case_id,
        "human_review_accepted",
        current_user,
        {"previous_recommendation": action, "final_decision": action},
    )
    return {"case_id": case_id, "human_review": review}


@router.post("/{case_id}/review/override")
async def override_recommendation(
    case_id: str,
    body: OverrideRequest,
    current_user=Depends(get_current_user),
):
    """Override Agent 6's recommendation. Biometric verification is reserved for hardware integration."""
    valid_decisions = {"BLOCK", "MONITOR", "ESCALATE", "FILE_STR", "REQUEST_INFO", "CLOSE"}
    if body.decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"Decision must be one of {sorted(valid_decisions)}")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="Override reason is required")

    db = await get_db()
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    recommendation = case.get("recommendation") or case.get("investigation", {}).get("recommendation", {})
    previous = _get_recommendation_action(recommendation)
    if not previous:
        raise HTTPException(status_code=400, detail="No AI recommendation exists for this case")

    review = {
        "status": "overridden",
        "action": "override",
        "reviewer_id": current_user.get("_id"),
        "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
        "previous_recommendation": previous,
        "final_decision": body.decision,
        "reason": body.reason.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "biometric_verified": False,
    }
    updated = await repo.record_human_review(case_id, review)
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")
    await _audit(
        db,
        case_id,
        "human_review_overridden",
        current_user,
        {
            "previous_recommendation": previous,
            "final_decision": body.decision,
            "reason": body.reason.strip(),
        },
    )
    return {"case_id": case_id, "human_review": review}


@router.post("/{case_id}/review/more-evidence")
async def request_more_evidence(
    case_id: str,
    body: MoreEvidenceRequest,
    current_user=Depends(get_current_user),
):
    """Ask for additional evidence and return the case to investigation."""
    if not body.request.strip():
        raise HTTPException(status_code=400, detail="Evidence request is required")

    db = await get_db()
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    recommendation = case.get("recommendation") or case.get("investigation", {}).get("recommendation", {})
    previous = _get_recommendation_action(recommendation)
    review = {
        "status": "more_evidence_requested",
        "action": "request_more_evidence",
        "reviewer_id": current_user.get("_id"),
        "reviewer_name": current_user.get("name", current_user.get("email", "Unknown")),
        "previous_recommendation": previous,
        "final_decision": None,
        "reason": body.request.strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "biometric_verified": False,
    }
    updated = await repo.record_human_review(case_id, review)
    if not updated:
        raise HTTPException(status_code=404, detail="Case not found")

    await repo.update_status(case_id, "investigating", body.request.strip())

    # Actually reopen: reset the underlying transactions to unanalyzed so
    # the background worker re-runs the Adaptive Planner / 6-agent pipeline
    # on them. Previously this endpoint only relabelled case.status without
    # re-triggering any investigation — the case would sit as "investigating"
    # forever with no new agent run behind it.
    transactions_reopened = 0
    txn_ids = case.get("transaction_ids", [])
    if txn_ids:
        txn_repo = TransactionRepository(db)
        transactions_reopened = await txn_repo.reset_analyzed(txn_ids)

    await _audit(
        db,
        case_id,
        "more_evidence_requested",
        current_user,
        {
            "previous_recommendation": previous,
            "request": body.request.strip(),
            "transactions_reopened": transactions_reopened,
        },
    )

    return {
        "case_id": case_id,
        "human_review": review,
        "status": "investigating",
        "transactions_reopened": transactions_reopened,
    }


@router.patch("/{case_id}/status")
async def update_case_status(
    case_id: str,
    body: StatusUpdate,
    current_user=Depends(get_current_user),
):
    valid = {"new", "investigating", "reviewed", "reviewing", "filed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")

    db   = await get_db()
    repo = CaseRepository(db)
    case = await repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    role = normalize_role(current_user.get("role"))
    if role == "officer" and case.get("assigned_officer_id") != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="This case is not assigned to you")

    ok = await repo.update_status(case_id, body.status, body.analyst_notes)
    if not ok:
        raise HTTPException(status_code=404, detail="Case not found")

    await _audit(
        db,
        case_id,
        "case_status_changed",
        current_user,
        {
            "from": case.get("status"),
            "to": body.status,
            "analyst_notes": body.analyst_notes,
        },
    )
    return {"case_id": case_id, "status": body.status, "updated": True}


@router.post("/{case_id}/str/download-challenge", response_model=BiometricChallengeResponse, status_code=202)
async def start_str_download_challenge(case_id: str, current_user=Depends(get_current_user)):
    """Start a fresh local fingerprint check for one official STR download."""
    db = await get_db()
    case = await _authorised_case_for_biometric_download(db, case_id, current_user)
    try:
        return biometric_workflow.response(await biometric_workflow.start_str_download(current_user, case, db))
    except HardwareBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HardwareUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{case_id}/str/download-challenge/{challenge_id}", response_model=BiometricChallengeResponse)
async def check_str_download_challenge(case_id: str, challenge_id: str, current_user=Depends(get_current_user)):
    db = await get_db()
    await _authorised_case_for_biometric_download(db, case_id, current_user)
    try:
        return await biometric_workflow.download_challenge_response(challenge_id, case_id, current_user, db)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{case_id}/str/download")
async def download_str(case_id: str, challenge_id: str = Query(..., min_length=1), current_user=Depends(get_current_user)):
    """Consume exactly one successful biometric authorization and return an attachment."""
    db = await get_db()
    case = await _authorised_case_for_biometric_download(db, case_id, current_user)
    consumed = await BiometricChallengeRepository(db).consume_download(
        challenge_id, str(current_user["_id"]), case_id, utcnow())
    if not consumed:
        await _audit(db, case_id, "str_download_denied", current_user, {"reason": "invalid_or_consumed_biometric_challenge"})
        raise HTTPException(status_code=403, detail="A valid, unexpired biometric download authorization is required")
    try:
        content = render_str(case)
    except ValueError as exc:
        # The authorization remains consumed: do not permit replay after a failed artifact request.
        await _audit(db, case_id, "str_download_denied", current_user, {"reason": "missing_str_narrative"})
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await _audit(db, case_id, "str_download_consumed", current_user)
    return Response(content=content, media_type="text/plain", headers={
        "Content-Disposition": f'attachment; filename="{str_filename(case_id)}"',
        "Cache-Control": "no-store",
    })
