"""Feedback service for CRUD operations and state management.

Provides database operations for feedback tracking:
- Creating feedback records linked to GitHub issues
- Retrieving feedback by ID or issue number
- Updating feedback status through resolution workflow
- Managing email monitor state persistence
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.feedback import EmailMonitorState, Feedback, FeedbackStatus
from app.schemas.feedback import FeedbackCreate

logger = get_logger(__name__)

SINGLETON_ID = "singleton"


class FeedbackService:
    """Service for feedback CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: FeedbackCreate) -> Feedback:
        """Create a new feedback record.

        Args:
            data: FeedbackCreate schema with required fields

        Returns:
            Created Feedback model instance
        """
        feedback = Feedback(
            user_id=data.user_id,
            project_id=data.project_id,
            github_issue_number=data.github_issue_number,
            github_issue_url=data.github_issue_url,
            status=FeedbackStatus.PENDING,
        )
        self.db.add(feedback)
        await self.db.flush()
        await self.db.refresh(feedback)

        logger.info(
            "feedback_created",
            feedback_id=str(feedback.id),
            issue_number=feedback.github_issue_number,
        )

        return feedback

    async def get_by_id(self, feedback_id: UUID) -> Feedback | None:
        """Get feedback by ID.

        Args:
            feedback_id: UUID of the feedback record

        Returns:
            Feedback model or None if not found
        """
        result = await self.db.execute(
            select(Feedback)
            .options(selectinload(Feedback.user))
            .where(Feedback.id == feedback_id)
        )
        return result.scalar_one_or_none()

    async def get_by_issue_number(self, issue_number: int) -> Feedback | None:
        """Get feedback by GitHub issue number.

        Args:
            issue_number: GitHub issue number

        Returns:
            Feedback model or None if not found
        """
        result = await self.db.execute(
            select(Feedback)
            .options(selectinload(Feedback.user))
            .where(Feedback.github_issue_number == issue_number)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        feedback_id: UUID,
        status: FeedbackStatus,
        **kwargs: datetime | str | int | None,
    ) -> Feedback | None:
        """Update feedback status and related fields.

        Args:
            feedback_id: UUID of the feedback record
            status: New status
            **kwargs: Additional fields to update:
                - notification_sent_at: datetime
                - notification_message_id: str
                - response_received_at: datetime
                - response_email_id: str
                - response_content: str
                - follow_up_issue_number: int
                - follow_up_issue_url: str

        Returns:
            Updated Feedback model or None if not found
        """
        feedback = await self.get_by_id(feedback_id)
        if not feedback:
            return None

        feedback.status = status

        # Update optional fields
        allowed_fields = {
            "notification_sent_at",
            "notification_message_id",
            "response_received_at",
            "response_email_id",
            "response_content",
            "follow_up_issue_number",
            "follow_up_issue_url",
        }

        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(feedback, field, value)

        await self.db.flush()
        await self.db.refresh(feedback)

        logger.info(
            "feedback_status_updated",
            feedback_id=str(feedback_id),
            new_status=status.value,
        )

        return feedback

    async def get_pending(self) -> list[Feedback]:
        """Get all feedback in 'pending' status.

        Used for verification reminder workflows.

        Returns:
            List of pending Feedback records
        """
        result = await self.db.execute(
            select(Feedback)
            .options(selectinload(Feedback.user))
            .where(Feedback.status == FeedbackStatus.PENDING)
            .order_by(Feedback.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_resolved(self) -> list[Feedback]:
        """Get all feedback in 'resolved' status.

        Used by email monitoring to match incoming replies.

        Returns:
            List of resolved Feedback records
        """
        result = await self.db.execute(
            select(Feedback)
            .options(selectinload(Feedback.user))
            .where(Feedback.status == FeedbackStatus.RESOLVED)
            .order_by(Feedback.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        status: FeedbackStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Feedback]:
        """List feedback records with optional filtering.

        Args:
            status: Optional status filter
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of Feedback records
        """
        query = select(Feedback).options(selectinload(Feedback.user))

        if status:
            query = query.where(Feedback.status == status)

        query = query.order_by(Feedback.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # Email Monitor State Management

    async def get_last_check_time(self) -> datetime:
        """Get the last email check time.

        Returns the current time minus 15 minutes if no state exists (first run).

        Returns:
            datetime of last check
        """
        result = await self.db.execute(
            select(EmailMonitorState).where(EmailMonitorState.id == SINGLETON_ID)
        )
        state = result.scalar_one_or_none()

        if not state:
            # First run - return 15 minutes ago as default
            return datetime.now(UTC) - timedelta(minutes=15)

        return state.last_check_time

    async def update_last_check_time(self, time: datetime) -> None:
        """Update the last email check time.

        Creates the singleton record if it doesn't exist.

        Args:
            time: datetime to set as last check time
        """
        result = await self.db.execute(
            select(EmailMonitorState).where(EmailMonitorState.id == SINGLETON_ID)
        )
        state = result.scalar_one_or_none()

        if state:
            state.last_check_time = time
        else:
            state = EmailMonitorState(id=SINGLETON_ID, last_check_time=time)
            self.db.add(state)

        await self.db.flush()

        logger.debug("email_check_time_updated", last_check=time.isoformat())
