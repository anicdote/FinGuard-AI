"""Public schemas for server-authoritative biometric challenges."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BiometricChallengeResponse(BaseModel):
    challenge_id: str
    purpose: str
    status: str
    message: str
    expires_at: datetime
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    # Returned only when a password-authenticated login is started.  It is
    # required to poll that otherwise unauthenticated challenge endpoint.
    challenge_token: Optional[str] = None


class EnrolmentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    fingerprint_id: int = Field(..., ge=1, le=127)
