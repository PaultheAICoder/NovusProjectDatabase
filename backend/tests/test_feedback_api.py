"""Tests for feedback API endpoints."""

from unittest.mock import patch

import pytest


class TestFeedbackClarifyEndpoint:
    """Tests for POST /api/v1/feedback/clarify."""

    @pytest.mark.asyncio
    async def test_clarify_returns_three_questions(self):
        """Clarify endpoint should return exactly 3 questions."""
        # Test will use fallback questions when AI not configured
        from app.services.ai_enhancement import AIEnhancementService

        service = AIEnhancementService()
        result = await service.generate_clarifying_questions(
            feedback_type="bug",
            description="The login button is not working on the homepage",
        )

        assert len(result.questions) == 3
        assert all(isinstance(q, str) for q in result.questions)

    @pytest.mark.asyncio
    async def test_clarify_different_questions_for_bug_vs_feature(self):
        """Bug and feature requests should get different questions."""
        from app.services.ai_enhancement import AIEnhancementService

        service = AIEnhancementService()

        bug_result = await service.generate_clarifying_questions(
            feedback_type="bug",
            description="Something is broken",
        )

        feature_result = await service.generate_clarifying_questions(
            feedback_type="feature",
            description="I want a new feature",
        )

        # Fallback questions are different for bug vs feature
        assert bug_result.questions != feature_result.questions


class TestFeedbackSubmitEndpoint:
    """Tests for POST /api/v1/feedback."""

    @pytest.mark.asyncio
    async def test_enhance_issue_returns_title_and_body(self):
        """AI enhancement should return title and body."""
        from app.services.ai_enhancement import AIEnhancementService

        service = AIEnhancementService()
        result = await service.enhance_issue(
            feedback_type="bug",
            description="Login button broken",
            answers=["Chrome 120", "Expected to log in", "Yesterday"],
        )

        assert result.title
        assert result.body
        assert len(result.title) <= 80

    @pytest.mark.asyncio
    async def test_fallback_issue_format(self):
        """Fallback formatting should produce valid issue body."""
        from app.services.ai_enhancement import AIEnhancementService

        service = AIEnhancementService()
        result = service._format_fallback_issue(
            feedback_type="bug",
            description="Test bug description",
            answers=["Answer 1", "Answer 2", "Answer 3"],
        )

        assert "Reported Issue" in result.body
        assert "Test bug description" in result.body
        assert result.title == "Test bug description"


class TestGitHubWebhookSignature:
    """Tests for webhook signature verification."""

    def test_valid_signature(self):
        """Valid HMAC signature should pass verification."""
        import hashlib
        import hmac

        from app.api.webhooks import verify_github_signature

        secret = "test-webhook-secret"
        payload = b'{"action": "closed"}'

        # Compute expected signature
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.github_webhook_secret = secret
            result = verify_github_signature(payload, f"sha256={expected}")

        assert result is True

    def test_invalid_signature(self):
        """Invalid signature should fail verification."""
        from app.api.webhooks import verify_github_signature

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.github_webhook_secret = "test-secret"
            result = verify_github_signature(b"payload", "sha256=invalid")

        assert result is False

    def test_missing_signature(self):
        """Missing signature should fail verification."""
        from app.api.webhooks import verify_github_signature

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.github_webhook_secret = "test-secret"
            result = verify_github_signature(b"payload", None)

        assert result is False

    def test_missing_secret(self):
        """Missing webhook secret should fail verification."""
        from app.api.webhooks import verify_github_signature

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.github_webhook_secret = ""
            result = verify_github_signature(b"payload", "sha256=something")

        assert result is False


class TestWebhookHealthEndpoint:
    """Tests for GET /api/v1/webhooks/github."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        """Health endpoint should return ok status."""
        from app.api.webhooks import webhook_health

        result = await webhook_health()

        assert result["status"] == "ok"
        assert result["service"] == "github-webhook"
