"""Team management API endpoints (Admin only)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.core.logging import get_logger
from app.core.rate_limit import admin_limit, limiter
from app.models.team import Team
from app.schemas.team import (
    TeamCreate,
    TeamDetailResponse,
    TeamListResponse,
    TeamResponse,
    TeamUpdate,
)
from app.services.team_sync_service import TeamSyncService

logger = get_logger(__name__)

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=TeamListResponse)
@limiter.limit(admin_limit)
async def list_teams(
    request: Request,
    db: DbSession,
    admin_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TeamListResponse:
    """List all teams with pagination. Admin only."""
    # Count total
    total = await db.scalar(select(func.count()).select_from(Team)) or 0

    # Fetch paginated teams
    result = await db.execute(
        select(Team).order_by(Team.name).offset((page - 1) * page_size).limit(page_size)
    )
    teams = result.scalars().all()

    return TeamListResponse(
        items=[TeamResponse.model_validate(t) for t in teams],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(admin_limit)
async def create_team(
    request: Request,
    data: TeamCreate,
    db: DbSession,
    admin_user: AdminUser,
) -> TeamResponse:
    """Create a new team from Azure AD group. Admin only."""
    team = Team(
        name=data.name,
        azure_ad_group_id=data.azure_ad_group_id,
        description=data.description,
    )
    db.add(team)

    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team with Azure AD group ID '{data.azure_ad_group_id}' already exists",
        )

    logger.info(
        "team_created",
        team_id=str(team.id),
        name=team.name,
        azure_ad_group_id=team.azure_ad_group_id,
        created_by=str(admin_user.id),
    )

    return TeamResponse.model_validate(team)


@router.get("/{team_id}", response_model=TeamDetailResponse)
@limiter.limit(admin_limit)
async def get_team(
    request: Request,
    team_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> TeamDetailResponse:
    """Get team details with member list. Admin only."""
    result = await db.execute(
        select(Team).where(Team.id == team_id).options(selectinload(Team.members))
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    return TeamDetailResponse.model_validate(team)


@router.put("/{team_id}", response_model=TeamResponse)
@limiter.limit(admin_limit)
async def update_team(
    request: Request,
    team_id: UUID,
    data: TeamUpdate,
    db: DbSession,
    admin_user: AdminUser,
) -> TeamResponse:
    """Update team details. Admin only."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if data.name is not None:
        team.name = data.name
    if data.description is not None:
        team.description = data.description

    await db.flush()

    logger.info(
        "team_updated",
        team_id=str(team.id),
        updated_by=str(admin_user.id),
    )

    return TeamResponse.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(admin_limit)
async def delete_team(
    request: Request,
    team_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> None:
    """Delete a team. Admin only.

    Also removes all team members and project permissions associated with this team.
    """
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    team_name = team.name
    await db.delete(team)
    await db.flush()

    logger.info(
        "team_deleted",
        team_id=str(team_id),
        team_name=team_name,
        deleted_by=str(admin_user.id),
    )


class TeamSyncResponse(BaseModel):
    """Response schema for team sync operation."""

    status: str
    team_id: str
    team_name: str
    members_added: int
    members_removed: int
    members_unchanged: int
    errors: list[str]
    synced_at: str


@router.post("/{team_id}/sync", response_model=TeamSyncResponse)
@limiter.limit(admin_limit)
async def sync_team(
    request: Request,
    team_id: UUID,
    db: DbSession,
    admin_user: AdminUser,
) -> TeamSyncResponse:
    """Manually trigger Azure AD group membership sync. Admin only.

    Fetches current group members from Azure AD and updates the
    local TeamMember cache. This is useful for immediate sync when
    group membership changes, rather than waiting for the scheduled
    cron job.

    Returns statistics about members added, removed, or unchanged.
    """
    # Fetch team
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if sync is configured
    sync_service = TeamSyncService()
    if not sync_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure AD not configured for team sync",
        )

    # Perform sync
    sync_result = await sync_service.sync_team(db, team)

    await db.commit()

    logger.info(
        "team_sync_manual",
        team_id=str(team.id),
        team_name=team.name,
        members_added=sync_result.members_added,
        members_removed=sync_result.members_removed,
        triggered_by=str(admin_user.id),
    )

    return TeamSyncResponse(
        status="success" if not sync_result.errors else "partial",
        team_id=str(sync_result.team_id),
        team_name=sync_result.team_name,
        members_added=sync_result.members_added,
        members_removed=sync_result.members_removed,
        members_unchanged=sync_result.members_unchanged,
        errors=sync_result.errors,
        synced_at=sync_result.synced_at.isoformat(),
    )
