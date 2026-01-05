"""Tests for generic caching service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache_service import (
    FallbackCache,
    InMemoryCache,
    RedisCache,
    get_or_set,
    reset_caches,
)


class TestInMemoryCache:
    """Tests for in-memory cache."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Cache should store and retrieve values."""
        cache = InMemoryCache(maxsize=10)
        data = {"key": "value", "count": 42}

        await cache.set("test_key", data)
        retrieved = await cache.get("test_key")

        assert retrieved == data

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Cache should return None for missing keys."""
        cache = InMemoryCache(maxsize=10)

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Cache should evict oldest entries when full."""
        cache = InMemoryCache(maxsize=2)

        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})
        await cache.set("key3", {"data": 3})

        # key1 should be evicted
        assert await cache.get("key1") is None
        assert await cache.get("key2") == {"data": 2}
        assert await cache.get("key3") == {"data": 3}

    @pytest.mark.asyncio
    async def test_cache_lru_access_order(self):
        """Accessing a key should move it to end of LRU order."""
        cache = InMemoryCache(maxsize=2)

        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})

        # Access key1 to move it to end
        await cache.get("key1")

        # Add key3 - should evict key2 (not key1)
        await cache.set("key3", {"data": 3})

        assert await cache.get("key1") == {"data": 1}
        assert await cache.get("key2") is None
        assert await cache.get("key3") == {"data": 3}

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Cache should delete specific keys."""
        cache = InMemoryCache(maxsize=10)

        await cache.set("key1", {"data": 1})
        await cache.set("key2", {"data": 2})

        deleted = await cache.delete("key1")

        assert deleted is True
        assert await cache.get("key1") is None
        assert await cache.get("key2") == {"data": 2}

    @pytest.mark.asyncio
    async def test_cache_delete_nonexistent(self):
        """Deleting nonexistent key should return False."""
        cache = InMemoryCache(maxsize=10)

        deleted = await cache.delete("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_cache_invalidate_prefix(self):
        """Cache should invalidate all entries matching prefix."""
        cache = InMemoryCache(maxsize=10)

        await cache.set("tags:list", {"data": 1})
        await cache.set("tags:flat", {"data": 2})
        await cache.set("orgs:list", {"data": 3})

        count = await cache.invalidate_prefix("tags:")

        assert count == 2
        assert await cache.get("tags:list") is None
        assert await cache.get("tags:flat") is None
        assert await cache.get("orgs:list") == {"data": 3}

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Cache should track hit/miss stats."""
        cache = InMemoryCache(maxsize=10)

        await cache.set("key1", {"data": 1})
        await cache.get("key1")  # hit
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss

        stats = cache.stats
        assert stats["type"] == "in_memory"
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == pytest.approx(66.67, rel=0.01)
        assert stats["size"] == 1
        assert stats["maxsize"] == 10

    @pytest.mark.asyncio
    async def test_cache_stats_empty(self):
        """Stats should handle zero requests gracefully."""
        cache = InMemoryCache(maxsize=10)

        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_percent"] == 0


class TestRedisCache:
    """Tests for Redis cache."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.delete = AsyncMock(return_value=1)
        mock.scan = AsyncMock(return_value=(0, []))
        return mock

    @pytest.mark.asyncio
    async def test_redis_cache_miss(self, mock_redis):
        """Redis cache should return None on miss."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis

        result = await cache.get("key1")

        assert result is None
        assert cache.stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_redis_cache_hit(self, mock_redis):
        """Redis cache should return data on hit."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        data = {"items": [], "total": 0}
        mock_redis.get.return_value = json.dumps(data)

        result = await cache.get("key1")

        assert result == data
        assert cache.stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_redis_cache_set_with_default_ttl(self, mock_redis):
        """Redis cache should set with default TTL."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        data = {"items": [], "total": 0}

        await cache.set("key1", data)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == "test:key1"  # Prefixed key
        assert call_args[1] == 300  # Default TTL

    @pytest.mark.asyncio
    async def test_redis_cache_set_with_custom_ttl(self, mock_redis):
        """Redis cache should respect custom TTL."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        data = {"items": [], "total": 0}

        await cache.set("key1", data, ttl=600)

        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 600  # Custom TTL

    @pytest.mark.asyncio
    async def test_redis_cache_delete(self, mock_redis):
        """Redis cache should delete keys."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis

        deleted = await cache.delete("key1")

        assert deleted is True
        mock_redis.delete.assert_called_once_with("test:key1")

    @pytest.mark.asyncio
    async def test_redis_cache_invalidate_all(self, mock_redis):
        """Redis cache should delete all matching keys."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        mock_redis.scan.return_value = (0, ["test:key1", "test:key2"])

        count = await cache.invalidate_prefix("test:")

        mock_redis.delete.assert_called_once()
        assert count == 2

    @pytest.mark.asyncio
    async def test_redis_error_handling_on_get(self, mock_redis):
        """Redis cache should handle errors gracefully on get."""
        from redis.exceptions import RedisError

        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        mock_redis.get.side_effect = RedisError("Connection failed")

        result = await cache.get("key1")

        assert result is None
        assert cache.stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_redis_error_handling_on_set(self, mock_redis):
        """Redis cache should handle errors gracefully on set."""
        from redis.exceptions import RedisError

        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        mock_redis.setex.side_effect = RedisError("Connection failed")

        # Should not raise exception
        await cache.set("key1", {"data": 1})

    @pytest.mark.asyncio
    async def test_redis_stats(self, mock_redis):
        """Redis cache should provide stats."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
            default_ttl=300,
        )
        cache._client = mock_redis
        mock_redis.get.return_value = json.dumps({"data": 1})

        await cache.get("key1")  # hit

        stats = cache.stats
        assert stats["type"] == "redis"
        assert stats["prefix"] == "test:"
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["ttl_seconds"] == 300


class TestFallbackCache:
    """Tests for fallback cache."""

    @pytest.mark.asyncio
    async def test_uses_redis_when_available(self):
        """Should use Redis when available."""
        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"data": 1}))
        mock_redis.stats = {"type": "redis", "hits": 1, "misses": 0}
        cache._redis_cache._client = mock_redis

        result = await cache.get("key1")

        assert result == {"data": 1}

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_error(self):
        """Should fallback to memory on Redis error."""
        from redis.exceptions import RedisError

        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )

        # Mock the redis cache's get method directly to trigger fallback in FallbackCache
        mock_redis_cache = AsyncMock()
        mock_redis_cache.get = AsyncMock(side_effect=RedisError("Redis down"))
        cache._redis_cache = mock_redis_cache

        # Pre-populate memory cache
        await cache._memory_cache.set("key1", {"data": 1})

        result = await cache.get("key1")

        assert result == {"data": 1}
        assert cache._using_fallback is True

    @pytest.mark.asyncio
    async def test_memory_only_when_no_redis(self):
        """Should use memory cache when no Redis configured."""
        cache = FallbackCache(redis_url=None, prefix="test:")

        await cache.set("key1", {"data": 1})
        result = await cache.get("key1")

        assert result == {"data": 1}
        assert cache._redis_cache is None

    @pytest.mark.asyncio
    async def test_set_stores_in_both_caches(self):
        """Should store in both memory and Redis."""
        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        cache._redis_cache._client = mock_redis

        await cache.set("key1", {"data": 1})

        # Check memory cache
        memory_result = await cache._memory_cache.get("key1")
        assert memory_result == {"data": 1}

        # Check Redis was called
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_show_redis_when_active(self):
        """Stats should show Redis info when active."""
        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )

        cache._redis_cache._hits = 5
        cache._redis_cache._misses = 2

        stats = cache.stats
        assert stats["type"] == "redis"
        assert stats["fallback_active"] is False
        assert stats["hits"] == 5

    @pytest.mark.asyncio
    async def test_stats_show_fallback_when_active(self):
        """Stats should indicate fallback status when Redis fails."""
        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )
        cache._using_fallback = True

        stats = cache.stats
        assert stats["type"] == "in_memory"
        assert stats["fallback_active"] is True
        assert stats["redis_configured"] is True

    @pytest.mark.asyncio
    async def test_invalidate_prefix_both_caches(self):
        """Should invalidate in both memory and Redis."""
        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )

        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, ["test:key1", "test:key2"]))
        mock_redis.delete = AsyncMock()
        cache._redis_cache._client = mock_redis

        # Pre-populate memory cache
        await cache._memory_cache.set("test:key1", {"data": 1})
        await cache._memory_cache.set("test:key2", {"data": 2})

        count = await cache.invalidate_prefix("test:")

        assert count == 2
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_from_both_caches(self):
        """Should delete from both memory and Redis."""
        cache = FallbackCache(
            redis_url="redis://localhost:6379/0",
            prefix="test:",
        )

        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)
        cache._redis_cache._client = mock_redis

        # Pre-populate memory cache
        await cache._memory_cache.set("key1", {"data": 1})

        deleted = await cache.delete("key1")

        assert deleted is True
        mock_redis.delete.assert_called_once()
        assert await cache._memory_cache.get("key1") is None


