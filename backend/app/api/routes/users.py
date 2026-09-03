"""Users routes — Phase 8: list officers for case assignment (manager/admin only)."""

from fastapi import APIRouter, Depends

from app.core.security import require_manager_or_admin
from app.db.session import get_db
from app.db.repositories.user_repo import UserRepository

router = APIRouter()


@router.get("/officers")
async def list_officers(current_user=Depends(require_manager_or_admin)):
    """List officer accounts (incl. legacy 'analyst' role) so a manager/admin can assign cases."""
    db = await get_db()
    repo = UserRepository(db)
    return await repo.list_by_roles(["officer", "analyst"])
