"""Email reply parsing service for feedback verification workflow.

Parses feedback reply emails to determine user intent:
- "verified" - User confirms the fix works
- "changes_requested" - User needs additional changes
"""

import re
from dataclasses import dataclass
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class ParseAction(str, Enum):
    """Parsed action from email reply."""

    VERIFIED = "verified"
    CHANGES_REQUESTED = "changes_requested"


class ParseConfidence(str, Enum):
    """Confidence level of parsing."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Keywords indicating verification (fix works)
VERIFY_KEYWORDS = [
    "verified",
    "looks good",
    "works",
    "fixed",
    "confirmed",
    "approved",
    "great",
    "perfect",
    "thank you",
    "thanks",
    "all good",
    "working now",
    "issue resolved",
    "problem solved",
]

# Keywords indicating changes needed (fix incomplete)
CHANGE_KEYWORDS = [
    "changes needed",
    "not working",
    "still broken",
    "issue remains",
    "problem persists",
    "needs more work",
    "doesn't work",
    "does not work",
    "still not",
    "still having",
    "not fixed",
    "still see",
    "same issue",
    "same problem",
    "different issue",
    "another issue",
]


@dataclass
class ParseResult:
    """Result of parsing an email reply."""

    action: ParseAction | None
    keyword: str | None
    cleaned_body: str
    confidence: ParseConfidence


def clean_email_body(body: str) -> str:
    """Clean email body by removing quoted text, signatures, and HTML."""
    # Remove HTML tags if present
    cleaned = re.sub(r"<[^>]*>", "", body)

    # Decode common HTML entities
    html_entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
    }
    for entity, char in html_entities.items():
        cleaned = cleaned.replace(entity, char)

    lines = cleaned.split("\n")
    cleaned_lines: list[str] = []

    for line in lines:
        trimmed = line.strip()

        # Skip empty lines
        if not trimmed:
            continue

        # Stop at signature delimiters
        if trimmed in ["--", "---", "____", "====", "___"]:
            break

        # Skip quoted lines (email replies)
        if trimmed.startswith(">"):
            continue

        # Skip email client headers (stop processing at these)
        if re.match(
            r"^(On .+ wrote:|From:|Sent:|To:|Subject:|Date:)", trimmed, re.IGNORECASE
        ):
            break

        # Skip "Sent from" signatures
        if re.match(r"^Sent from ", trimmed, re.IGNORECASE):
            break

        # Skip app signatures
        if re.match(r"^Get (Outlook|Gmail|Yahoo)", trimmed, re.IGNORECASE):
            break

        # Skip confidentiality notices
        if re.match(
            r"^(This email|This message|CONFIDENTIAL|NOTICE:|DISCLAIMER)",
            trimmed,
            re.IGNORECASE,
        ):
            break

        cleaned_lines.append(trimmed)

        # Stop after collecting enough content
        if len(cleaned_lines) >= 10:
            break

    return " ".join(cleaned_lines)


def _find_keyword(text: str, keywords: list[str]) -> str | None:
    """Find keyword in text with word boundary matching."""
    text_lower = text.lower()

    for keyword in keywords:
        # Escape special regex characters and create word boundary pattern
        escaped = re.escape(keyword)
        pattern = rf"\b{escaped}\b"

        if re.search(pattern, text_lower, re.IGNORECASE):
            return keyword

    return None


def parse_reply_decision(email_body: str) -> ParseResult:
    """Parse email body for verification or change request.

    Args:
        email_body: Raw email body (may contain HTML)

    Returns:
        ParseResult with detected action and cleaned body
    """
    cleaned_body = clean_email_body(email_body)

    # Handle empty body
    if not cleaned_body.strip():
        return ParseResult(
            action=None,
            keyword=None,
            cleaned_body=cleaned_body,
            confidence=ParseConfidence.LOW,
        )

    verify_keyword = _find_keyword(cleaned_body, VERIFY_KEYWORDS)
    change_keyword = _find_keyword(cleaned_body, CHANGE_KEYWORDS)

    # Handle ambiguous case (both types of keywords found)
    if verify_keyword and change_keyword:
        logger.warning(
            "ambiguous_email_reply",
            verify_keyword=verify_keyword,
            change_keyword=change_keyword,
        )
        # Give priority to change keywords (safer to re-open than miss an issue)
        return ParseResult(
            action=ParseAction.CHANGES_REQUESTED,
            keyword=change_keyword,
            cleaned_body=cleaned_body,
            confidence=ParseConfidence.LOW,
        )

    if verify_keyword:
        return ParseResult(
            action=ParseAction.VERIFIED,
            keyword=verify_keyword,
            cleaned_body=cleaned_body,
            confidence=ParseConfidence.HIGH,
        )

    if change_keyword:
        return ParseResult(
            action=ParseAction.CHANGES_REQUESTED,
            keyword=change_keyword,
            cleaned_body=cleaned_body,
            confidence=ParseConfidence.HIGH,
        )

    # No clear keywords found
    return ParseResult(
        action=None,
        keyword=None,
        cleaned_body=cleaned_body,
        confidence=ParseConfidence.LOW,
    )


def extract_issue_number(subject: str) -> int | None:
    """Extract issue number from email subject.

    Looks for patterns like:
    - "Re: [Resolved] Your Bug Report #123"
    - "RE: Your Feature Request #456"
    - "#789"
    """
    match = re.search(r"#(\d+)", subject)
    if match:
        return int(match.group(1))
    return None


def is_reply_email(subject: str) -> bool:
    """Check if an email appears to be a reply."""
    subject_lower = subject.lower().strip()
    return subject_lower.startswith("re:")


def extract_project_marker(subject: str) -> str | None:
    """Extract project marker from email subject.

    Looks for patterns like [NPD], [SKU], etc.
    """
    match = re.search(r"\[([A-Z]{2,10})\]", subject)
    if match:
        return match.group(1)
    return None
