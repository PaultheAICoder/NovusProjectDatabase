"""GitHub webhook endpoints for feedback system integration."""

import hashlib
import hmac

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import DbSession
from app.config import get_settings
from app.core.logging import get_logger
from app.models.feedback import FeedbackStatus
from app.services import FeedbackService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def verify_github_signature(payload: bytes, signature: str | None) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256.

    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value

    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.github_webhook_secret:
        logger.warning("github_webhook_secret_not_configured")
        return False

    if not signature:
        return False

    # GitHub sends signature as "sha256=<hash>"
    if not signature.startswith("sha256="):
        return False

    expected_signature = signature[7:]  # Remove "sha256=" prefix

    # Compute HMAC-SHA256
    computed = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed, expected_signature)


@router.get("/github")
async def webhook_health() -> dict[str, str]:
    """Health check endpoint for GitHub webhook configuration.

    This is a public endpoint used by GitHub to verify the webhook URL.
    """
    return {"status": "ok", "service": "github-webhook"}


@router.post("/github")
async def handle_github_webhook(
    request: Request,
    db: DbSession,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
) -> dict[str, str]:
    """Handle incoming GitHub webhook events.

    Processes issue closed events to update feedback status.
    Requires valid webhook signature for authentication.
    """
    # Read raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    if not verify_github_signature(body, x_hub_signature_256):
        logger.warning(
            "github_webhook_invalid_signature",
            event=x_github_event,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # Only process issue events
    if x_github_event != "issues":
        logger.debug(
            "github_webhook_ignored",
            event=x_github_event,
            reason="not_issues_event",
        )
        return {"status": "ignored", "reason": "not an issues event"}

    action = payload.get("action")
    issue = payload.get("issue", {})
    issue_number = issue.get("number")

    logger.info(
        "github_webhook_received",
        event=x_github_event,
        action=action,
        issue_number=issue_number,
    )

    # Only process "closed" action
    if action != "closed":
        return {"status": "ignored", "reason": f"action '{action}' not handled"}

    if not issue_number:
        return {"status": "ignored", "reason": "no issue number"}

    # Find and update feedback record
    feedback_service = FeedbackService(db)
    feedback = await feedback_service.get_by_issue_number(issue_number)

    if not feedback:
        logger.debug(
            "github_webhook_no_feedback",
            issue_number=issue_number,
        )
        return {"status": "ignored", "reason": "no matching feedback record"}

    # Update status to resolved
    await feedback_service.update_status(feedback.id, FeedbackStatus.RESOLVED)

    logger.info(
        "feedback_resolved_via_webhook",
        feedback_id=str(feedback.id),
        issue_number=issue_number,
    )

    return {"status": "processed", "feedback_id": str(feedback.id)}
