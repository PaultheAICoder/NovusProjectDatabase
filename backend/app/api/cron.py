"""Cron job endpoints for background processing.

Protected by CRON_SECRET bearer token authentication.
These endpoints should be called by external schedulers (cron-job.org, etc).
"""

import re
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import DbSession
from app.config import get_settings
from app.core.logging import get_logger
from app.models.feedback import FeedbackStatus
from app.schemas.document import DocumentQueueProcessResult
from app.schemas.job import JobQueueProcessResult
from app.schemas.monday import SyncQueueProcessResult
from app.services import (
    FeedbackService,
    GraphEmailService,
    ParseAction,
    extract_issue_number,
    extract_project_marker,
    parse_reply_decision,
    process_document_queue,
    process_sync_queue,
)
from app.services.jira_service import refresh_all_jira_statuses

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/cron", tags=["cron"])

# NPD project marker for multi-project email filtering
NPD_PROJECT_MARKER = "NPD"


class EmailMonitorResult(BaseModel):
    """Response schema for email monitor endpoint."""

    status: str
    emails_checked: int
    processed: int
    verified: int
    changes_requested: int
    skipped: int
    skipped_reasons: list[str]
    errors: list[str]
    last_check_time_updated: bool
    timestamp: str
    check_window: dict[str, str] | None = None


def verify_cron_secret(authorization: str | None) -> bool:
    """Verify CRON_SECRET bearer token."""
    if not settings.cron_secret:
        logger.warning("cron_secret_not_configured")
        return False

    if not authorization:
        return False

    if not authorization.startswith("Bearer "):
        return False

    token = authorization[7:]  # Remove "Bearer " prefix
    return token == settings.cron_secret


def extract_submitter_email_from_body(body: str) -> str | None:
    """Extract submitter email from GitHub issue body.

    Looks for pattern: **Submitted by**: Name (email@example.com)
    """
    match = re.search(r"\*\*Submitted by\*\*:\s*[^(]+\s*\(([^)]+)\)", body)
    return match.group(1).strip() if match else None


