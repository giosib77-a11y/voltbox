"""Current administrator profile.

What it does: returns the signed-in admin, used by the admin shell to render
the header and to confirm the account really has admin rights.
Where it fits: mounted on admin_router, so require_admin has already run.
"""

from fastapi import APIRouter

from app.core.deps import AdminUser
from app.schemas.admin import AdminUserOut

router = APIRouter()


@router.get("/me", summary="Current administrator", response_model=AdminUserOut)
async def read_me(admin: AdminUser) -> AdminUserOut:
    return AdminUserOut.model_validate(admin)