class TestGetOrSet:
    """Tests for cache-aside helper."""

    @pytest.mark.asyncio
    async def test_returns_cached_value(self):
        """Should return cached value without calling factory."""
        cache = FallbackCache(redis_url=None)
        await cache.set("key1", {"data": "cached"})

        factory_called = False

        async def factory():
            nonlocal factory_called
            factory_called = True
            return {"data": "fresh"}

        result = await get_or_set(cache, "key1", factory)

        assert result == {"data": "cached"}
        assert factory_called is False

    @pytest.mark.asyncio
    async def test_calls_factory_on_miss(self):
        """Should call factory when key not in cache."""
        cache = FallbackCache(redis_url=None)

        factory_called = False

        async def factory():
            nonlocal factory_called
            factory_called = True
            return {"data": "fresh"}

        result = await get_or_set(cache, "key1", factory)

        assert result == {"data": "fresh"}
        assert factory_called is True

    @pytest.mark.asyncio
    async def test_caches_factory_result(self):
        """Should cache the result from factory."""
        cache = FallbackCache(redis_url=None)

        async def factory():
            return {"data": "fresh"}

        await get_or_set(cache, "key1", factory)

        # Verify it's cached
        cached = await cache.get("key1")
        assert cached == {"data": "fresh"}

    @pytest.mark.asyncio
    async def test_uses_custom_ttl(self):
        """Should pass custom TTL to cache."""
        cache = FallbackCache(redis_url=None)

        async def factory():
            return {"data": "fresh"}

        # Just ensure it doesn't error - TTL is ignored for in-memory
        result = await get_or_set(cache, "key1", factory, ttl=600)
        assert result == {"data": "fresh"}


class TestCacheFactoryFunctions:
    """Tests for cache factory functions."""

    def teardown_method(self):
        """Reset caches after each test."""
        reset_caches()

    @pytest.mark.asyncio
    async def test_get_tag_cache_creates_singleton(self):
        """get_tag_cache should return same instance."""
        from app.services.cache_service import get_tag_cache

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                tag_cache_ttl=3600,
            )

            cache1 = get_tag_cache()
            cache2 = get_tag_cache()

            assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_get_org_cache_creates_singleton(self):
        """get_org_cache should return same instance."""
        from app.services.cache_service import get_org_cache

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                org_cache_ttl=900,
            )

            cache1 = get_org_cache()
            cache2 = get_org_cache()

            assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_get_dashboard_cache_creates_singleton(self):
        """get_dashboard_cache should return same instance."""
        from app.services.cache_service import get_dashboard_cache

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                dashboard_cache_ttl=300,
            )

            cache1 = get_dashboard_cache()
            cache2 = get_dashboard_cache()

            assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_invalidate_tag_cache(self):
        """invalidate_tag_cache should clear tag cache."""
        from app.services.cache_service import get_tag_cache, invalidate_tag_cache

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                tag_cache_ttl=3600,
            )

            cache = get_tag_cache()
            await cache.set("tags:test", {"data": 1})

            count = await invalidate_tag_cache()

            assert count == 1
            assert await cache.get("tags:test") is None

    @pytest.mark.asyncio
    async def test_invalidate_org_cache(self):
        """invalidate_org_cache should clear org cache."""
        from app.services.cache_service import get_org_cache, invalidate_org_cache

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                org_cache_ttl=900,
            )

            cache = get_org_cache()
            await cache.set("orgs:test", {"data": 1})

            count = await invalidate_org_cache()

            assert count == 1
            assert await cache.get("orgs:test") is None

    @pytest.mark.asyncio
    async def test_invalidate_dashboard_cache(self):
        """invalidate_dashboard_cache should clear dashboard cache."""
        from app.services.cache_service import (
            get_dashboard_cache,
            invalidate_dashboard_cache,
        )

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                dashboard_cache_ttl=300,
            )

            cache = get_dashboard_cache()
            await cache.set("dash:test", {"data": 1})

            count = await invalidate_dashboard_cache()

            assert count == 1
            assert await cache.get("dash:test") is None

    def test_reset_caches_clears_all(self):
        """reset_caches should clear all cache instances."""
        from app.services.cache_service import (
            get_dashboard_cache,
            get_org_cache,
            get_tag_cache,
            reset_caches,
        )

        with patch("app.services.cache_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                is_redis_configured=False,
                tag_cache_ttl=3600,
                org_cache_ttl=900,
                dashboard_cache_ttl=300,
            )

            # Create caches
            get_tag_cache()
            get_org_cache()
            get_dashboard_cache()

            # Reset
            reset_caches()

            # Import module-level variables to check they're None
            import app.services.cache_service as cs

            assert cs._tag_cache is None
            assert cs._org_cache is None
            assert cs._dashboard_cache is None
