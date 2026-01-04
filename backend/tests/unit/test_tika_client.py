"""Tests for Tika client service."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import httpx
import pytest

from app.services.tika_client import (
    ExtractionResult,
    TikaClient,
)


class TestTikaClient:
    """Tests for TikaClient."""

    @pytest.fixture
    def client(self) -> TikaClient:
        """Create a client instance."""
        return TikaClient()

    def test_is_enabled_default_false(self, client: TikaClient):
        """By default, Tika should be disabled."""
        assert isinstance(client.is_enabled, bool)

    @pytest.mark.asyncio
    async def test_extract_text_disabled(self, client: TikaClient):
        """When disabled, extraction should return SKIPPED."""
        with patch.object(
            TikaClient, "is_enabled", new_callable=PropertyMock
        ) as mock_enabled:
            mock_enabled.return_value = False
            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )
            assert result.result == ExtractionResult.SKIPPED

    @pytest.mark.asyncio
    async def test_extract_text_success(self, client: TikaClient):
        """Successful extraction should return text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Extracted text content"
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(
                TikaClient, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_enabled.return_value = True
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            assert result.result == ExtractionResult.SUCCESS
            assert result.text == "Extracted text content"

    @pytest.mark.asyncio
    async def test_extract_text_timeout(self, client: TikaClient):
        """Timeout should return ERROR with message."""
        with (
            patch.object(
                TikaClient, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_enabled.return_value = True
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.put = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            assert result.result == ExtractionResult.ERROR
            assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_extract_text_connection_error(self, client: TikaClient):
        """Connection error should return ERROR with message."""
        with (
            patch.object(
                TikaClient, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_enabled.return_value = True
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.put = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            assert result.result == ExtractionResult.ERROR
            assert "cannot connect" in result.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_disabled(self, client: TikaClient):
        """Health check should return False when disabled."""
        with patch.object(
            TikaClient, "is_enabled", new_callable=PropertyMock
        ) as mock_enabled:
            mock_enabled.return_value = False
            result = await client.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_success(self, client: TikaClient):
        """Health check should return True when Tika responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch.object(
                TikaClient, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_enabled.return_value = True
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client: TikaClient):
        """Health check should return False on connection error."""
        with (
            patch.object(
                TikaClient, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_enabled.return_value = True
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_class.return_value = mock_client

            result = await client.health_check()
            assert result is False
