"""Job status API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.core.logging import get_logger
from app.models.user import UserRole
from app.schemas.job import JobResponse
from app.services.job_service import JobService

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> JobResponse:
    """Get status of a background job.

    Users can check the status of jobs they created.
    Admins can view any job.

    Args:
        job_id: UUID of the job to retrieve
        db: Database session
        current_user: Authenticated user

    Returns:
        JobResponse with job details

    Raises:
        HTTPException: 404 if job not found, 403 if access denied
    """
    service = JobService(db)
    job = await service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Check ownership - allow access if user created the job or is admin
    if (
        job.created_by
        and job.created_by != current_user.id
        and current_user.role != UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - you can only view jobs you created",
        )

    return JobResponse.model_validate(job)
