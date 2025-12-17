"""Tests for auth endpoint rate limiting configuration."""

import inspect


class TestAuthRateLimitConfiguration:
    """Verify rate limiting is configured on auth endpoints."""

    def test_all_auth_endpoints_have_request_parameter(self):
        """All auth endpoints should accept Request for rate limiting."""
        from app.api.auth import (
            auth_callback,
            auth_debug,
            create_test_token,
            get_current_user_info,
            login,
            logout,
        )

        endpoints = [
            auth_debug,
            login,
            auth_callback,
            logout,
            get_current_user_info,
            create_test_token,
        ]

        for endpoint in endpoints:
            sig = inspect.signature(endpoint)
            param_names = list(sig.parameters.keys())
            assert (
                "request" in param_names
            ), f"{endpoint.__name__} missing request parameter"

    def test_auth_endpoints_have_rate_limit_decorator(self):
        """All auth endpoints should have @limiter.limit decorator."""
        from app.api.auth import (
            auth_callback,
            auth_debug,
            create_test_token,
            get_current_user_info,
            login,
            logout,
        )

        endpoints = [
            ("auth_debug", auth_debug),
            ("login", login),
            ("auth_callback", auth_callback),
            ("logout", logout),
            ("get_current_user_info", get_current_user_info),
            ("create_test_token", create_test_token),
        ]

        for name, _endpoint in endpoints:
            # Check that the endpoint has been wrapped by slowapi
            # slowapi stores decorated functions in limiter._Limiter__marked_for_limiting
            from app.core.rate_limit import limiter

            # The function should be in the marked_for_limiting dict
            full_name = f"app.api.auth.{name}"
            assert (
                full_name in limiter._Limiter__marked_for_limiting
            ), f"{name} is not rate limited - missing @limiter.limit decorator"

    def test_auth_limit_returns_correct_value(self):
        """auth_limit should return the configured rate limit."""
        from app.core.rate_limit import auth_limit

        limit = auth_limit()
        # Default is "20/minute" per config.py
        assert "/" in limit, "Rate limit should be in format 'N/period'"
        assert limit.split("/")[0].isdigit(), "Rate limit should start with a number"