@router.get("/email-monitor", response_model=EmailMonitorResult)
async def monitor_emails(
    db: DbSession,
    authorization: str | None = Header(None),
) -> EmailMonitorResult:
    """Poll for email replies and process feedback verification.

    This endpoint should be called by an external cron job every 5 minutes.
    Protected by CRON_SECRET bearer token.

    Processing flow:
    1. Verify CRON_SECRET bearer token
    2. Get last_check_time from EmailMonitorState
    3. Fetch unread emails since last_check_time
    4. Filter emails with subject containing [NPD]
    5. For each email:
       - Extract issue number from subject
       - Find matching Feedback record
       - Parse reply content (verified vs changes_requested)
       - Update feedback status
       - Create follow-up issue if changes requested
    6. Update last_check_time
    7. Return summary
    """
    # Verify cron secret
    if not verify_cron_secret(authorization):
        logger.warning("cron_unauthorized_request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing CRON_SECRET",
        )

    # Check if email is configured
    graph_service = GraphEmailService()
    if not graph_service.is_configured():
        logger.info("email_monitor_skipped_not_configured")
        return EmailMonitorResult(
            status="skipped",
            emails_checked=0,
            processed=0,
            verified=0,
            changes_requested=0,
            skipped=0,
            skipped_reasons=["Email monitoring not configured"],
            errors=[],
            last_check_time_updated=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

    # Check GitHub token
    if not settings.github_api_token:
        logger.warning("email_monitor_github_token_missing")
        return EmailMonitorResult(
            status="error",
            emails_checked=0,
            processed=0,
            verified=0,
            changes_requested=0,
            skipped=0,
            skipped_reasons=[],
            errors=["GITHUB_API_TOKEN not configured"],
            last_check_time_updated=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

    feedback_service = FeedbackService(db)

    # Get last check time
    previous_check_time = await feedback_service.get_last_check_time()
    new_check_time = datetime.now(UTC)

    logger.info(
        "email_monitor_starting",
        since=previous_check_time.isoformat(),
    )

    # Results tracking
    results = EmailMonitorResult(
        status="success",
        emails_checked=0,
        processed=0,
        verified=0,
        changes_requested=0,
        skipped=0,
        skipped_reasons=[],
        errors=[],
        last_check_time_updated=False,
        timestamp=new_check_time.isoformat(),
        check_window={
            "from": previous_check_time.isoformat(),
            "to": new_check_time.isoformat(),
        },
    )

    # Fetch new reply emails
    emails = await graph_service.fetch_new_replies(previous_check_time)
    results.emails_checked = len(emails)

    if not emails:
        logger.info("email_monitor_no_new_emails")
        await feedback_service.update_last_check_time(new_check_time)
        results.last_check_time_updated = True
        return results

    logger.info("email_monitor_found_emails", count=len(emails))

    # Process each email
    for email in emails:
        try:
            # Filter by [NPD] project marker
            project_marker = extract_project_marker(email.subject)
            if project_marker != NPD_PROJECT_MARKER:
                skip_reason = (
                    f"Email not for NPD project (marker: {project_marker or 'none'})"
                )
                logger.debug("email_monitor_skip_wrong_project", subject=email.subject)
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            # Extract issue number from subject
            issue_number = extract_issue_number(email.subject)
            if not issue_number:
                skip_reason = (
                    f"Could not extract issue number from: {email.subject[:50]}"
                )
                logger.debug(
                    "email_monitor_skip_no_issue_number", subject=email.subject
                )
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            # Find feedback record
            feedback = await feedback_service.get_by_issue_number(issue_number)
            if not feedback:
                skip_reason = f"No feedback record for issue #{issue_number}"
                logger.debug(
                    "email_monitor_skip_no_feedback", issue_number=issue_number
                )
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            # Check idempotency - skip if already processed this email
            if feedback.response_email_id == email.id:
                skip_reason = (
                    f"Email {email.id[:8]} already processed for issue #{issue_number}"
                )
                logger.debug("email_monitor_skip_already_processed", email_id=email.id)
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            # Only process replies for feedback in 'resolved' status
            if feedback.status != FeedbackStatus.RESOLVED:
                skip_reason = (
                    f"Feedback for issue #{issue_number} not in resolved status "
                    f"({feedback.status.value})"
                )
                logger.debug(
                    "email_monitor_skip_wrong_status", status=feedback.status.value
                )
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            # Verify sender matches submitter (fetch issue from GitHub)
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    response = await client.get(
                        f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/issues/{issue_number}",
                        headers={
                            "Authorization": f"token {settings.github_api_token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                    )
                    response.raise_for_status()
                    issue = response.json()
                except httpx.HTTPError:
                    skip_reason = f"Could not fetch issue #{issue_number} from GitHub"
                    results.skipped += 1
                    results.skipped_reasons.append(skip_reason)
                    continue

            # Verify issue is closed
            if issue.get("state") != "closed":
                skip_reason = (
                    f"Issue #{issue_number} is not closed "
                    f"(state: {issue.get('state')})"
                )
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            # Extract and verify submitter email
            submitter_email = extract_submitter_email_from_body(issue.get("body", ""))
            if not submitter_email:
                skip_reason = f"No submitter email in issue #{issue_number} body"
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            if submitter_email.lower() != email.from_address.lower():
                skip_reason = (
                    f"Email from {email.from_address} doesn't match submitter "
                    f"{submitter_email}"
                )
                logger.warning(
                    "email_monitor_sender_mismatch",
                    from_address=email.from_address,
                    submitter=submitter_email,
                )
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            logger.info(
                "email_monitor_processing",
                issue_number=issue_number,
                from_address=email.from_address,
            )

            # Parse the reply decision
            parse_result = parse_reply_decision(email.body)

            if not parse_result.action:
                skip_reason = (
                    f"Could not determine action from reply for issue #{issue_number}"
                )
                logger.info(
                    "email_monitor_ambiguous_reply",
                    issue_number=issue_number,
                    confidence=parse_result.confidence.value,
                )
                results.skipped += 1
                results.skipped_reasons.append(skip_reason)
                continue

            results.processed += 1

            if parse_result.action == ParseAction.VERIFIED:
                # Update feedback to verified
                await feedback_service.update_status(
                    feedback.id,
                    FeedbackStatus.VERIFIED,
                    response_received_at=email.received_at,
                    response_email_id=email.id,
                    response_content=parse_result.cleaned_body[:1000],
                )

                # Add comment to GitHub issue
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        comment_body = parse_result.cleaned_body[:200]
                        if len(parse_result.cleaned_body) > 200:
                            comment_body += "..."
                        await client.post(
                            f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/issues/{issue_number}/comments",
                            headers={
                                "Authorization": f"token {settings.github_api_token}",
                                "Accept": "application/vnd.github.v3+json",
                            },
                            json={
                                "body": (
                                    "**User Verified**: The submitter confirmed the "
                                    f"fix works.\n\n> {comment_body}"
                                )
                            },
                        )
                except Exception as e:
                    logger.warning("github_comment_failed", error=str(e))

                results.verified += 1
                logger.info("email_monitor_verified", issue_number=issue_number)

            elif parse_result.action == ParseAction.CHANGES_REQUESTED:
                # Determine issue type from labels
                labels = issue.get("labels", [])
                issue_type = (
                    "bug"
                    if any(label.get("name") == "bug" for label in labels)
                    else "enhancement"
                )

                # Create follow-up issue
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        follow_up_response = await client.post(
                            f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/issues",
                            headers={
                                "Authorization": f"token {settings.github_api_token}",
                                "Accept": "application/vnd.github.v3+json",
                            },
                            json={
                                "title": (
                                    f"[Follow-up] Re: #{issue_number} - "
                                    f"{issue.get('title', 'Unknown')}"
                                ),
                                "body": f"""## Submitter Information
**Project**: NovusProjectDatabase
**Submitted by**: {submitter_email.split('@')[0]} ({submitter_email})
**Submitted at**: {datetime.now(UTC).isoformat()}

---

## Follow-up to Issue #{issue_number}

**Original Issue**: {issue.get('html_url', '')}
**Original Title**: {issue.get('title', 'Unknown')}

### User Feedback
The submitter reports the fix did not fully resolve their issue:

> {parse_result.cleaned_body}

### Context
This follow-up was automatically created when the user replied to the resolution notification indicating additional changes are needed.

## Next Steps
- Review user feedback above
- Investigate what was missed in the original fix
- Implement additional changes as needed""",
                                "labels": [issue_type, "follow-up"],
                            },
                        )
                        follow_up_response.raise_for_status()
                        follow_up_data = follow_up_response.json()
                        follow_up_number = follow_up_data["number"]
                        follow_up_url = follow_up_data["html_url"]
                except httpx.HTTPError as e:
                    logger.error("follow_up_issue_creation_failed", error=str(e))
                    results.errors.append(
                        f"Failed to create follow-up for #{issue_number}"
                    )
                    continue

                # Update feedback to changes_requested
                await feedback_service.update_status(
                    feedback.id,
                    FeedbackStatus.CHANGES_REQUESTED,
                    response_received_at=email.received_at,
                    response_email_id=email.id,
                    response_content=parse_result.cleaned_body[:1000],
                    follow_up_issue_number=follow_up_number,
                    follow_up_issue_url=follow_up_url,
                )

                # Add comment to original issue
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        comment_body = parse_result.cleaned_body[:200]
                        if len(parse_result.cleaned_body) > 200:
                            comment_body += "..."
                        await client.post(
                            f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}/issues/{issue_number}/comments",
                            headers={
                                "Authorization": f"token {settings.github_api_token}",
                                "Accept": "application/vnd.github.v3+json",
                            },
                            json={
                                "body": (
                                    "**Changes Requested**: The submitter reported "
                                    "the fix didn't fully resolve their issue.\n\n"
                                    f"Follow-up issue created: #{follow_up_number}\n\n"
                                    f"> {comment_body}"
                                )
                            },
                        )
                except Exception as e:
                    logger.warning("github_comment_failed", error=str(e))

                results.changes_requested += 1
                logger.info(
                    "email_monitor_changes_requested",
                    issue_number=issue_number,
                    follow_up_number=follow_up_number,
                )

        except Exception as e:
            error_msg = f"Error processing email: {str(e)}"
            logger.error("email_monitor_processing_error", error=str(e))
            results.errors.append(error_msg)

    # Update last check time if processing was successful
    if not results.errors or results.processed > 0:
        await feedback_service.update_last_check_time(new_check_time)
        results.last_check_time_updated = True
    else:
        logger.warning("email_monitor_not_updating_check_time_all_errors")

    logger.info(
        "email_monitor_complete",
        processed=results.processed,
        verified=results.verified,
        changes_requested=results.changes_requested,
        skipped=results.skipped,
        errors=len(results.errors),
    )

    return results


@router.get("/sync-queue", response_model=SyncQueueProcessResult)
async def process_sync_queue_endpoint(
    authorization: str | None = Header(None),
) -> SyncQueueProcessResult:
    """Process pending sync queue items.

    This endpoint should be called by an external cron job every minute.
    Protected by CRON_SECRET bearer token.

    Processing flow:
    1. Verify CRON_SECRET bearer token
    2. Fetch pending queue items where next_retry <= now
    3. For each item:
       - Mark as in_progress
       - Execute sync operation
       - On success: mark as completed
       - On failure: increment attempts, calculate next_retry
       - If max_attempts reached: mark as failed
    4. Return summary

    Backoff schedule:
    - Attempt 1: Immediate (initial failure)
    - Attempt 2: +1 minute
    - Attempt 3: +5 minutes
    - Attempt 4: +15 minutes
    - Attempt 5: +60 minutes (max retries)
    """
    # Verify cron secret
    if not verify_cron_secret(authorization):
        logger.warning("cron_sync_queue_unauthorized")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing CRON_SECRET",
        )

    logger.info("cron_sync_queue_triggered")

    try:
        result = await process_sync_queue()
        return SyncQueueProcessResult(**result)
    except Exception as e:
        logger.exception("cron_sync_queue_error", error=str(e))
        return SyncQueueProcessResult(
            status="error",
            items_processed=0,
            items_succeeded=0,
            items_failed=0,
            items_requeued=0,
            items_max_retries=0,
            errors=[str(e)],
            timestamp=datetime.now(UTC).isoformat(),
        )


@router.get("/document-queue", response_model=DocumentQueueProcessResult)
async def process_document_queue_endpoint(
    authorization: str | None = Header(None),
) -> DocumentQueueProcessResult:
    """Process pending document queue items.

    This endpoint should be called by an external cron job every minute.
    Protected by CRON_SECRET bearer token.

    Processing flow:
    1. Verify CRON_SECRET bearer token
    2. Recover any stuck items (in_progress > 30 minutes)
    3. Fetch pending queue items where next_retry <= now
    4. For each item:
       - Mark as in_progress
       - Fetch document and file content
       - Execute document processing
       - On success: mark as completed
       - On failure:
         - If retryable error: requeue with exponential backoff
         - If non-retryable or max attempts: mark as failed
    5. Return summary

    Backoff schedule:
    - Attempt 1: Immediate
    - Attempt 2: +1 minute
    - Attempt 3: +5 minutes
    - Attempt 4: +15 minutes
    - Attempt 5: +60 minutes (max retries)
    """
    # Verify cron secret
    if not verify_cron_secret(authorization):
        logger.warning("cron_document_queue_unauthorized")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing CRON_SECRET",
        )

    logger.info("cron_document_queue_triggered")

    try:
        result = await process_document_queue()
        return DocumentQueueProcessResult(**result)
    except Exception as e:
        logger.exception("cron_document_queue_error", error=str(e))
        return DocumentQueueProcessResult(
            status="error",
            items_processed=0,
            items_succeeded=0,
            items_failed=0,
            errors=[str(e)],
            timestamp=datetime.now(UTC).isoformat(),
        )


class JiraRefreshResult(BaseModel):
    """Response schema for Jira refresh endpoint."""

    status: str
    total_links: int
    stale_links: int
    refreshed: int
    failed: int
    skipped: int
    errors: list[str]
    timestamp: str


@router.get("/jira-refresh", response_model=JiraRefreshResult)
async def process_jira_refresh_endpoint(
    authorization: str | None = Header(None),
) -> JiraRefreshResult:
    """Refresh all stale Jira link statuses.

    This endpoint should be called by an external cron job every hour.
    Protected by CRON_SECRET bearer token.

    Processing flow:
    1. Verify CRON_SECRET bearer token
    2. Fetch all Jira links with stale cache
    3. For each stale link:
       - Fetch current status from Jira API
       - Update cached_status, cached_summary, cached_at
    4. Return summary
    """
    # Verify cron secret
    if not verify_cron_secret(authorization):
        logger.warning("cron_jira_refresh_unauthorized")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing CRON_SECRET",
        )

    logger.info("cron_jira_refresh_triggered")

    try:
        result = await refresh_all_jira_statuses()
        return JiraRefreshResult(**result)
    except Exception as e:
        logger.exception("cron_jira_refresh_error", error=str(e))
        return JiraRefreshResult(
            status="error",
            total_links=0,
            stale_links=0,
            refreshed=0,
            failed=0,
            skipped=0,
            errors=[str(e)],
            timestamp=datetime.now(UTC).isoformat(),
        )


