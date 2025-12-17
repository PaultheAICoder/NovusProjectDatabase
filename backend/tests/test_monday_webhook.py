"""Tests for Monday.com webhook endpoint."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest


class TestMondayWebhookChallenge:
    """Tests for Monday.com webhook challenge verification."""

    @pytest.mark.asyncio
    async def test_challenge_echoes_token(self):
        """Challenge verification should echo the token back."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        # Create mock request
        challenge_payload = {"challenge": "test_challenge_token_123"}
        mock_request = MagicMock(spec=Request)
        mock_request.body = AsyncMock(
            return_value=json.dumps(challenge_payload).encode()
        )
        mock_request.json = AsyncMock(return_value=challenge_payload)

        result = await handle_monday_webhook(mock_request, authorization=None)

        assert result.challenge == "test_challenge_token_123"

    @pytest.mark.asyncio
    async def test_challenge_with_long_token(self):
        """Challenge verification should handle long tokens."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        long_token = "a" * 256
        challenge_payload = {"challenge": long_token}
        mock_request = MagicMock(spec=Request)
        mock_request.body = AsyncMock(
            return_value=json.dumps(challenge_payload).encode()
        )
        mock_request.json = AsyncMock(return_value=challenge_payload)

        result = await handle_monday_webhook(mock_request, authorization=None)

        assert result.challenge == long_token


class TestMondayWebhookSignature:
    """Tests for Monday.com webhook JWT verification."""

    def test_valid_jwt_signature(self):
        """Valid JWT signature should pass verification."""
        from app.api.webhooks import verify_monday_signature

        secret = "test-webhook-secret"

        # Create a valid JWT
        token = jwt.encode(
            {"iat": datetime.utcnow(), "exp": datetime.utcnow() + timedelta(hours=1)},
            secret,
            algorithm="HS256",
        )

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = secret
            result = verify_monday_signature(f"Bearer {token}")

        assert result is True

    def test_valid_jwt_without_bearer_prefix(self):
        """JWT without Bearer prefix should still verify."""
        from app.api.webhooks import verify_monday_signature

        secret = "test-webhook-secret"
        token = jwt.encode(
            {"iat": datetime.utcnow()},
            secret,
            algorithm="HS256",
        )

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = secret
            result = verify_monday_signature(token)

        assert result is True

    def test_invalid_jwt_signature(self):
        """Invalid JWT signature should fail verification."""
        from app.api.webhooks import verify_monday_signature

        # Create JWT with wrong secret
        token = jwt.encode(
            {"iat": datetime.utcnow()},
            "wrong-secret",
            algorithm="HS256",
        )

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = "correct-secret"
            result = verify_monday_signature(f"Bearer {token}")

        assert result is False

    def test_expired_jwt(self):
        """Expired JWT should fail verification."""
        from app.api.webhooks import verify_monday_signature

        secret = "test-webhook-secret"
        token = jwt.encode(
            {
                "iat": datetime.utcnow() - timedelta(hours=2),
                "exp": datetime.utcnow() - timedelta(hours=1),
            },
            secret,
            algorithm="HS256",
        )

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = secret
            result = verify_monday_signature(f"Bearer {token}")

        assert result is False

    def test_missing_token(self):
        """Missing token should fail verification."""
        from app.api.webhooks import verify_monday_signature

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = "test-secret"
            result = verify_monday_signature(None)

        assert result is False

    def test_empty_token(self):
        """Empty token should fail verification."""
        from app.api.webhooks import verify_monday_signature

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = "test-secret"
            result = verify_monday_signature("")

        assert result is False

    def test_missing_secret(self):
        """Missing webhook secret should fail verification."""
        from app.api.webhooks import verify_monday_signature

        token = "some.jwt.token"

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = ""
            result = verify_monday_signature(token)

        assert result is False

    def test_malformed_jwt(self):
        """Malformed JWT should fail verification."""
        from app.api.webhooks import verify_monday_signature

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_secret = "test-secret"
            result = verify_monday_signature("not.a.valid.jwt.token")

        assert result is False


class TestMondayWebhookHealthEndpoint:
    """Tests for GET /api/v1/webhooks/monday."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        """Health endpoint should return ok status."""
        from app.api.webhooks import monday_webhook_health

        result = await monday_webhook_health()

        assert result["status"] == "ok"
        assert result["service"] == "monday-webhook"


class TestMondayWebhookPayloadParsing:
    """Tests for webhook payload parsing."""

    def test_create_item_event_schema(self):
        """Create item event should parse correctly."""
        from app.schemas.monday import MondayWebhookPayload

        payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "pulseName": "New Contact",
                "boardId": "11111111",
                "groupId": "topics",
                "groupName": "Group 1",
                "triggerUuid": "abc-123-def",
            }
        }

        result = MondayWebhookPayload(**payload)

        assert result.event.type == "create_item"
        assert result.event.pulseId == "12345678"
        assert result.event.pulseName == "New Contact"
        assert result.event.boardId == "11111111"

    def test_change_column_value_event_schema(self):
        """Change column value event should parse correctly."""
        from app.schemas.monday import MondayWebhookPayload

        payload = {
            "event": {
                "type": "change_column_value",
                "pulseId": "12345678",
                "pulseName": "Contact Name",
                "boardId": "11111111",
                "columnId": "email",
                "columnType": "email",
                "columnTitle": "Email",
                "value": {"email": "new@example.com", "text": "new@example.com"},
                "previousValue": {
                    "email": "old@example.com",
                    "text": "old@example.com",
                },
            }
        }

        result = MondayWebhookPayload(**payload)

        assert result.event.type == "change_column_value"
        assert result.event.columnId == "email"
        assert result.event.value is not None

    def test_item_deleted_event_schema(self):
        """Item deleted event should parse correctly."""
        from app.schemas.monday import MondayWebhookPayload

        payload = {
            "event": {
                "type": "item_deleted",
                "pulseId": "12345678",
                "boardId": "11111111",
            }
        }

        result = MondayWebhookPayload(**payload)

        assert result.event.type == "item_deleted"
        assert result.event.pulseId == "12345678"

    def test_extra_fields_allowed(self):
        """Unknown fields should not cause parsing errors."""
        from app.schemas.monday import MondayWebhookPayload

        payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "11111111",
                "unknownField": "should be ignored",
                "anotherUnknown": {"nested": "value"},
            },
            "extraTopLevel": "also ignored",
        }

        # Should not raise
        result = MondayWebhookPayload(**payload)
        assert result.event.type == "create_item"

    def test_minimal_event_payload(self):
        """Minimal payload with only required fields should parse."""
        from app.schemas.monday import MondayWebhookPayload

        payload = {
            "event": {
                "type": "unknown_event",
            }
        }

        result = MondayWebhookPayload(**payload)
        assert result.event.type == "unknown_event"


class TestMondayWebhookEndpointIntegration:
    """Integration tests for the webhook POST endpoint."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self):
        """Invalid JSON should return 400 Bad Request."""
        from fastapi import HTTPException, Request

        from app.api.webhooks import handle_monday_webhook

        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        with pytest.raises(HTTPException) as exc_info:
            await handle_monday_webhook(mock_request, authorization=None)

        assert exc_info.value.status_code == 400
        assert "Invalid JSON payload" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_event_without_secret_logs_warning(self):
        """Event processing without secret configured should log warning."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        event_payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "11111111",
            }
        }
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value=event_payload)

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_enabled = True
            mock_settings.monday_webhook_secret = ""
            mock_settings.monday_contacts_board_id = ""
            mock_settings.monday_organizations_board_id = ""

            result = await handle_monday_webhook(mock_request, authorization=None)

        assert result["status"] == "received"
        assert result["event_type"] == "create_item"

    @pytest.mark.asyncio
    async def test_disabled_webhook_returns_ignored(self):
        """Disabled webhook should return ignored status."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        event_payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "11111111",
            }
        }
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value=event_payload)

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_enabled = False

            result = await handle_monday_webhook(mock_request, authorization=None)

        assert result["status"] == "ignored"
        assert result["reason"] == "webhook processing disabled"

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self):
        """Invalid signature with secret configured should return 401."""
        from fastapi import HTTPException, Request

        from app.api.webhooks import handle_monday_webhook

        event_payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "11111111",
            }
        }
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value=event_payload)

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_enabled = True
            mock_settings.monday_webhook_secret = "test-secret"

            with pytest.raises(HTTPException) as exc_info:
                await handle_monday_webhook(
                    mock_request, authorization="Bearer invalid"
                )

        assert exc_info.value.status_code == 401
        assert "Invalid webhook signature" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_board_type_contacts_identified(self):
        """Contacts board should be identified correctly."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        event_payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "contacts_board_123",
            }
        }
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value=event_payload)

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_enabled = True
            mock_settings.monday_webhook_secret = ""
            mock_settings.monday_contacts_board_id = "contacts_board_123"
            mock_settings.monday_organizations_board_id = "orgs_board_456"

            result = await handle_monday_webhook(mock_request, authorization=None)

        assert result["board_type"] == "contacts"

    @pytest.mark.asyncio
    async def test_board_type_organizations_identified(self):
        """Organizations board should be identified correctly."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        event_payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "orgs_board_456",
            }
        }
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value=event_payload)

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_enabled = True
            mock_settings.monday_webhook_secret = ""
            mock_settings.monday_contacts_board_id = "contacts_board_123"
            mock_settings.monday_organizations_board_id = "orgs_board_456"

            result = await handle_monday_webhook(mock_request, authorization=None)

        assert result["board_type"] == "organizations"

    @pytest.mark.asyncio
    async def test_unknown_board_type(self):
        """Unknown board should return 'unknown' board type."""
        from fastapi import Request

        from app.api.webhooks import handle_monday_webhook

        event_payload = {
            "event": {
                "type": "create_item",
                "pulseId": "12345678",
                "boardId": "unknown_board_789",
            }
        }
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value=event_payload)

        with patch("app.api.webhooks.settings") as mock_settings:
            mock_settings.monday_webhook_enabled = True
            mock_settings.monday_webhook_secret = ""
            mock_settings.monday_contacts_board_id = "contacts_board_123"
            mock_settings.monday_organizations_board_id = "orgs_board_456"

            result = await handle_monday_webhook(mock_request, authorization=None)

        assert result["board_type"] == "unknown"
