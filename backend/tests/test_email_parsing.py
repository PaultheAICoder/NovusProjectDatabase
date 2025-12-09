"""Tests for email parsing service."""

from app.services.email_parsing import (
    ParseAction,
    ParseConfidence,
    clean_email_body,
    extract_issue_number,
    extract_project_marker,
    is_reply_email,
    parse_reply_decision,
)


class TestCleanEmailBody:
    """Tests for email body cleaning."""

    def test_removes_html_tags(self):
        """HTML tags should be stripped."""
        body = "<p>Hello <strong>World</strong></p>"
        cleaned = clean_email_body(body)
        assert "<p>" not in cleaned
        assert "<strong>" not in cleaned
        assert "Hello" in cleaned
        assert "World" in cleaned

    def test_decodes_html_entities(self):
        """HTML entities should be decoded."""
        body = "&amp; &lt; &gt; &quot; &#39; &nbsp;"
        cleaned = clean_email_body(body)
        assert "&" in cleaned
        assert "<" in cleaned
        assert ">" in cleaned

    def test_removes_quoted_lines(self):
        """Lines starting with > should be removed."""
        body = "My reply\n> Original message\n> More original"
        cleaned = clean_email_body(body)
        assert "My reply" in cleaned
        assert "Original message" not in cleaned

    def test_stops_at_signature_delimiter(self):
        """Content after -- should be excluded."""
        body = "My message\n--\nJohn Doe\nCompany Inc"
        cleaned = clean_email_body(body)
        assert "My message" in cleaned
        assert "John Doe" not in cleaned

    def test_stops_at_email_headers(self):
        """Content after 'On ... wrote:' should be excluded."""
        body = "Thanks!\nOn Dec 9, 2025 at 10:00 AM, John wrote:\nOriginal message"
        cleaned = clean_email_body(body)
        assert "Thanks" in cleaned
        assert "Original message" not in cleaned

    def test_stops_at_sent_from(self):
        """Content after 'Sent from' should be excluded."""
        body = "My reply\nSent from my iPhone"
        cleaned = clean_email_body(body)
        assert "My reply" in cleaned
        assert "iPhone" not in cleaned


class TestParseReplyDecision:
    """Tests for parsing email replies."""

    def test_detects_verified(self):
        """Verified keywords should be detected."""
        result = parse_reply_decision("Thanks, looks good!")
        assert result.action == ParseAction.VERIFIED
        assert result.keyword == "looks good"
        assert result.confidence == ParseConfidence.HIGH

    def test_detects_verified_variants(self):
        """Various verified keywords should work."""
        for body in ["verified", "fixed", "works", "approved", "thanks"]:
            result = parse_reply_decision(f"This is {body}!")
            assert result.action == ParseAction.VERIFIED

    def test_detects_changes_requested(self):
        """Change request keywords should be detected."""
        result = parse_reply_decision("Still not working for me")
        assert result.action == ParseAction.CHANGES_REQUESTED
        assert result.keyword == "not working"
        assert result.confidence == ParseConfidence.HIGH

    def test_detects_changes_variants(self):
        """Various change keywords should work."""
        for body in ["still broken", "not fixed", "needs more work"]:
            result = parse_reply_decision(f"The issue is {body}")
            assert result.action == ParseAction.CHANGES_REQUESTED

    def test_ambiguous_prefers_changes(self):
        """Ambiguous emails should prefer changes_requested."""
        result = parse_reply_decision("Thanks but still not working")
        assert result.action == ParseAction.CHANGES_REQUESTED
        assert result.confidence == ParseConfidence.LOW

    def test_no_keywords_returns_null(self):
        """Email without keywords should return null action."""
        result = parse_reply_decision("I got your email about the update")
        assert result.action is None
        assert result.confidence == ParseConfidence.LOW

    def test_empty_body(self):
        """Empty body should be handled gracefully."""
        result = parse_reply_decision("")
        assert result.action is None
        assert result.confidence == ParseConfidence.LOW


class TestExtractIssueNumber:
    """Tests for issue number extraction."""

    def test_extracts_from_subject(self):
        """Issue number should be extracted from subject."""
        assert extract_issue_number("Re: Your Bug Report #123") == 123
        assert extract_issue_number("RE: Feature Request #456 resolved") == 456

    def test_no_issue_number(self):
        """Missing issue number should return None."""
        assert extract_issue_number("Re: Hello") is None
        assert extract_issue_number("Thanks for your email") is None


class TestExtractProjectMarker:
    """Tests for project marker extraction."""

    def test_extracts_npd(self):
        """[NPD] marker should be extracted."""
        assert extract_project_marker("Re: Bug Report [NPD] - Issue #123") == "NPD"

    def test_extracts_sku(self):
        """[SKU] marker should be extracted."""
        assert extract_project_marker("Re: [SKU] Feature Request") == "SKU"

    def test_no_marker(self):
        """Missing marker should return None."""
        assert extract_project_marker("Re: Bug Report #123") is None


class TestIsReplyEmail:
    """Tests for reply detection."""

    def test_detects_re_prefix(self):
        """Re: prefix should indicate reply."""
        assert is_reply_email("Re: Hello") is True
        assert is_reply_email("RE: Hello") is True
        assert is_reply_email("re: Hello") is True

    def test_not_reply(self):
        """Non-reply subjects should return False."""
        assert is_reply_email("Hello") is False
        assert is_reply_email("Request: Info") is False
