"""Feedback API endpoints for AI-powered issue submission."""

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import crud_limit, feedback_limit, limiter
from app.schemas.feedback import (
    FeedbackClarifyRequest,
    FeedbackClarifyResponse,
    FeedbackCreate,
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
)
from app.services import AIEnhancementService, FeedbackService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/clarify", response_model=FeedbackClarifyResponse)
@limiter.limit(crud_limit)
async def get_clarifying_questions(
    request: Request,
    data: FeedbackClarifyRequest,
    current_user: CurrentUser,
) -> FeedbackClarifyResponse:
    """Get AI-generated clarifying questions for a feedback submission.

    Returns 3 targeted questions based on the feedback type and description.
    """
    ai_service = AIEnhancementService()
    result = await ai_service.generate_clarifying_questions(
        feedback_type=data.feedback_type,
        description=data.description,
    )

    logger.info(
        "clarifying_questions_requested",
        user_id=str(current_user.id),
        feedback_type=data.feedback_type,
        question_count=len(result.questions),
    )

    return FeedbackClarifyResponse(questions=result.questions)


@router.post(
    "", response_model=FeedbackSubmitResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(feedback_limit)
async def submit_feedback(
    request: Request,
    data: FeedbackSubmitRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> FeedbackSubmitResponse:
    """Submit feedback and create a GitHub issue.

    Enhances the submission with AI, creates a GitHub issue,
    and stores the feedback record for tracking.
    """
    # Validate GitHub API is configured
    if not settings.github_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration not configured",
        )

    # Enhance the issue with AI
    ai_service = AIEnhancementService()
    enhanced = await ai_service.enhance_issue(
        feedback_type=data.feedback_type,
        description=data.description,
        answers=data.clarifying_answers,
    )

    # Build submitter info section
    submitter_info = f"""## Submitter Information
**Project**: NovusProjectDatabase
**Submitted by**: {current_user.display_name} ({current_user.email})
**Submitted at**: {datetime.now(UTC).isoformat()}

---

"""
    full_body = submitter_info + enhanced.body

    # Create GitHub issue
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/issues",
                headers={
                    "Authorization": f"token {settings.github_api_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "title": enhanced.title,
                    "body": full_body,
                    "labels": ["feedback", data.feedback_type],
                },
            )
            response.raise_for_status()
            issue_data = response.json()
    except httpx.HTTPError as e:
        logger.error(
            "github_issue_creation_failed",
            error=str(e),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create GitHub issue",
        )

    issue_number = issue_data["number"]
    issue_url = issue_data["html_url"]

    # Store feedback record
    feedback_service = FeedbackService(db)
    feedback = await feedback_service.create(
        FeedbackCreate(
            user_id=current_user.id,
            github_issue_number=issue_number,
            github_issue_url=issue_url,
        )
    )

    logger.info(
        "feedback_submitted",
        user_id=str(current_user.id),
        feedback_id=str(feedback.id),
        issue_number=issue_number,
    )

    return FeedbackSubmitResponse(
        feedback_id=feedback.id,
        github_issue_number=issue_number,
        github_issue_url=issue_url,
    )
