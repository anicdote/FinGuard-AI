"""Server-authoritative biometric workflows for login and STR submission."""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token

from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.biometric_repo import BiometricChallengeRepository
from app.db.repositories.user_repo import UserRepository

from app.services.hardware.fingerprint import (
    HardwareBusyError,
    HardwareUnavailableError,
    fingerprint_service,
)


logger = logging.getLogger("finguard.biometric")


def utcnow() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def normalize_utc_datetime(value: datetime) -> datetime:
    """
    Normalize a datetime to timezone-aware UTC.

    MongoDB/PyMongo may return UTC datetimes without timezone information.
    Treat naive datetimes as UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class BiometricWorkflowService:
    """
    Coordinates:

    - biometric login challenges
    - STR submission challenges
    - local Arduino fingerprint verification
    - short-lived challenge state
    - JWT issuance
    - immutable audit records

    Fingerprint templates never leave the local biometric controller.
    """

    # =====================================================================
    # PUBLIC CHALLENGE START METHODS
    # =====================================================================

    async def start_login(self, user: dict, db) -> dict:
        """Start a biometric login challenge."""
        return await self._start_challenge(
            db=db,
            user=user,
            purpose="login",
        )

    async def start_str_submission(
        self,
        user: dict,
        case: dict,
        db,
    ) -> dict:
        """Start a biometric challenge for STR submission."""
        return await self._start_challenge(
            db=db,
            user=user,
            purpose="str_submission",
            case_id=case["id"],
        )

    # =====================================================================
    # CHALLENGE CREATION
    # =====================================================================

    async def _start_challenge(
        self,
        db,
        user: dict,
        purpose: str,
        case_id: Optional[str] = None,
    ) -> dict:
        """
        Create a short-lived biometric challenge and start the
        server-side fingerprint verification task.
        """

        template_id = user.get("biometric_template_id")

        # A valid Arduino fingerprint template ID is required.
        if not isinstance(template_id, int) or template_id < 1:
            if case_id:
                await self._audit(
                    db=db,
                    case_id=case_id,
                    action=(
                        "STR_BIOMETRIC_AUTH_FAILED"
                        if purpose == "str_submission"
                        else "BIOMETRIC_LOGIN_FAILED"
                    ),
                    user=user,
                    metadata={
                        "reason": "no_registered_fingerprint",
                    },
                )

            raise HardwareUnavailableError(
                "No registered fingerprint is assigned to this user."
            )

        challenge_id = secrets.token_urlsafe(32)

        repository = BiometricChallengeRepository(db)

        challenge = await repository.create(
            {
                "challenge_id": challenge_id,
                "purpose": purpose,
                "user_id": user["_id"],
                "user_email": user.get("email"),
                "case_id": case_id,
                "status": "pending",
                "consumed": False,
                "expires_at": (
                    utcnow()
                    + timedelta(
                        seconds=settings.BIOMETRIC_CHALLENGE_TTL_SEC
                    )
                ),
            }
        )

        # IMPORTANT:
        #
        # The current fingerprint service owns the complete physical
        # verification operation through:
        #
        #     fingerprint_service.verify(...)
        #
        # Do NOT use reserve() + verify_reserved() here.
        #
        # This keeps the workflow compatible with the current Arduino
        # service implementation.
        asyncio.create_task(
            self._perform_verification(
                challenge_id=challenge_id,
                template_id=template_id,
                purpose=purpose,
                user=user,
                case_id=case_id,
                db=db,
            ),
            name=f"biometric-{purpose}-{challenge_id[:8]}",
        )

        return challenge

    # =====================================================================
    # HARDWARE VERIFICATION
    # =====================================================================

    async def _perform_verification(
        self,
        challenge_id: str,
        template_id: int,
        purpose: str,
        user: dict,
        case_id: Optional[str],
        db,
    ) -> None:
        """
        Perform the real fingerprint scan in the background.

        The browser only polls MongoDB challenge state. It never communicates
        directly with the Arduino.
        """

        repository = BiometricChallengeRepository(db)

        prefix = (
            "STR_BIOMETRIC_AUTH"
            if purpose == "str_submission"
            else "BIOMETRIC_LOGIN"
        )

        try:
            # Tell the frontend that the physical scan can begin.
            await repository.update(
                challenge_id,
                {
                    "status": "finger_required",
                    "message": (
                        "Place your registered finger "
                        "on the local sensor."
                    ),
                },
            )

            # -------------------------------------------------------------
            # REAL HARDWARE VERIFICATION
            # -------------------------------------------------------------
            #
            # Current fingerprint.py exposes:
            #
            #     verify(request_id, expected_fingerprint_id, purpose)
            #
            # and returns VerificationResult.
            #
            result = await fingerprint_service.verify(
                challenge_id,
                template_id,
                (
                    "STR"
                    if purpose == "str_submission"
                    else "LOGIN"
                ),
            )

            # Store only the verification result.
            # Fingerprint image/template never enters MongoDB.
            await repository.update(
                challenge_id,
                {
                    "status": result.status,
                    "message": result.detail,
                    "fingerprint_id": result.fingerprint_id,
                },
            )

            await self._audit(
                db=db,
                case_id=case_id,
                action=(
                    f"{prefix}_SUCCESS"
                    if result.success
                    else f"{prefix}_FAILED"
                ),
                user=user,
                metadata={
                    "result": result.status,
                    "fingerprint_id": result.fingerprint_id,
                },
            )

        except HardwareBusyError as exc:
            logger.warning(
                "Biometric hardware busy for %s: %s",
                challenge_id,
                exc,
            )

            await repository.update(
                challenge_id,
                {
                    "status": "hardware_error",
                    "message": str(exc),
                },
            )

            await self._audit(
                db=db,
                case_id=case_id,
                action=f"{prefix}_FAILED",
                user=user,
                metadata={
                    "result": "hardware_busy",
                },
            )

        except HardwareUnavailableError as exc:
            logger.error(
                "Biometric hardware unavailable for %s: %s",
                challenge_id,
                exc,
            )

            await repository.update(
                challenge_id,
                {
                    "status": "hardware_error",
                    "message": str(exc),
                },
            )

            await self._audit(
                db=db,
                case_id=case_id,
                action=f"{prefix}_FAILED",
                user=user,
                metadata={
                    "result": "hardware_unavailable",
                },
            )

        except Exception:
            # A background task must ALWAYS leave a decisive state.
            logger.exception(
                "Biometric verification failed for %s",
                challenge_id,
            )

            await repository.update(
                challenge_id,
                {
                    "status": "hardware_error",
                    "message": "Biometric controller error.",
                },
            )

            await self._audit(
                db=db,
                case_id=case_id,
                action=f"{prefix}_FAILED",
                user=user,
                metadata={
                    "result": "hardware_error",
                },
            )

    # =====================================================================
    # LOGIN POLLING / COMPLETION
    # =====================================================================

    async def login_challenge_response(
        self,
        challenge_id: str,
        db,
    ) -> dict:
        """
        Poll a login biometric challenge.

        When fingerprint verification succeeds, consume the challenge and
        issue access + refresh JWTs.
        """

        repository = BiometricChallengeRepository(db)

        challenge = await self._valid_challenge(
            challenge_id,
            "login",
            repository,
        )

        response = self.response(challenge)

        # Fingerprint has not succeeded yet.
        if challenge["status"] != "success":
            return response

        # Prevent replay of a successful biometric challenge.
        if challenge.get("consumed"):
            return response

        consumed = await repository.consume(challenge_id)

        if not consumed:
            latest = await repository.get(challenge_id)

            if latest:
                return self.response(latest)

            return response

        user = await UserRepository(db).get_by_id(
            challenge["user_id"]
        )

        if not user:
            raise ValueError("User no longer exists.")

        token_data = {
            "sub": user["_id"],
            "role": user["role"],
            "email": user["email"],
        }

        response.update(
            {
                "access_token": create_access_token(token_data),
                "refresh_token": create_refresh_token(token_data),
                "token_type": "bearer",
            }
        )

        return response

    # =====================================================================
    # STR POLLING / COMPLETION
    # =====================================================================

    async def str_challenge_response(
        self,
        challenge_id: str,
        case_id: str,
        user: dict,
        db,
    ) -> dict:
        """
        Poll an STR biometric challenge.

        A successful fingerprint:

        1. consumes the challenge
        2. changes the case status to filed
        3. records an immutable audit event
        """

        repository = BiometricChallengeRepository(db)

        challenge = await self._valid_challenge(
            challenge_id,
            "str_submission",
            repository,
        )

        # Challenge must belong to BOTH the case and current analyst.
        if (
            challenge.get("case_id") != case_id
            or challenge.get("user_id") != user["_id"]
        ):
            raise PermissionError(
                "This biometric challenge is not authorized "
                "for the current STR submission."
            )

        response = self.response(challenge)

        # Nothing to do until fingerprint succeeds.
        if challenge["status"] != "success":
            return response

        # Already consumed = already processed.
        if challenge.get("consumed"):
            return response

        consumed = await repository.consume(challenge_id)

        if not consumed:
            latest = await repository.get(challenge_id)

            if latest:
                return self.response(latest)

            return response

        now = utcnow()

        # -------------------------------------------------------------
        # FINAL STR FILING STATE
        # -------------------------------------------------------------
        result = await db.cases.update_one(
            {"id": case_id},
            {
                "$set": {
                    "status": "filed",
                    "str_submitted_at": now,
                    "updated_at": now,
                }
            },
        )

        if result.matched_count == 0:
            raise ValueError(
                "Case could not be updated after biometric authorization."
            )

        await self._audit(
            db=db,
            case_id=case_id,
            action="str_submission_confirmed",
            user=user,
            metadata={
                "submission": "internal_case_state_recorded",
                "biometric_authorization": True,
            },
        )

        response["message"] = (
            "Biometric authorization succeeded; "
            "STR case status is now filed."
        )

        return response

    # =====================================================================
    # BIOMETRIC ENROLLMENT
    # =====================================================================

    async def enroll(
        self,
        administrator: dict,
        user_id: str,
        fingerprint_id: int,
        db,
    ) -> dict:
        """
        Enroll a fingerprint directly on the Arduino and associate its
        numeric template ID with the target user.
        """

        request_id = secrets.token_urlsafe(20)

        result = await fingerprint_service.enroll(
            request_id,
            fingerprint_id,
        )

        if not result.success:
            return result.to_dict()

        user = await UserRepository(db).get_by_id(
            user_id
        )

        if not user:
            raise ValueError(
                "Target user not found."
            )

        mapped = await UserRepository(db).set_biometric_template(
            user_id,
            fingerprint_id,
        )

        if not mapped:
            raise ValueError(
                "Target user could not be mapped "
                "to the enrolled fingerprint."
            )

        return result.to_dict()

    # =====================================================================
    # AUDIT
    # =====================================================================

    async def _audit(
        self,
        db,
        case_id: Optional[str],
        action: str,
        user: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Write an immutable audit record.

        Login itself has no case ID, so login-only events are not written to
        the case audit collection. STR/case events always include the case ID.
        """

        if not case_id:
            return

        performed_by = None

        if user:
            performed_by = {
                "id": str(
                    user.get(
                        "_id",
                        "unknown",
                    )
                ),
                "name": user.get(
                    "name",
                    user.get(
                        "email",
                        "Unknown",
                    ),
                ),
                "role": user.get(
                    "role",
                    "system",
                ),
            }

        await AuditRepository(db).record(
            case_id=str(case_id),
            action=action,
            performed_by=performed_by,
            metadata=metadata or {},
        )

    # =====================================================================
    # CHALLENGE VALIDATION
    # =====================================================================

    @staticmethod
    async def _valid_challenge(
        challenge_id: str,
        purpose: str,
        repository: BiometricChallengeRepository,
    ) -> dict:
        """
        Load and validate a biometric challenge.
        """

        challenge = await repository.get(
            challenge_id
        )

        if (
            not challenge
            or challenge.get("purpose") != purpose
        ):
            raise ValueError(
                "Biometric challenge not found."
            )

        expires_at = normalize_utc_datetime(
            challenge["expires_at"]
        )

        challenge["expires_at"] = expires_at

        if (
            expires_at <= utcnow()
            and challenge.get("status")
            in {
                "pending",
                "finger_required",
                "verifying",
            }
        ):
            await repository.update(
                challenge_id,
                {
                    "status": "timeout",
                    "message": (
                        "Biometric challenge expired."
                    ),
                },
            )

            challenge["status"] = "timeout"
            challenge["message"] = (
                "Biometric challenge expired."
            )

        return challenge

    # =====================================================================
    # RESPONSE SERIALIZER
    # =====================================================================

    @staticmethod
    def response(
        challenge: dict,
    ) -> dict:
        """
        Public response serializer.

        IMPORTANT:
        auth.py in the current project calls:

            biometric_workflow.response(challenge)

        Therefore this must remain a PUBLIC method.
        """

        messages = {
            "pending": (
                "Place your registered finger "
                "on the local sensor."
            ),
            "finger_required": (
                "Place your registered finger "
                "on the local sensor."
            ),
            "verifying": (
                "Verifying fingerprint..."
            ),
            "success": (
                "Fingerprint verified."
            ),
            "failed": (
                "Fingerprint was not recognized."
            ),
            "timeout": (
                "Fingerprint verification timed out."
            ),
            "hardware_error": (
                "Biometric hardware is unavailable."
            ),
        }

        expires_at = normalize_utc_datetime(
            challenge["expires_at"]
        )

        response = {
            "challenge_id": challenge["challenge_id"],
            "purpose": challenge["purpose"],
            "status": challenge["status"],
            "message": (
                challenge.get("message")
                or messages.get(
                    challenge["status"],
                    "Verification in progress.",
                )
            ),
            "expires_at": expires_at.isoformat(),
        }

        # Preserve challenge_token if the calling route has attached one.
        if challenge.get("challenge_token"):
            response["challenge_token"] = (
                challenge["challenge_token"]
            )

        # Preserve access tokens if a caller has attached them.
        if challenge.get("access_token"):
            response["access_token"] = (
                challenge["access_token"]
            )

        if challenge.get("refresh_token"):
            response["refresh_token"] = (
                challenge["refresh_token"]
            )

        if challenge.get("token_type"):
            response["token_type"] = (
                challenge["token_type"]
            )

        return response

    # Backwards-compatible private alias.
    @staticmethod
    def _response(
        challenge: dict,
    ) -> dict:
        return BiometricWorkflowService.response(
            challenge
        )


biometric_workflow = BiometricWorkflowService()