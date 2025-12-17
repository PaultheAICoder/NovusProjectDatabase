"""GitHub webhook endpoints for feedback system integration."""

import hashlib
import hmac
import re
from datetime import UTC, datetime

import httpx
import jwt
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import DbSession
from app.config import get_settings
from app.core.logging import get_logger
from app.models.feedback import FeedbackStatus
from app.schemas.monday import (
    MondayWebhookChallenge,
    MondayWebhookChallengeResponse,
    MondayWebhookPayload,
)
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


def verify_monday_signature(token: str | None) -> bool:
    """Verify Monday.com webhook JWT signature.

    Monday.com sends a JWT in the Authorization header. The JWT is signed
    with the app's signing secret. Verification ensures the webhook is
    legitimately from Monday.com.

    Args:
        token: JWT from Authorization header (with or without "Bearer " prefix)

    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.monday_webhook_secret:
        logger.warning("monday_webhook_secret_not_configured")
        return False

    if not token:
        return False

    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        # Decode and verify the JWT
        jwt.decode(
            token,
            settings.monday_webhook_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Monday doesn't set audience
        )
        return True
    except jwt.InvalidTokenError as e:
        logger.warning("monday_webhook_invalid_jwt", error=str(e))
        return False


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


# Monday.com Webhook Endpoints


@router.get("/monday")
async def monday_webhook_health() -> dict[str, str]:
    """Health check endpoint for Monday.com webhook configuration.

    This endpoint can be used to verify the webhook URL is accessible.
    """
    return {"status": "ok", "service": "monday-webhook"}


@router.post("/monday")
async def handle_monday_webhook(
    request: Request,
    authorization: str | None = Header(None),
) -> dict[str, str] | MondayWebhookChallengeResponse:
    """Handle incoming Monday.com webhook events.

    Supports:
    - Challenge verification for webhook setup
    - Item events (create, update, delete)

    Requires valid JWT signature when webhook secret is configured.
    """
    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # Handle challenge verification (no auth required)
    if "challenge" in payload:
        challenge = MondayWebhookChallenge(**payload)
        logger.info(
            "monday_webhook_challenge_received",
            challenge_length=len(challenge.challenge),
        )
        return MondayWebhookChallengeResponse(challenge=challenge.challenge)

    # Check if webhook processing is enabled
    if not settings.monday_webhook_enabled:
        logger.debug("monday_webhook_disabled")
        return {"status": "ignored", "reason": "webhook processing disabled"}

    # Verify signature (if secret is configured)
    if settings.monday_webhook_secret:
        if not verify_monday_signature(authorization):
            logger.warning(
                "monday_webhook_invalid_signature",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
    else:
        logger.warning("monday_webhook_no_secret_configured")

    # Parse and validate webhook payload
    try:
        webhook_payload = MondayWebhookPayload(**payload)
    except Exception as e:
        logger.warning(
            "monday_webhook_invalid_payload",
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {str(e)}",
        )

    event = webhook_payload.event
    event_type = event.type

    # Log the event
    logger.info(
        "monday_webhook_received",
        event_type=event_type,
        board_id=event.boardId,
        item_id=event.pulseId,
        item_name=event.pulseName,
        column_id=event.columnId,
        trigger_uuid=event.triggerUuid,
    )

    # Identify board type (contacts vs organizations)
    board_type = None
    if event.boardId:
        if event.boardId == settings.monday_contacts_board_id:
            board_type = "contacts"
        elif event.boardId == settings.monday_organizations_board_id:
            board_type = "organizations"
        else:
            board_type = "unknown"

    logger.debug(
        "monday_webhook_board_identified",
        board_id=event.boardId,
        board_type=board_type,
    )

    # Return acknowledgment (actual sync logic will be in issue #58)
    return {
        "status": "received",
        "event_type": event_type,
        "board_type": board_type or "unknown",
        "item_id": event.pulseId or "unknown",
    }
