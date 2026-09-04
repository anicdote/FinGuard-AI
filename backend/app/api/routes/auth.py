"""Auth routes — register, login, refresh token."""

from fastapi import APIRouter, HTTPException, Depends, Header, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,
)
from app.db.session import get_db
from app.db.repositories.user_repo import UserRepository
from app.schemas.biometric import BiometricChallengeResponse
from app.services.hardware.biometric_workflow import biometric_workflow
from app.services.hardware.fingerprint import HardwareBusyError, HardwareUnavailableError

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "analyst"   # analyst | admin


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=201)
async def register(req: RegisterRequest):
    db   = await get_db()
    repo = UserRepository(db)

    existing = await repo.get_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await repo.create({
        "email":           req.email,
        "hashed_password": hash_password(req.password),
        "name":            req.name,
        "role":            req.role,
    })
    user.pop("hashed_password", None)
    return user


@router.post("/login", response_model=BiometricChallengeResponse, status_code=status.HTTP_202_ACCEPTED)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    db   = await get_db()
    repo = UserRepository(db)

    user = await repo.get_by_email(form.username)
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        challenge = await biometric_workflow.start_login(user, db)
    except HardwareBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HardwareUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return biometric_workflow.response(challenge)


@router.get("/biometric-challenges/{challenge_id}", response_model=BiometricChallengeResponse)
async def complete_biometric_login(
    challenge_id: str,
    challenge_token: str = Header(..., alias="X-Biometric-Challenge-Token", min_length=1),
):
    try:
        return await biometric_workflow.login_challenge_response(challenge_id, challenge_token, await get_db())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Not a refresh token")

    token_data = {"sub": payload["sub"], "role": payload["role"], "email": payload["email"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    current_user.pop("hashed_password", None)
    current_user.pop("biometric_template_id", None)
    current_user.pop("biometric_enrolled_at", None)
    return current_user