@router.get("/jobs", response_model=JobQueueProcessResult)
async def process_jobs_endpoint(
    authorization: str | None = Header(None),
    job_type: str | None = Query(None, description="Filter by job type"),
) -> JobQueueProcessResult:
    """Process pending background jobs.

    This endpoint should be called by an external cron job every minute.
    Protected by CRON_SECRET bearer token.

    Processing flow:
    1. Verify CRON_SECRET bearer token
    2. Recover any stuck jobs (in_progress > 30 minutes)
    3. Fetch pending jobs where next_retry <= now
    4. For each job:
       - Mark as in_progress
       - Execute registered handler
       - On success: mark as completed
       - On failure:
         - If retryable error: requeue with exponential backoff
         - If non-retryable or max attempts: mark as failed
    5. Return summary

    Backoff schedule:
    - Attempt 1: Immediate
    - Attempt 2: +1 minute
    - Attempt 3: +5 minutes
    - Attempt 4: +15 minutes
    - Attempt 5: +60 minutes (max retries)
    """
    # Verify cron secret
    if not verify_cron_secret(authorization):
        logger.warning("cron_jobs_unauthorized")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing CRON_SECRET",
        )

    logger.info("cron_jobs_triggered", job_type=job_type)

    try:
        # Import job handlers to register them
        import app.services.job_handlers  # noqa: F401
        from app.models.job import JobType
        from app.services.job_service import process_job_queue

        job_type_enum = None
        if job_type:
            try:
                job_type_enum = JobType(job_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid job_type: {job_type}. Valid types: {[t.value for t in JobType]}",
                )

        result = await process_job_queue(job_type=job_type_enum)
        return JobQueueProcessResult(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("cron_jobs_error", error=str(e))
        return JobQueueProcessResult(
            status="error",
            jobs_processed=0,
            jobs_succeeded=0,
            jobs_failed=0,
            jobs_requeued=0,
            jobs_max_retries=0,
            jobs_recovered=0,
            errors=[str(e)],
            timestamp=datetime.now(UTC).isoformat(),
        )
