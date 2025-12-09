"""Feedback Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import FeedbackStatus


class FeedbackBase(BaseModel):
    """Base feedback schema."""

    project_id: str = Field(
        default="NovusProjectDatabase",
        max_length=100,
    )


class FeedbackCreate(FeedbackBase):
    """Schema for creating feedback record after GitHub issue creation."""

    user_id: UUID
    github_issue_number: int = Field(..., gt=0)
    github_issue_url: str = Field(..., max_length=500)


class FeedbackResponse(FeedbackBase):
    """Feedback response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    github_issue_number: int
    github_issue_url: str
    status: FeedbackStatus
    notification_sent_at: datetime | None = None
    response_received_at: datetime | None = None
    response_content: str | None = None
    follow_up_issue_number: int | None = None
    follow_up_issue_url: str | None = None
    created_at: datetime
    updated_at: datetime


class FeedbackClarifyRequest(BaseModel):
    """Request schema for AI clarification questions."""

    feedback_type: str = Field(
        ...,
        description="Either 'bug' or 'feature'",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="User's description of bug or feature",
    )


class FeedbackClarifyResponse(BaseModel):
    """Response schema with AI-generated clarifying questions."""

    questions: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of clarifying questions",
    )


class FeedbackSubmitRequest(BaseModel):
    """Request schema for submitting feedback to create GitHub issue."""

    feedback_type: str = Field(..., description="Either 'bug' or 'feature'")
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    clarifying_answers: list[str] = Field(
        default_factory=list,
        description="Answers to clarifying questions",
    )


class FeedbackSubmitResponse(BaseModel):
    """Response after feedback submission with GitHub issue details."""

    feedback_id: UUID
    github_issue_number: int
    github_issue_url: str
    message: str = "Your feedback has been submitted successfully"
