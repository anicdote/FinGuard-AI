"""Server-authoritative biometric workflows for login and STR downloads."""

import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.biometric_repo import BiometricChallengeRepository
from app.db.repositories.user_repo import UserRepository
from app.services.hardware.fingerprint import fingerprint_service


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class BiometricWorkflowService:
    def __init__(self) -> None:
        self._background_tasks: set[asyncio.Task] = set()

    async def start_login(self, user: dict, db) -> dict:
        return await self._start_challenge(db, user, "login")

    async def start_str_download(self, user: dict, case: dict, db) -> dict:
        return await self._start_challenge(db, user, "str_download", case["id"])

    async def _audit(self, db, action: str, user: dict, case_id: str | None = None, metadata: dict | None = None) -> None:
        await AuditRepository(db).record(
            case_id=case_id or "", action=action,
            performed_by={"id": str(user.get("_id", "unknown")),
                          "name": user.get("name", user.get("email", "Unknown")),
                          "role": user.get("role", "system")}, metadata=metadata or {})

    async def _start_challenge(self, db, user: dict, purpose: str, case_id: str | None = None) -> dict:
        template_id = user.get("biometric_template_id")
        event_prefix = "biometric_login" if purpose == "login" else "str_download"
        if not isinstance(template_id, int) or template_id < 1:
            await self._audit(db, f"{event_prefix}_failed", user, case_id, {"reason": "no_registered_fingerprint"})
            from app.services.hardware.fingerprint import HardwareUnavailableError
            raise HardwareUnavailableError("No registered fingerprint is assigned to this user.")
        challenge_id = secrets.token_urlsafe(32)
        # The challenge id is an identifier, not a bearer credential.  Login
        # polling is unauthenticated, so require a second secret delivered
        # only after the password check and persist only its digest.
        challenge_token = secrets.token_urlsafe(32) if purpose == "login" else None
        repo = BiometricChallengeRepository(db)
        payload = {
            "challenge_id": challenge_id, "purpose": purpose, "user_id": user["_id"],
            "user_email": user.get("email"), "case_id": case_id, "status": "pending",
            "consumed": False, "completed_at": None,
            "expires_at": utcnow() + timedelta(seconds=settings.BIOMETRIC_CHALLENGE_TTL_SEC),
        }
        if challenge_token:
            payload["login_challenge_token_hash"] = hashlib.sha256(challenge_token.encode()).hexdigest()
        challenge = await repo.create(payload)
        if challenge_token:
            challenge["challenge_token"] = challenge_token
        try:
            await fingerprint_service.reserve(challenge_id)
        except Exception as exc:
            await repo.update(challenge_id, {"status": "hardware_error", "message": str(exc), "completed_at": utcnow()})
            await self._audit(db, f"{event_prefix}_failed", user, case_id, {"reason": "hardware_unavailable"})
            raise
        await self._audit(db, f"{event_prefix}_started", user, case_id)
        task = asyncio.create_task(self._perform_verification(challenge_id, template_id, purpose, user, case_id, db))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return challenge

    async def _perform_verification(self, challenge_id: str, template_id: int, purpose: str,
                                    user: dict, case_id: str | None, db) -> None:
        repo = BiometricChallengeRepository(db)
        prefix = "biometric_login" if purpose == "login" else "str_download"
        try:
            await repo.update(challenge_id, {"status": "finger_required", "message": "Place your registered finger on the local sensor."})

            async def progress(status: str) -> None:
                await repo.update(challenge_id, {"status": status,
                    "message": "Fingerprint is being verified." if status == "verifying" else "Place your registered finger on the local sensor."})

            result = await fingerprint_service.verify(challenge_id, template_id,
                "LOGIN" if purpose == "login" else "STR", progress_callback=progress, reserved=True)
            await repo.update(challenge_id, {"status": result.status, "message": result.detail,
                                              "completed_at": utcnow()})
            event = "str_download_authorized" if purpose == "str_download" and result.success else f"{prefix}_{'success' if result.success else 'failed'}"
            await self._audit(db, event, user, case_id, {"result": result.status})
        except Exception:
            await repo.update(challenge_id, {"status": "hardware_error", "message": "Biometric controller error.", "completed_at": utcnow()})
            await self._audit(db, f"{prefix}_failed", user, case_id, {"reason": "hardware_error"})
        finally:
            await fingerprint_service.release(challenge_id)

    async def valid_challenge(self, challenge_id: str, purpose: str, repo: BiometricChallengeRepository) -> dict:
        challenge = await repo.get(challenge_id)
        if not challenge or challenge.get("purpose") != purpose:
            raise ValueError("Biometric challenge not found.")
        expires_at = challenge.get("expires_at")
        if isinstance(expires_at, datetime):
            expires_at = ensure_utc(expires_at)
            challenge["expires_at"] = expires_at
        if isinstance(expires_at, datetime) and expires_at <= utcnow():
            if challenge.get("status") not in {"timeout", "failed", "hardware_error"}:
                await repo.update(challenge_id, {"status": "timeout", "message": "Biometric challenge expired.", "completed_at": utcnow()})
            challenge["status"] = "timeout"
            challenge["message"] = "Biometric challenge expired."
        return challenge

    def response(self, challenge: dict) -> dict:
        expires = challenge.get("expires_at")
        response = {"challenge_id": challenge["challenge_id"], "purpose": challenge["purpose"],
                "status": challenge["status"], "message": challenge.get("message") or "Fingerprint verification in progress.",
                "expires_at": ensure_utc(expires) if isinstance(expires, datetime) else expires}
        if challenge.get("challenge_token"):
            response["challenge_token"] = challenge["challenge_token"]
        return response

    async def login_challenge_response(self, challenge_id: str, challenge_token: str, db) -> dict:
        repo = BiometricChallengeRepository(db)
        challenge = await self.valid_challenge(challenge_id, "login", repo)
        supplied_hash = hashlib.sha256(challenge_token.encode()).hexdigest()
        expected_hash = challenge.get("login_challenge_token_hash")
        if not expected_hash or not hmac.compare_digest(expected_hash, supplied_hash):
            raise ValueError("Biometric challenge not found.")
        response = self.response(challenge)
        if challenge["status"] != "success":
            return response
        tokens = challenge.get("login_tokens")
        if not tokens:
            user = await UserRepository(db).get_by_id(challenge["user_id"])
            if not user:
                raise ValueError("User no longer exists.")
            data = {"sub": user["_id"], "role": user["role"], "email": user["email"]}
            stored = await repo.store_login_tokens(challenge_id, {
                "access_token": create_access_token(data), "refresh_token": create_refresh_token(data), "token_type": "bearer"}, utcnow())
            challenge = stored or await repo.get(challenge_id)
            tokens = challenge.get("login_tokens") if challenge else None
        if tokens:
            response.update(tokens)
        return response

    async def download_challenge_response(self, challenge_id: str, case_id: str, user: dict, db) -> dict:
        challenge = await self.valid_challenge(challenge_id, "str_download", BiometricChallengeRepository(db))
        if challenge.get("case_id") != case_id or challenge.get("user_id") != user["_id"]:
            raise PermissionError("This biometric challenge is not authorized for this STR download.")
        return self.response(challenge)


biometric_workflow = BiometricWorkflowService()
