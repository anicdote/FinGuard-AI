"""Auth routes — register, login, biometric login polling, refresh token."""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.db.session import get_db
from app.db.repositories.user_repo import UserRepository
from app.schemas.biometric import BiometricChallengeResponse
from app.services.hardware.biometric_workflow import biometric_workflow
from app.services.hardware.fingerprint import (
    HardwareBusyError,
    HardwareUnavailableError,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "analyst"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/register", status_code=201)
async def register(req: RegisterRequest):
    db = await get_db()
    repo = UserRepository(db)

    existing = await repo.get_by_email(req.email)

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    user = await repo.create(
        {
            "email": req.email,
            "hashed_password": hash_password(req.password),
            "name": req.name,
            "role": req.role,
        }
    )

    user.pop("hashed_password", None)

    return user


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────
#
# Password is the first factor.
#
# A successful password check DOES NOT issue JWTs.
# Instead, it creates a short-lived biometric challenge.
#
# The frontend then polls:
#
# GET /api/v1/auth/biometric-challenges/{challenge_id}
#
# The backend owns the Arduino/R307S interaction.
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=BiometricChallengeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
):
    db = await get_db()
    repo = UserRepository(db)

    user = await repo.get_by_email(form.username)

    if not user or not verify_password(
        form.password,
        user["hashed_password"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    try:
        challenge = await biometric_workflow.start_login(
            user,
            db,
        )

    except HardwareBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except HardwareUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return biometric_workflow._response(challenge)


# ─────────────────────────────────────────────────────────────────────────────
# Biometric login challenge polling
# ─────────────────────────────────────────────────────────────────────────────
#
# IMPORTANT:
#
# This endpoint intentionally requires ONLY the opaque challenge_id.
#
# There is NO:
#
#   X-Biometric-Challenge-Token
#
# header requirement here.
#
# The challenge ID itself is short-lived and server-generated.
# The backend verifies the actual fingerprint against the registered
# fingerprint template before issuing JWTs.
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/biometric-challenges/{challenge_id}",
    response_model=BiometricChallengeResponse,
)
async def complete_biometric_login(
    challenge_id: str,
):
    """
    Poll one biometric login challenge.

    JWTs are issued only after the local fingerprint sensor
    successfully matches the registered fingerprint.
    """

    try:
        db = await get_db()

        return await biometric_workflow.login_challenge_response(
            challenge_id,
            db,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Refresh token
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh(
    refresh_token: str,
):
    payload = decode_token(refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=400,
            detail="Not a refresh token",
        )

    token_data = {
        "sub": payload["sub"],
        "role": payload["role"],
        "email": payload["email"],
    }

    return TokenResponse(
        access_token=create_access_token(
            token_data,
        ),
        refresh_token=create_refresh_token(
            token_data,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Current user
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/me")
async def me(
    current_user=Depends(get_current_user),
):
    current_user.pop(
        "hashed_password",
        None,
    )

    return current_user