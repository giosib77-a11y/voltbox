"""Recording what an administrator changed.

What it does: writes one admin_audit_log row per mutation, holding only the
fields that actually changed and their before/after values.
Where it fits: called by admin services inside the same transaction as the
change, so a rolled-back change cannot leave a log entry claiming it happened.
Notes: inventory adjustments and order transitions have their own history tables
and are not duplicated here - two records of one event drift apart eventually.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminAuditLog

#: Never written to the log, whatever a caller passes.
REDACTED_FIELDS = frozenset({"password", "password_hash", "token", "token_hash", "refresh_token"})

#: Columns the database maintains. Excluded for two reasons: `updated_at` would
#: appear in the diff of every single edit and bury the field that actually
#: changed, and reading it straight after a flush triggers a lazy refresh that
#: raises MissingGreenlet under async SQLAlchemy.
AUTO_COLUMNS = frozenset({"id", "created_at", "updated_at"})


def snapshot(instance: object, columns: list[str]) -> dict[str, Any]:
    """Values of `columns`, skipping the ones the database maintains."""
    return {name: getattr(instance, name) for name in columns if name not in AUTO_COLUMNS}


def _plain(value: Any) -> Any:
    """JSON-safe version of a value, for storing in a JSONB column."""
    if isinstance(value, Decimal):
        # str, not float: a float would silently change 10.10 into 10.099999...
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """`{"field": [old, new]}` for the fields that differ.

    Only changed fields are kept: logging every field on every edit buries the
    one thing a reader is looking for.
    """
    changes: dict[str, list[Any]] = {}
    for key, new_value in after.items():
        if key in REDACTED_FIELDS:
            continue
        old_value = before.get(key)
        if old_value != new_value:
            changes[key] = [_plain(old_value), _plain(new_value)]
    return changes


async def record(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str,
    changes: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AdminAuditLog | None:
    """Append an audit row. Returns None when there was nothing to record.

    An update that changed nothing writes no row - an audit trail full of empty
    entries is harder to read than one without them.
    """
    payload = {k: v for k, v in (changes or {}).items() if k not in REDACTED_FIELDS}
    if action.endswith(".update") and not payload:
        return None

    entry = AdminAuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=_plain(payload),
        ip=ip,
    )
    db.add(entry)
    await db.flush()
    return entry
