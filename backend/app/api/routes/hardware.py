"""Local Arduino health and administrator-only enrollment routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user, require_admin
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_db
from app.schemas.biometric import EnrolmentRequest
from app.services.hardware.fingerprint import HardwareBusyError, HardwareUnavailableError, fingerprint_service

router = APIRouter()


@router.get("/status")
async def status(current_user=Depends(get_current_user)):
    return await fingerprint_service.status()


@router.post("/enroll")
async def enroll(body: EnrolmentRequest, current_user=Depends(require_admin)):
    db = await get_db()
    users = UserRepository(db)
    target = await users.get_by_id(body.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")
    existing_owner = await users.get_by_biometric_template(body.fingerprint_id)
    if existing_owner and existing_owner["_id"] != body.user_id:
        raise HTTPException(status_code=409, detail="Fingerprint ID is already assigned to another user")
    try:
        result = await fingerprint_service.enroll(body.user_id, body.fingerprint_id)
    except HardwareBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HardwareUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not result.success:
        await AuditRepository(db).record(case_id="", action="biometric_enrollment_failed",
            performed_by={"id": str(current_user["_id"]), "name": current_user.get("name", "Unknown"), "role": current_user.get("role", "admin")},
            metadata={"target_user_id": body.user_id, "result": result.status})
        return {"status": result.status, "detail": result.detail}
    if not await users.set_biometric_template(body.user_id, body.fingerprint_id):
        raise HTTPException(status_code=409, detail="Fingerprint ID could not be assigned to the target user")
    await AuditRepository(db).record(case_id="", action="biometric_enrollment_success",
        performed_by={"id": str(current_user["_id"]), "name": current_user.get("name", "Unknown"), "role": current_user.get("role", "admin")},
        metadata={"target_user_id": body.user_id})
    return {"status": "success", "detail": result.detail}
