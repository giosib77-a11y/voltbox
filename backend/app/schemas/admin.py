"""Admin-facing response schemas.

What it does: response models for the admin API.
Where it fits: used by the routes under app/api/v1/routes/admin/.
Notes: these are separate from the storefront schemas on purpose. Returning an
ORM object would leak password_hash and token hashes, and the storefront UserOut
deliberately hides `role`.
"""

from datetime import datetime
from uuid import UUID

from app.schemas.base import ApiModel


class AdminUserOut(ApiModel):
    """The signed-in administrator. Never includes credentials."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime
