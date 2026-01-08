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


class TestTikaClientRetryLogic:
    """Tests for TikaClient retry behavior."""

    @pytest.fixture
    def client(self) -> TikaClient:
        """Create a client instance with fast retries for testing."""
        return TikaClient(max_retries=3, retry_delay=0.01)

    @pytest.mark.asyncio
    async def test_connection_error_retries_up_to_max(self, client: TikaClient):
        """Connection errors should retry max_retries times."""
        call_count = 0

        async def mock_put(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("Connection refused")

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            # Should have tried max_retries times
            assert call_count == 3
            assert result.result == ExtractionResult.ERROR
            assert "cannot connect" in result.message.lower()

    @pytest.mark.asyncio
    async def test_connection_error_succeeds_on_retry(self, client: TikaClient):
        """Connection errors should succeed if retry works."""
        call_count = 0

        async def mock_put(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            # Success on 3rd try
            response = MagicMock()
            response.status_code = 200
            response.text = "Extracted text"
            response.raise_for_status = MagicMock()
            return response

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            assert call_count == 3
            assert result.result == ExtractionResult.SUCCESS
            assert result.text == "Extracted text"

    @pytest.mark.asyncio
    async def test_5xx_error_retries(self, client: TikaClient):
        """5xx errors should trigger retry."""
        call_count = 0

        async def mock_put(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 500
            error = httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=response
            )
            raise error

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            # Should have tried max_retries times for 5xx
            assert call_count == 3
            assert result.result == ExtractionResult.ERROR
            assert "500" in result.message

    @pytest.mark.asyncio
    async def test_4xx_error_no_retry(self, client: TikaClient):
        """4xx errors should NOT retry."""
        call_count = 0

        async def mock_put(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.status_code = 400
            error = httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=response
            )
            raise error

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            # Should have tried only once for 4xx
            assert call_count == 1
            assert result.result == ExtractionResult.ERROR
            assert "400" in result.message

    @pytest.mark.asyncio
    async def test_timeout_no_retry(self, client: TikaClient):
        """Timeouts should NOT retry (indicates long processing)."""
        call_count = 0

        async def mock_put(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Request timed out")

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            # Should have tried only once for timeout
            assert call_count == 1
            assert result.result == ExtractionResult.ERROR
            assert "timed out" in result.message.lower()


class TestTikaClientHTTPStatusErrors:
    """Tests for specific HTTP status error handling."""

    @pytest.fixture
    def client(self) -> TikaClient:
        """Create a client instance."""
        return TikaClient()

    @pytest.mark.asyncio
    async def test_422_unprocessable_entity(self, client: TikaClient):
        """422 Unprocessable Entity should return error (corrupted file)."""

        async def mock_put(*args, **kwargs):
            response = MagicMock()
            response.status_code = 422
            error = httpx.HTTPStatusError(
                "Unprocessable Entity", request=MagicMock(), response=response
            )
            raise error

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"corrupted content", "application/msword", "corrupted.doc"
            )

            assert result.result == ExtractionResult.ERROR
            assert "422" in result.message

    @pytest.mark.asyncio
    async def test_500_internal_server_error(self, client: TikaClient):
        """500 Internal Server Error should return error after retries."""

        async def mock_put(*args, **kwargs):
            response = MagicMock()
            response.status_code = 500
            error = httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=response
            )
            raise error

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            assert result.result == ExtractionResult.ERROR
            assert "500" in result.message

    @pytest.mark.asyncio
    async def test_503_service_unavailable(self, client: TikaClient):
        """503 Service Unavailable should return error after retries."""

        async def mock_put(*args, **kwargs):
            response = MagicMock()
            response.status_code = 503
            error = httpx.HTTPStatusError(
                "Service Unavailable", request=MagicMock(), response=response
            )
            raise error

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
            mock_client.put = mock_put
            mock_client_class.return_value = mock_client

            result = await client.extract_text(
                b"test content", "application/msword", "test.doc"
            )

            assert result.result == ExtractionResult.ERROR
            assert "503" in result.message
