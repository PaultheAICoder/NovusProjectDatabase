"""Tests for embedding service and embedding cache."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_service import (
    EmbeddingCache,
    EmbeddingService,
    FallbackEmbeddingCache,
    InMemoryEmbeddingCache,
    RedisEmbeddingCache,
)


class TestInMemoryEmbeddingCache:
    """Tests for the InMemoryEmbeddingCache class."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Cache should store and retrieve embeddings correctly."""
        cache = InMemoryEmbeddingCache(maxsize=10)
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        await cache.set("test query", embedding)
        result = await cache.get("test query")

        assert result == embedding

    @pytest.mark.asyncio
    async def test_cache_returns_none_for_missing_key(self):
        """Cache should return None for keys not in cache."""
        cache = InMemoryEmbeddingCache(maxsize=10)

        result = await cache.get("nonexistent query")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_normalized_keys(self):
        """Cache should normalize keys (lowercase, stripped whitespace)."""
        cache = InMemoryEmbeddingCache(maxsize=10)
        embedding = [0.1, 0.2, 0.3]

        # Set with lowercase
        await cache.set("test", embedding)

        # Get with various cases and whitespace - should all match
        assert await cache.get("TEST") == embedding
        assert await cache.get("Test") == embedding
        assert await cache.get("  test  ") == embedding
        assert await cache.get("  TEST  ") == embedding

    @pytest.mark.asyncio
    async def test_cache_different_queries_different_embeddings(self):
        """Different queries should have different embeddings."""
        cache = InMemoryEmbeddingCache(maxsize=10)
        embedding1 = [0.1, 0.2, 0.3]
        embedding2 = [0.4, 0.5, 0.6]

        await cache.set("query one", embedding1)
        await cache.set("query two", embedding2)

        assert await cache.get("query one") == embedding1
        assert await cache.get("query two") == embedding2
        result_one = await cache.get("query one")
        result_two = await cache.get("query two")
        assert result_one != result_two

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Cache should evict oldest entries when maxsize is reached."""
        cache = InMemoryEmbeddingCache(maxsize=2)

        await cache.set("first", [0.1])
        await cache.set("second", [0.2])
        await cache.set("third", [0.3])  # Should evict "first"

        assert await cache.get("first") is None
        assert await cache.get("second") == [0.2]
        assert await cache.get("third") == [0.3]

    @pytest.mark.asyncio
    async def test_cache_access_updates_lru_order(self):
        """Accessing a cache entry should move it to the end of the LRU queue."""
        cache = InMemoryEmbeddingCache(maxsize=2)

        await cache.set("first", [0.1])
        await cache.set("second", [0.2])

        # Access "first" to move it to the end
        await cache.get("first")

        # Add "third" - should evict "second" (now oldest)
        await cache.set("third", [0.3])

        assert await cache.get("first") == [0.1]
        assert await cache.get("second") is None
        assert await cache.get("third") == [0.3]

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Cache should track hits and misses correctly."""
        cache = InMemoryEmbeddingCache(maxsize=10)

        # Initial stats
        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0
        assert stats["type"] == "in_memory"

        # Add an entry
        await cache.set("test", [0.1, 0.2])
        assert cache.stats["size"] == 1

        # Miss
        await cache.get("nonexistent")
        assert cache.stats["misses"] == 1
        assert cache.stats["hits"] == 0

        # Hit
        await cache.get("test")
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 1

        # Check hit rate
        assert cache.stats["hit_rate_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_cache_update_existing_key(self):
        """Updating an existing key should replace the value."""
        cache = InMemoryEmbeddingCache(maxsize=10)

        await cache.set("test", [0.1, 0.2])
        await cache.set("test", [0.3, 0.4])

        assert await cache.get("test") == [0.3, 0.4]
        assert cache.stats["size"] == 1  # Still only one entry


class TestRedisEmbeddingCache:
    """Tests for RedisEmbeddingCache class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock()
        mock.ping = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_redis_cache_get_miss(self, mock_redis):
        """Redis cache should return None on miss."""
        cache = RedisEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
        )
        cache._client = mock_redis
        mock_redis.get.return_value = None

        result = await cache.get("test query")

        assert result is None
        assert cache.stats["misses"] == 1
        assert cache.stats["hits"] == 0

    @pytest.mark.asyncio
    async def test_redis_cache_get_hit(self, mock_redis):
        """Redis cache should return embedding on hit."""
        cache = RedisEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
        )
        cache._client = mock_redis
        embedding = [0.1, 0.2, 0.3]
        mock_redis.get.return_value = json.dumps(embedding)

        result = await cache.get("test query")

        assert result == embedding
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_redis_cache_set_with_ttl(self, mock_redis):
        """Redis cache should set with TTL."""
        ttl = 7200
        cache = RedisEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=ttl,
        )
        cache._client = mock_redis
        embedding = [0.1, 0.2, 0.3]

        await cache.set("test query", embedding)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == ttl  # TTL argument
        assert json.loads(call_args[0][2]) == embedding

    @pytest.mark.asyncio
    async def test_redis_cache_error_handling(self, mock_redis):
        """Redis cache should handle errors gracefully."""
        from redis.exceptions import RedisError

        cache = RedisEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
        )
        cache._client = mock_redis
        mock_redis.get.side_effect = RedisError("Connection failed")

        result = await cache.get("test query")

        assert result is None
        assert cache.stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_redis_cache_stats(self, mock_redis):
        """Redis cache should track stats correctly."""
        cache = RedisEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
        )
        cache._client = mock_redis
        mock_redis.get.return_value = json.dumps([0.1, 0.2])

        # Get a hit
        await cache.get("test")

        stats = cache.stats
        assert stats["type"] == "redis"
        assert stats["hits"] == 1
        assert stats["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_redis_cache_key_normalization(self, mock_redis):
        """Redis cache should normalize and prefix keys."""
        cache = RedisEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
            prefix="test:",
        )
        cache._client = mock_redis
        mock_redis.get.return_value = None

        await cache.get("  TEST Query  ")

        # Should be called with normalized, prefixed key
        mock_redis.get.assert_called_with("test:test query")


class TestFallbackEmbeddingCache:
    """Tests for FallbackEmbeddingCache class."""

    @pytest.mark.asyncio
    async def test_fallback_uses_redis_when_available(self):
        """Should use Redis when available."""
        cache = FallbackEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            maxsize=100,
        )

        # Mock the redis cache
        mock_redis_cache = AsyncMock()
        mock_redis_cache.get = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_redis_cache.stats = {"type": "redis", "hits": 1, "misses": 0}
        cache._redis_cache = mock_redis_cache

        result = await cache.get("test")

        assert result == [0.1, 0.2, 0.3]
        mock_redis_cache.get.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_redis_error(self):
        """Should fall back to memory cache on Redis error."""
        cache = FallbackEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            maxsize=100,
        )

        # Mock redis cache to raise an error
        mock_redis_cache = AsyncMock()
        mock_redis_cache.get = AsyncMock(side_effect=Exception("Redis down"))
        cache._redis_cache = mock_redis_cache

        # Pre-populate memory cache
        await cache._memory_cache.set("test", [0.4, 0.5, 0.6])

        result = await cache.get("test")

        assert result == [0.4, 0.5, 0.6]
        assert cache._using_fallback is True

    @pytest.mark.asyncio
    async def test_fallback_stats_show_fallback_status(self):
        """Stats should indicate when fallback is active."""
        cache = FallbackEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            maxsize=100,
        )

        # Initially, fallback should not be active
        cache._redis_cache = AsyncMock()
        cache._redis_cache.stats = {
            "type": "redis",
            "hits": 0,
            "misses": 0,
            "hit_rate_percent": 0,
            "ttl_seconds": 86400,
        }
        stats = cache.stats
        assert stats["fallback_active"] is False

        # After triggering fallback
        cache._using_fallback = True
        stats = cache.stats
        assert stats["fallback_active"] is True
        assert stats["redis_configured"] is True

    @pytest.mark.asyncio
    async def test_memory_cache_used_when_no_redis(self):
        """Memory cache should be used when no Redis is configured."""
        cache = FallbackEmbeddingCache(
            redis_url=None,
            maxsize=100,
        )

        # Should have no Redis cache
        assert cache._redis_cache is None

        # Should use memory cache
        embedding = [0.1, 0.2, 0.3]
        await cache.set("test", embedding)
        result = await cache.get("test")

        assert result == embedding

    @pytest.mark.asyncio
    async def test_set_stores_in_both_caches(self):
        """Set should store in both Redis and memory caches."""
        cache = FallbackEmbeddingCache(
            redis_url="redis://localhost:6379/0",
            maxsize=100,
        )

        # Mock redis cache
        mock_redis_cache = AsyncMock()
        mock_redis_cache.set = AsyncMock()
        cache._redis_cache = mock_redis_cache

        embedding = [0.1, 0.2, 0.3]
        await cache.set("test", embedding)

        # Both should have been called
        mock_redis_cache.set.assert_called_once_with("test", embedding)
        # Memory cache should also have the value
        result = await cache._memory_cache.get("test")
        assert result == embedding


class TestEmbeddingServiceCaching:
    """Tests for EmbeddingService caching behavior."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx AsyncClient."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        return mock_client

    @pytest.mark.asyncio
    async def test_embedding_service_caches_results(self, mock_httpx_client):
        """EmbeddingService should cache embedding results."""
        # We need to patch at the module level to test caching
        from app.services import embedding_service

        # Reset the cache for this test
        embedding_service._embedding_cache = FallbackEmbeddingCache(
            redis_url=None, maxsize=1000
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_httpx_client
            mock_context.__aexit__.return_value = None
            MockClient.return_value = mock_context

            service = EmbeddingService()

            # First call - should make HTTP request
            result1 = await service.generate_embedding("test query")
            assert result1 == [0.1, 0.2, 0.3, 0.4]
            assert mock_httpx_client.post.call_count == 1

            # Second call with same query - should use cache
            result2 = await service.generate_embedding("test query")
            assert result2 == [0.1, 0.2, 0.3, 0.4]
            # HTTP should NOT be called again
            assert mock_httpx_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_embedding_service_cache_normalized_queries(self, mock_httpx_client):
        """EmbeddingService cache should work with normalized queries."""
        from app.services import embedding_service

        # Reset the cache for this test
        embedding_service._embedding_cache = FallbackEmbeddingCache(
            redis_url=None, maxsize=1000
        )

        with patch("httpx.AsyncClient") as MockClient:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_httpx_client
            mock_context.__aexit__.return_value = None
            MockClient.return_value = mock_context

            service = EmbeddingService()

            # First call
            await service.generate_embedding("Test Query")
            assert mock_httpx_client.post.call_count == 1

            # These should all hit the cache (normalized to same key)
            await service.generate_embedding("test query")
            await service.generate_embedding("TEST QUERY")
            await service.generate_embedding("  Test Query  ")

            # HTTP should only be called once
            assert mock_httpx_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_embedding_service_returns_none_for_empty_input(self):
        """EmbeddingService should return None for empty input without HTTP call."""
        service = EmbeddingService()

        result = await service.generate_embedding("")
        assert result is None

        result = await service.generate_embedding("   ")
        assert result is None

        result = await service.generate_embedding(None)  # type: ignore
        assert result is None


# Backward compatibility test for EmbeddingCache alias
class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with EmbeddingCache alias."""

    def test_embedding_cache_alias_exists(self):
        """EmbeddingCache should be an alias for InMemoryEmbeddingCache."""
        assert EmbeddingCache is InMemoryEmbeddingCache

    @pytest.mark.asyncio
    async def test_embedding_cache_alias_works(self):
        """EmbeddingCache alias should work the same as InMemoryEmbeddingCache."""
        cache = EmbeddingCache(maxsize=10)
        await cache.set("test", [0.1, 0.2])
        result = await cache.get("test")
        assert result == [0.1, 0.2]
