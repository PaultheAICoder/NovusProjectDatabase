"""Background job Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus, JobType


class JobResponse(BaseModel):
    """Response for a single job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: JobType
    status: JobStatus
    entity_type: str | None = None
    entity_id: UUID | None = None
    payload: dict | None = None
    result: dict | None = None
    priority: int
    attempts: int
    max_attempts: int
    error_message: str | None = None
    error_context: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    next_retry: datetime | None = None
    created_by: UUID | None = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    items: list[JobResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class JobStatsResponse(BaseModel):
    """Job queue statistics."""

    pending: int
    in_progress: int
    completed: int
    failed: int
    total: int
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Counts per job type"
    )


class JobCreateRequest(BaseModel):
    """Request to create a new job."""

    job_type: JobType
    entity_type: str | None = None
    entity_id: UUID | None = None
    payload: dict | None = None
    priority: int = Field(default=0, ge=0, le=100)
    max_attempts: int = Field(default=5, ge=1, le=20)


class JobQueueProcessResult(BaseModel):
    """Result from processing the job queue."""

    status: str = Field(..., description="Overall status: success, partial, error")
    jobs_processed: int
    jobs_succeeded: int
    jobs_failed: int
    jobs_requeued: int = Field(default=0, description="Jobs requeued for retry")
    jobs_max_retries: int = Field(
        default=0, description="Jobs that hit max retry limit"
    )
    jobs_recovered: int = Field(
        default=0, description="Jobs recovered from stuck state"
    )
    errors: list[str] = Field(default_factory=list)
    timestamp: str
