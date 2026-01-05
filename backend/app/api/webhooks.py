"""GitHub webhook endpoints for feedback system integration."""

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
import pydantic
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import DbSession
from app.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter, webhook_limit
from app.models.feedback import FeedbackStatus
from app.schemas.monday import (
    MondayWebhookChallenge,
    MondayWebhookChallengeResponse,
    MondayWebhookPayload,
)
from app.services import FeedbackService, GraphEmailService
from app.services.monday_service import MondayAPIError, MondayService

logger = get_logger(__name__)
settings = get_settings()

# Maximum payload size for Monday.com webhooks (1MB)
# Challenge payloads are typically <100 bytes, event payloads <10KB
MAX_MONDAY_WEBHOOK_PAYLOAD_SIZE = 1 * 1024 * 1024

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
@limiter.limit(webhook_limit)
async def webhook_health(request: Request) -> dict[str, str]:
    """Health check endpoint for GitHub webhook configuration.

    This is a public endpoint used by GitHub to verify the webhook URL.
    """
    return {"status": "ok", "service": "github-webhook"}


@router.post("/github")
@limiter.limit(webhook_limit)
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
    except json.JSONDecodeError as e:
        logger.warning(
            "github_webhook_invalid_json",
            error=str(e),
            exc_info=True,
        )
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
                    except httpx.HTTPError as e:
                        logger.warning(
                            "github_comment_failed",
                            error=str(e),
                            exc_info=True,
                        )
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
@limiter.limit(webhook_limit)
async def monday_webhook_health(request: Request) -> dict[str, str]:
    """Health check endpoint for Monday.com webhook configuration.

    This endpoint can be used to verify the webhook URL is accessible.
    """
    return {"status": "ok", "service": "monday-webhook"}


@router.post("/monday")
@limiter.limit(webhook_limit)
async def handle_monday_webhook(
    request: Request,
    db: DbSession,
    authorization: str | None = Header(None),
) -> dict[str, Any] | MondayWebhookChallengeResponse:
    """Handle incoming Monday.com webhook events.

    Supports:
    - Challenge verification for webhook setup
    - Item events (create, update, delete)

    Security: Authentication is verified before processing non-challenge payloads.
    """
    # Step 1: Check Content-Length header for DoS protection
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_MONDAY_WEBHOOK_PAYLOAD_SIZE:
                logger.warning(
                    "monday_webhook_payload_too_large",
                    content_length=content_length,
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Payload too large",
                )
        except ValueError:
            pass  # Invalid Content-Length, will be caught during body read

    # Step 2: Read raw body with size limit
    body = await request.body()
    if len(body) > MAX_MONDAY_WEBHOOK_PAYLOAD_SIZE:
        logger.warning(
            "monday_webhook_payload_too_large",
            actual_size=len(body),
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large",
        )

    # Step 3: Quick challenge detection using lightweight check
    # Monday challenge payloads are simple: {"challenge": "token"}
    # We can check for this pattern without full JSON parsing
    is_likely_challenge = b'"challenge"' in body and b'"event"' not in body

    if is_likely_challenge:
        # For challenge requests, parse JSON and respond
        # Challenge requests don't include auth (Monday.com limitation)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        if "challenge" in payload:
            challenge = MondayWebhookChallenge(**payload)
            logger.info(
                "monday_webhook_challenge_received",
                challenge_length=len(challenge.challenge),
            )
            return MondayWebhookChallengeResponse(challenge=challenge.challenge)

    # Step 4: For non-challenge requests, check webhook enabled
    if not settings.monday_webhook_enabled:
        logger.debug("monday_webhook_disabled")
        return {"status": "ignored", "reason": "webhook processing disabled"}

    # Step 5: Verify signature BEFORE parsing payload (security-first)
    if settings.monday_webhook_secret:
        if not verify_monday_signature(authorization):
            logger.warning("monday_webhook_invalid_signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
    else:
        logger.warning("monday_webhook_no_secret_configured")

    # Step 6: Now safe to parse full payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # Parse and validate webhook payload
    try:
        webhook_payload = MondayWebhookPayload(**payload)
    except pydantic.ValidationError as e:
        logger.warning(
            "monday_webhook_invalid_payload",
            error=str(e),
            exc_info=True,
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

    # Process the event based on type
    result: dict[str, Any] = {"status": "received", "event_type": event_type}

    if board_type in ("contacts", "organizations"):
        monday_service = MondayService(db)
        try:
            if event_type == "create_item":
                sync_result = await monday_service.process_monday_create(
                    board_id=event.boardId or "",
                    monday_item_id=event.pulseId or "",
                    item_name=event.pulseName or "",
                    board_type=board_type,
                )
                result["sync_result"] = sync_result

            elif event_type in ("change_column_value", "update_column_value"):
                # Extract value from event
                value_dict = None
                if event.value:
                    value_dict = event.value.model_dump()

                previous_dict = None
                if event.previousValue:
                    previous_dict = event.previousValue.model_dump()

                sync_result = await monday_service.process_monday_update(
                    board_id=event.boardId or "",
                    monday_item_id=event.pulseId or "",
                    column_id=event.columnId or "",
                    new_value=value_dict,
                    previous_value=previous_dict,
                    board_type=board_type,
                )
                result["sync_result"] = sync_result

            elif event_type in ("item_deleted", "delete_item"):
                sync_result = await monday_service.process_monday_delete(
                    board_id=event.boardId or "",
                    monday_item_id=event.pulseId or "",
                    board_type=board_type,
                )
                result["sync_result"] = sync_result

            else:
                result["sync_result"] = {
                    "action": "skipped",
                    "reason": f"unhandled_event_type:{event_type}",
                }

        except MondayAPIError as e:
            logger.error(
                "monday_webhook_sync_failed",
                event_type=event_type,
                monday_item_id=event.pulseId,
                error=str(e),
                exc_info=True,
            )
            result["sync_result"] = {"action": "error", "message": str(e)}
        finally:
            await monday_service.close()
    else:
        result["sync_result"] = {"action": "skipped", "reason": "unknown_board"}

    result["board_type"] = board_type or "unknown"
    result["item_id"] = event.pulseId or "unknown"

    return result
