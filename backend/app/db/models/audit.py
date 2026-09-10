"""Administrator action log.

What it does: one row per admin mutation - who did what, to which entity, and
which fields changed from what to what.
Where it fits: written by app/services/audit.py inside the same transaction as
the change itself, so a rolled-back change leaves no log entry claiming it
happened.
Notes: inventory adjustments and order transitions have their own history tables
(inventory_movements, order_status_history) and are not duplicated here.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class AdminAuditLog(UUIDPrimaryKey, Base):
    __tablename__ = "admin_audit_log"

    # SET NULL, not CASCADE: deleting a user must not erase the record of what
    # they changed. The trail outlives the account.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # TEXT, not a UUID column: not every entity this logs is keyed by UUID.
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    # {"field": [old, new]} - only the fields that actually changed.
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ip: Mapped[str | None] = mapped_column(String(45))

    # clock_timestamp() for the same reason as inventory_movements: several
    # audit rows can be written in one transaction and must stay orderable.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()"), nullable=False
    )

    __table_args__ = (
        Index("ix_admin_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_admin_audit_log_created_at", text("created_at DESC")),
    )
