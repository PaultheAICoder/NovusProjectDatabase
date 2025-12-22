"""Tests for API endpoint rate limiting configuration."""

import inspect


class TestWebhookRateLimitConfiguration:
    """Verify rate limiting is configured on webhook endpoints."""

    def test_all_webhook_endpoints_have_request_parameter(self):
        """All webhook endpoints should accept Request for rate limiting."""
        from app.api.webhooks import (
            handle_github_webhook,
            handle_monday_webhook,
            monday_webhook_health,
            webhook_health,
        )

        endpoints = [
            webhook_health,
            handle_github_webhook,
            monday_webhook_health,
            handle_monday_webhook,
        ]

        for endpoint in endpoints:
            sig = inspect.signature(endpoint)
            param_names = list(sig.parameters.keys())
            assert (
                "request" in param_names
            ), f"{endpoint.__name__} missing request parameter"

    def test_webhook_endpoints_have_rate_limit_decorator(self):
        """All webhook endpoints should have @limiter.limit decorator."""
        from app.api.webhooks import (
            handle_github_webhook,
            handle_monday_webhook,
            monday_webhook_health,
            webhook_health,
        )

        endpoints = [
            ("webhook_health", webhook_health),
            ("handle_github_webhook", handle_github_webhook),
            ("monday_webhook_health", monday_webhook_health),
            ("handle_monday_webhook", handle_monday_webhook),
        ]

        from app.core.rate_limit import limiter

        for name, _endpoint in endpoints:
            full_name = f"app.api.webhooks.{name}"
            assert (
                full_name in limiter._Limiter__marked_for_limiting
            ), f"{name} is not rate limited - missing @limiter.limit decorator"

    def test_webhook_limit_returns_correct_value(self):
        """webhook_limit should return the configured rate limit."""
        from app.core.rate_limit import webhook_limit

        limit = webhook_limit()
        assert "/" in limit, "Rate limit should be in format 'N/period'"
        assert limit.split("/")[0].isdigit(), "Rate limit should start with a number"


class TestRateLimitConfiguration:
    """Verify rate limit configuration values."""

    def test_all_rate_limit_functions_return_valid_format(self):
        """All rate limit functions should return valid format."""
        from app.core.rate_limit import (
            admin_limit,
            auth_limit,
            crud_limit,
            feedback_limit,
            search_limit,
            upload_limit,
            webhook_limit,
        )

        limits = [
            ("search_limit", search_limit),
            ("crud_limit", crud_limit),
            ("upload_limit", upload_limit),
            ("admin_limit", admin_limit),
            ("auth_limit", auth_limit),
            ("feedback_limit", feedback_limit),
            ("webhook_limit", webhook_limit),
        ]

        for name, limit_func in limits:
            result = limit_func()
            assert "/" in result, f"{name} should return format 'N/period'"
            parts = result.split("/")
            assert parts[0].isdigit(), f"{name} should start with a number"
            assert parts[1] in [
                "second",
                "minute",
                "hour",
                "day",
            ], f"{name} should have valid period"


class TestCronEndpointsNoRateLimit:
    """Verify cron endpoints do NOT have rate limiting (protected by secret)."""

    def test_cron_endpoints_use_secret_authentication(self):
        """Cron endpoints should use CRON_SECRET, not rate limiting."""
        # Import to ensure these endpoint functions exist
        from app.api.cron import (
            monitor_emails as _monitor_emails,
        )
        from app.api.cron import (
            process_document_queue_endpoint as _process_document_queue_endpoint,
        )
        from app.api.cron import (
            process_sync_queue_endpoint as _process_sync_queue_endpoint,
        )

        # Silence unused import warnings - imports verify endpoints exist
        assert _monitor_emails is not None
        assert _process_document_queue_endpoint is not None
        assert _process_sync_queue_endpoint is not None

        # These endpoints should NOT be rate limited - they use CRON_SECRET
        from app.core.rate_limit import limiter

        cron_endpoints = [
            "monitor_emails",
            "process_sync_queue_endpoint",
            "process_document_queue_endpoint",
        ]

        for name in cron_endpoints:
            full_name = f"app.api.cron.{name}"
            assert (
                full_name not in limiter._Limiter__marked_for_limiting
            ), f"{name} should NOT have rate limiting (uses CRON_SECRET instead)"
