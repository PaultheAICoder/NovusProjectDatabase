"""Tests for search result caching service."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.search_cache import (
    FallbackSearchCache,
    InMemorySearchCache,
    RedisSearchCache,
    generate_cache_key,
)


class TestGenerateCacheKey:
    """Tests for cache key generation."""

    def test_generates_consistent_key(self):
        """Same parameters should generate same key."""
        key1 = generate_cache_key(
            query="test",
            status=["active"],
            organization_id="123",
            tag_ids=["a", "b"],
            owner_id="456",
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        key2 = generate_cache_key(
            query="test",
            status=["active"],
            organization_id="123",
            tag_ids=["a", "b"],
            owner_id="456",
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        assert key1 == key2

    def test_different_params_different_key(self):
        """Different parameters should generate different keys."""
        key1 = generate_cache_key(
            query="test1",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        key2 = generate_cache_key(
            query="test2",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        assert key1 != key2

    def test_normalizes_query_case(self):
        """Query should be case-insensitive."""
        key1 = generate_cache_key(
            query="TEST",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        key2 = generate_cache_key(
            query="test",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        assert key1 == key2

    def test_sorts_list_parameters(self):
        """List parameters should be sorted for consistency."""
        key1 = generate_cache_key(
            query="test",
            status=["b", "a"],
            organization_id=None,
            tag_ids=["z", "a"],
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        key2 = generate_cache_key(
            query="test",
            status=["a", "b"],
            organization_id=None,
            tag_ids=["a", "z"],
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        assert key1 == key2

    def test_page_affects_key(self):
        """Different pages should have different keys."""
        key1 = generate_cache_key(
            query="test",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=1,
            page_size=20,
        )
        key2 = generate_cache_key(
            query="test",
            status=None,
            organization_id=None,
            tag_ids=None,
            owner_id=None,
            sort_by="relevance",
            sort_order="desc",
            page=2,
            page_size=20,
        )
        assert key1 != key2


class TestInMemorySearchCache:
    """Tests for in-memory search cache."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Cache should store and retrieve results."""
        cache = InMemorySearchCache(maxsize=10)
        results = {"items": [], "total": 0}

        await cache.set("key1", results)
        retrieved = await cache.get("key1")

        assert retrieved == results

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Cache should return None for missing keys."""
        cache = InMemorySearchCache(maxsize=10)

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Cache should evict oldest entries when full."""
        cache = InMemorySearchCache(maxsize=2)

        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})
        await cache.set("key3", {"data": 3})

        assert await cache.get("key1") is None
        assert await cache.get("key2") == {"data": 2}
        assert await cache.get("key3") == {"data": 3}

    @pytest.mark.asyncio
    async def test_cache_invalidate_all(self):
        """Invalidate should clear all entries."""
        cache = InMemorySearchCache(maxsize=10)

        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})

        count = await cache.invalidate_all()

        assert count == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Cache should track hit/miss stats."""
        cache = InMemorySearchCache(maxsize=10)

        await cache.set("key1", {"data": 1})
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0


class TestRedisSearchCache:
    """Tests for Redis search cache."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.scan = AsyncMock(return_value=(0, []))
        mock.delete = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_redis_cache_miss(self, mock_redis):
        """Redis cache should return None on miss."""
        cache = RedisSearchCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=300,
        )
        cache._client = mock_redis

        result = await cache.get("key1")

        assert result is None
        assert cache.stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_redis_cache_hit(self, mock_redis):
        """Redis cache should return data on hit."""
        cache = RedisSearchCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=300,
        )
        cache._client = mock_redis
        data = {"items": [], "total": 0}
        mock_redis.get.return_value = json.dumps(data)

        result = await cache.get("key1")

        assert result == data
        assert cache.stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_redis_cache_set_with_ttl(self, mock_redis):
        """Redis cache should set with correct TTL."""
        cache = RedisSearchCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=300,
        )
        cache._client = mock_redis
        data = {"items": [], "total": 0}

        await cache.set("key1", data)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 300  # TTL

    @pytest.mark.asyncio
    async def test_redis_cache_invalidate_all(self, mock_redis):
        """Redis cache should delete all matching keys."""
        cache = RedisSearchCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=300,
        )
        cache._client = mock_redis
        mock_redis.scan.return_value = (0, ["search:key1", "search:key2"])

        count = await cache.invalidate_all()

        mock_redis.delete.assert_called_once()
        assert count == 2

    @pytest.mark.asyncio
    async def test_redis_error_handling(self, mock_redis):
        """Redis cache should handle errors gracefully."""
        from redis.exceptions import RedisError

        cache = RedisSearchCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=300,
        )
        cache._client = mock_redis
        mock_redis.get.side_effect = RedisError("Connection failed")

        result = await cache.get("key1")

        assert result is None
        assert cache.stats["misses"] == 1


class TestFallbackSearchCache:
    """Tests for fallback search cache."""

    @pytest.mark.asyncio
    async def test_uses_redis_when_available(self):
        """Should use Redis when available."""
        cache = FallbackSearchCache(
            redis_url="redis://localhost:6379/0",
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value={"data": 1})
        mock_redis.stats = {"type": "redis", "hits": 1, "misses": 0}
        cache._redis_cache = mock_redis

        result = await cache.get("key1")

        assert result == {"data": 1}
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_error(self):
        """Should fallback to memory on Redis error."""
        cache = FallbackSearchCache(
            redis_url="redis://localhost:6379/0",
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        cache._redis_cache = mock_redis

        await cache._memory_cache.set("key1", {"data": 1})

        result = await cache.get("key1")

        assert result == {"data": 1}
        assert cache._using_fallback is True

    @pytest.mark.asyncio
    async def test_memory_only_when_no_redis(self):
        """Should use memory cache when no Redis configured."""
        cache = FallbackSearchCache(redis_url=None)

        await cache.set("key1", {"data": 1})
        result = await cache.get("key1")

        assert result == {"data": 1}
        assert cache._redis_cache is None

    @pytest.mark.asyncio
    async def test_stats_show_fallback_status(self):
        """Stats should indicate fallback status."""
        cache = FallbackSearchCache(
            redis_url="redis://localhost:6379/0",
        )

        cache._redis_cache = MagicMock()
        cache._redis_cache.stats = {
            "type": "redis",
            "hits": 0,
            "misses": 0,
            "hit_rate_percent": 0,
            "ttl_seconds": 300,
        }

        stats = cache.stats
        assert stats["fallback_active"] is False

        cache._using_fallback = True
        stats = cache.stats
        assert stats["fallback_active"] is True
