"""Audit Log Query API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import crud_limit, limiter
from app.models.audit import AuditAction, AuditLog
from app.schemas.audit import AuditLogWithUser, UserSummary
from app.schemas.base import PaginatedResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=PaginatedResponse[AuditLogWithUser])
@limiter.limit(crud_limit)
async def list_audit_logs(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    entity_type: str | None = Query(
        None, description="Filter by entity type (e.g., 'project', 'contact')"
    ),
    entity_id: UUID | None = Query(None, description="Filter by specific entity ID"),
    user_id: UUID | None = Query(
        None, description="Filter by user who made the change"
    ),
    action: AuditAction | None = Query(None, description="Filter by action type"),
    from_date: datetime | None = Query(
        None, description="Filter changes after this date"
    ),
    to_date: datetime | None = Query(
        None, description="Filter changes before this date"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditLogWithUser]:
    """
    Query audit logs with optional filters.

    Returns paginated list of audit log entries with user display names.
    Supports filtering by entity type, entity ID, user, action type, and date range.
    """
    # Build query with user relationship
    query = select(AuditLog).options(selectinload(AuditLog.user))

    # Apply filters
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)
    if from_date:
        query = query.where(AuditLog.created_at >= from_date)
    if to_date:
        query = query.where(AuditLog.created_at <= to_date)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply ordering and pagination
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    audit_logs = result.scalars().all()

    # Build response with user summaries
    items = []
    for log in audit_logs:
        user_summary = None
        if log.user:
            user_summary = UserSummary(
                id=log.user.id,
                display_name=log.user.display_name,
            )

        items.append(
            AuditLogWithUser(
                id=log.id,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                action=log.action,
                user=user_summary,
                changed_fields=log.changed_fields,
                created_at=log.created_at,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )
