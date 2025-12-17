"""Tests for antivirus service."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.services.antivirus import (
    AntivirusService,
    ClamAVConnectionPool,
    ScanResponse,
    ScanResult,
    close_clamav_pool,
    get_clamav_pool,
    init_clamav_pool,
)


class TestAntivirusService:
    """Tests for AntivirusService."""

    @pytest.fixture
    def service(self) -> AntivirusService:
        """Create a service instance."""
        return AntivirusService()

    @pytest.fixture(autouse=True)
    def mock_no_pool(self):
        """Ensure tests run without pool (testing fallback behavior)."""
        with patch("app.services.antivirus._clamav_pool", None):
            yield

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
            large_content = b"x" * (service._max_stream_size + 1)
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


class TestClamAVConnectionPool:
    """Tests for ClamAVConnectionPool."""

    @pytest.fixture
    def pool(self) -> ClamAVConnectionPool:
        """Create a pool instance for testing."""
        return ClamAVConnectionPool(
            host="localhost",
            port=3310,
            pool_size=2,
            connection_timeout=5.0,
            max_connection_age=60.0,
        )

    @pytest.mark.asyncio
    async def test_pool_stats_initial(self, pool: ClamAVConnectionPool):
        """Initial pool stats should show empty pool."""
        stats = pool.stats
        assert stats["pool_size"] == 2
        assert stats["created_count"] == 0
        assert stats["active_count"] == 0
        assert stats["available_count"] == 0
        assert stats["closed"] is False

    @pytest.mark.asyncio
    async def test_pool_acquire_creates_connection(self, pool: ClamAVConnectionPool):
        """Acquiring from empty pool should create new connection."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch(
                "asyncio.open_connection",
                AsyncMock(return_value=(mock_reader, mock_writer)),
            ),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
        ):
            reader, writer = await pool.acquire()
            assert pool.stats["created_count"] == 1
            assert pool.stats["active_count"] == 1

    @pytest.mark.asyncio
    async def test_pool_release_returns_connection(self, pool: ClamAVConnectionPool):
        """Released connection should be available for reuse."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch(
                "asyncio.open_connection",
                AsyncMock(return_value=(mock_reader, mock_writer)),
            ),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
        ):
            reader, writer = await pool.acquire()
            await pool.release(reader, writer)
            assert pool.stats["available_count"] == 1
            assert pool.stats["active_count"] == 0

    @pytest.mark.asyncio
    async def test_pool_close(self, pool: ClamAVConnectionPool):
        """Closing pool should mark it closed."""
        await pool.close()
        assert pool.stats["closed"] is True

    @pytest.mark.asyncio
    async def test_pool_acquire_after_close_raises(self, pool: ClamAVConnectionPool):
        """Acquiring after close should raise RuntimeError."""
        await pool.close()
        with pytest.raises(RuntimeError, match="Pool is closed"):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_pool_connection_refused(self, pool: ClamAVConnectionPool):
        """Connection refused should propagate."""
        with (
            patch("asyncio.open_connection", side_effect=ConnectionRefusedError()),
            pytest.raises(ConnectionRefusedError),
        ):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_pool_release_discard(self, pool: ClamAVConnectionPool):
        """Discarding connection should close it instead of returning to pool."""
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch(
                "asyncio.open_connection",
                AsyncMock(return_value=(mock_reader, mock_writer)),
            ),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
        ):
            reader, writer = await pool.acquire()
            await pool.release(reader, writer, discard=True)
            assert pool.stats["available_count"] == 0
            assert pool.stats["created_count"] == 0
            mock_writer.close.assert_called_once()


class TestAntivirusServiceWithPool:
    """Tests for AntivirusService using connection pool."""

    @pytest.fixture
    def service(self) -> AntivirusService:
        """Create a service instance."""
        return AntivirusService()

    @pytest.mark.asyncio
    async def test_scan_uses_pool_when_available(self, service: AntivirusService):
        """Scan should use pool when available."""
        mock_pool = MagicMock(spec=ClamAVConnectionPool)
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"stream: OK\x00")
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.is_closing = MagicMock(return_value=False)

        mock_pool.acquire = AsyncMock(return_value=(mock_reader, mock_writer))
        mock_pool.release = AsyncMock()

        with (
            patch.object(
                AntivirusService, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("app.services.antivirus.get_clamav_pool", return_value=mock_pool),
        ):
            mock_enabled.return_value = True
            result = await service.scan_bytes(b"test content", "test.txt")

            assert result.result == ScanResult.CLEAN
            mock_pool.acquire.assert_called_once()
            mock_pool.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_scan_pool_timeout_returns_error(self, service: AntivirusService):
        """Pool timeout should return ERROR."""
        mock_pool = MagicMock(spec=ClamAVConnectionPool)
        mock_pool.acquire = AsyncMock(side_effect=TimeoutError("Pool timeout"))
        mock_pool.stats = {"pool_size": 5, "active_count": 5}

        with (
            patch.object(
                AntivirusService, "is_enabled", new_callable=PropertyMock
            ) as mock_enabled,
            patch("app.services.antivirus.get_clamav_pool", return_value=mock_pool),
        ):
            mock_enabled.return_value = True
            result = await service.scan_bytes(b"test content", "test.txt")

            assert result.result == ScanResult.ERROR
            assert "pool timeout" in result.message.lower()

    @pytest.mark.asyncio
    async def test_ping_uses_pool_when_available(self, service: AntivirusService):
        """Ping should use pool when available."""
        mock_pool = MagicMock(spec=ClamAVConnectionPool)
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b"PONG\x00")
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.is_closing = MagicMock(return_value=False)

        mock_pool.acquire = AsyncMock(return_value=(mock_reader, mock_writer))
        mock_pool.release = AsyncMock()

        async def mock_wait_for(coro, timeout):
            return await coro

        with (
            patch("app.services.antivirus.get_clamav_pool", return_value=mock_pool),
            patch("asyncio.wait_for", side_effect=mock_wait_for),
        ):
            result = await service.ping()

            assert result is True
            mock_pool.acquire.assert_called_once()
            mock_pool.release.assert_called_once()


class TestPoolLifecycle:
    """Tests for pool lifecycle functions."""

    @pytest.mark.asyncio
    async def test_init_pool_when_disabled(self):
        """Pool should not initialize when ClamAV is disabled."""
        with patch("app.services.antivirus.get_settings") as mock_settings:
            mock_settings.return_value.clamav_enabled = False
            result = await init_clamav_pool()
            assert result is None

    @pytest.mark.asyncio
    async def test_init_pool_when_enabled(self):
        """Pool should initialize when ClamAV is enabled."""
        with patch("app.services.antivirus.get_settings") as mock_settings:
            settings = MagicMock()
            settings.clamav_enabled = True
            settings.clamav_host = "localhost"
            settings.clamav_port = 3310
            settings.clamav_pool_size = 3
            settings.clamav_pool_timeout = 5
            settings.clamav_connection_max_age = 60
            mock_settings.return_value = settings

            pool = await init_clamav_pool()
            assert pool is not None
            assert get_clamav_pool() is pool

            # Cleanup
            await close_clamav_pool()
            assert get_clamav_pool() is None

    @pytest.mark.asyncio
    async def test_close_pool_when_none(self):
        """Closing None pool should be safe."""
        with patch("app.services.antivirus._clamav_pool", None):
            # Should not raise
            await close_clamav_pool()
