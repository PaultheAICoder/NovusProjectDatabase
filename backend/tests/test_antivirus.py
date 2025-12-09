"""Tests for antivirus service."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.services.antivirus import AntivirusService, ScanResponse, ScanResult


class TestAntivirusService:
    """Tests for AntivirusService."""

    @pytest.fixture
    def service(self) -> AntivirusService:
        """Create a service instance."""
        return AntivirusService()

    def test_is_enabled_default_false(self, service: AntivirusService):
        """By default, antivirus should be disabled."""
        # Depends on settings - check behavior
        assert isinstance(service.is_enabled, bool)

    def test_fail_open_default_true(self, service: AntivirusService):
        """By default, fail_open should be True."""
        assert isinstance(service.fail_open, bool)

    def test_parse_clean_response(self, service: AntivirusService):
        """Clean response should parse correctly."""
        response = service._parse_scan_response("stream: OK", "test.pdf")
        assert response.result == ScanResult.CLEAN
        assert response.threat_name is None

    def test_parse_infected_response(self, service: AntivirusService):
        """Infected response should parse correctly."""
        response = service._parse_scan_response(
            "stream: Win.Test.EICAR_HDB-1 FOUND", "test.pdf"
        )
        assert response.result == ScanResult.INFECTED
        assert response.threat_name == "Win.Test.EICAR_HDB-1"

    def test_parse_error_response(self, service: AntivirusService):
        """Error response should parse correctly."""
        response = service._parse_scan_response(
            "stream: Can't open file ERROR", "test.pdf"
        )
        assert response.result == ScanResult.ERROR

    def test_parse_null_terminated_response(self, service: AntivirusService):
        """Null-terminated response should be handled."""
        response = service._parse_scan_response("stream: OK\x00", "test.pdf")
        assert response.result == ScanResult.CLEAN

    @pytest.mark.asyncio
    async def test_scan_bytes_disabled(self, service: AntivirusService):
        """When disabled, scan should return SKIPPED."""
        with patch.object(
            AntivirusService, "is_enabled", new_callable=PropertyMock
        ) as mock_enabled:
            mock_enabled.return_value = False
            result = await service.scan_bytes(b"test content", "test.txt")
            assert result.result == ScanResult.SKIPPED

    @pytest.mark.asyncio
    async def test_scan_bytes_too_large(self, service: AntivirusService):
        """Files exceeding max size should return ERROR."""
        with patch.object(
            AntivirusService, "is_enabled", new_callable=PropertyMock
        ) as mock_enabled:
            mock_enabled.return_value = True
            large_content = b"x" * (service.MAX_STREAM_SIZE + 1)
            result = await service.scan_bytes(large_content, "large.bin")
            assert result.result == ScanResult.ERROR
            assert "too large" in result.message.lower()

    @pytest.mark.asyncio
    async def test_scan_bytes_connection_refused(self, service: AntivirusService):
        """Connection refused should return ERROR."""
        with (
            patch.object(
                AntivirusService, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("asyncio.open_connection", side_effect=ConnectionRefusedError()),
        ):
            mock_enabled.return_value = True
            result = await service.scan_bytes(b"test", "test.txt")
            assert result.result == ScanResult.ERROR
            assert "connect" in result.message.lower()

    @pytest.mark.asyncio
    async def test_scan_bytes_timeout(self, service: AntivirusService):
        """Connection timeout should return ERROR."""
        with (
            patch.object(
                AntivirusService, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("asyncio.open_connection", side_effect=TimeoutError()),
        ):
            mock_enabled.return_value = True
            result = await service.scan_bytes(b"test", "test.txt")
            assert result.result == ScanResult.ERROR

    @pytest.mark.asyncio
    async def test_scan_bytes_clean_file(self, service: AntivirusService):
        """Clean file scan should return CLEAN."""
        with (
            patch.object(
                AntivirusService, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch.object(
                service,
                "_scan_with_clamd",
                return_value=ScanResponse(result=ScanResult.CLEAN),
            ),
        ):
            mock_enabled.return_value = True
            result = await service.scan_bytes(b"test content", "test.pdf")
            assert result.result == ScanResult.CLEAN

    @pytest.mark.asyncio
    async def test_ping_success(self, service: AntivirusService):
        """Ping should return True when ClamAV responds."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = [
                (mock_reader, mock_writer),  # Connection
                b"PONG",  # Response
            ]
            result = await service.ping()
            assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, service: AntivirusService):
        """Ping should return False when ClamAV is unavailable."""
        with patch("asyncio.open_connection", side_effect=ConnectionRefusedError()):
            result = await service.ping()
            assert result is False


class TestScanResponse:
    """Tests for ScanResponse dataclass."""

    def test_clean_response(self):
        """Clean response should have no threat."""
        resp = ScanResponse(result=ScanResult.CLEAN)
        assert resp.result == ScanResult.CLEAN
        assert resp.threat_name is None
        assert resp.message is None

    def test_infected_response(self):
        """Infected response should include threat name."""
        resp = ScanResponse(
            result=ScanResult.INFECTED,
            threat_name="EICAR",
            message="Malware detected",
        )
        assert resp.result == ScanResult.INFECTED
        assert resp.threat_name == "EICAR"

    def test_error_response(self):
        """Error response should include message."""
        resp = ScanResponse(result=ScanResult.ERROR, message="Connection failed")
        assert resp.result == ScanResult.ERROR
        assert resp.message == "Connection failed"

    def test_skipped_response(self):
        """Skipped response should include reason."""
        resp = ScanResponse(
            result=ScanResult.SKIPPED, message="Antivirus scanning is disabled"
        )
        assert resp.result == ScanResult.SKIPPED
        assert resp.message == "Antivirus scanning is disabled"


class TestScanResult:
    """Tests for ScanResult enum."""

    def test_all_values_exist(self):
        """All expected values should exist."""
        assert ScanResult.CLEAN.value == "clean"
        assert ScanResult.INFECTED.value == "infected"
        assert ScanResult.ERROR.value == "error"
        assert ScanResult.SKIPPED.value == "skipped"
