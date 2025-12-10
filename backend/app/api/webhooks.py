"""GitHub webhook endpoints for feedback system integration."""

import hashlib
import hmac
import re
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import DbSession
from app.config import get_settings
from app.core.logging import get_logger
from app.models.feedback import FeedbackStatus
from app.services import FeedbackService, GraphEmailService

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


def extract_submitter_from_body(body: str) -> dict[str, str] | None:
    """Extract submitter name and email from issue body.

    Looks for pattern: **Submitted by**: Name (email@example.com)
    """
    match = re.match(r"\*\*Submitted by\*\*:\s*([^(]+)\s*\(([^)]+)\)", body)
    if match:
        return {"name": match.group(1).strip(), "email": match.group(2).strip()}
    return None


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

    # Send notification email to submitter
    submitter = extract_submitter_from_body(issue.get("body", ""))
    if submitter and submitter.get("email"):
        graph_service = GraphEmailService()
        if graph_service.is_configured():
            # Determine issue type from labels
            labels = issue.get("labels", [])
            issue_type = (
                "bug"
                if any(label.get("name") == "bug" for label in labels)
                else "feature"
            )

            # Build subject with [NPD] marker for multi-project support
            subject = f"Your {issue_type} report has been resolved [NPD] - Issue #{issue_number}"

            # Build HTML email body
            email_body = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #16a34a;">Your {'Bug Report' if issue_type == 'bug' else 'Feature Request'} Has Been Resolved</h2>

                <p>Hi {submitter.get('name', 'there')},</p>

                <p>We've resolved the {issue_type} you reported:</p>

                <div style="background: #f4f4f5; padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <p style="margin: 0; color: #71717a; font-size: 14px;">Issue #{issue_number}</p>
                    <p style="margin: 8px 0 0 0; font-weight: 500;">{issue.get('title', 'Unknown')}</p>
                </div>

                <p><a href="{issue.get('html_url', '')}" style="color: #2563eb;">View the issue on GitHub</a></p>

                <h3 style="color: #374151;">Please Verify</h3>
                <p>Could you please verify that this resolves your issue? Simply reply to this email with:</p>
                <ul>
                    <li><strong>"Verified"</strong> or <strong>"Looks good"</strong> - if the fix works for you</li>
                    <li><strong>"Not fixed"</strong> or describe what's still wrong - if you need further changes</li>
                </ul>

                <p style="color: #71717a; font-size: 14px; margin-top: 32px;">
                    Thank you for helping us improve!<br>
                    - The Development Team
                </p>
            </div>
            """

            email_sent = await graph_service.send_email(
                to=submitter["email"],
                subject=subject,
                body=email_body,
            )

            if email_sent:
                logger.info(
                    "notification_email_sent",
                    feedback_id=str(feedback.id),
                    issue_number=issue_number,
                    to=submitter["email"],
                )

                # Update feedback with notification timestamp
                await feedback_service.update_status(
                    feedback.id,
                    FeedbackStatus.RESOLVED,
                    notification_sent_at=datetime.now(UTC),
                )

                # Add comment to GitHub issue
                if settings.github_api_token:
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            await client.post(
                                f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/issues/{issue_number}/comments",
                                headers={
                                    "Authorization": f"token {settings.github_api_token}",
                                    "Accept": "application/vnd.github.v3+json",
                                },
                                json={
                                    "body": f"Notification sent to submitter ({submitter['email']}) requesting verification.\nTracking: Feedback #{str(feedback.id)[:8]}"
                                },
                            )
                    except Exception as e:
                        logger.warning("github_comment_failed", error=str(e))
            else:
                logger.warning(
                    "notification_email_failed",
                    feedback_id=str(feedback.id),
                    issue_number=issue_number,
                )
        else:
            logger.debug("graph_email_not_configured_skipping_notification")

    return {"status": "processed", "feedback_id": str(feedback.id)}
