"""Tests for embedding service and embedding cache."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_service import EmbeddingCache, EmbeddingService


class TestEmbeddingCache:
    """Tests for the EmbeddingCache class."""

    def test_cache_set_and_get(self):
        """Cache should store and retrieve embeddings correctly."""
        cache = EmbeddingCache(maxsize=10)
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        cache.set("test query", embedding)
        result = cache.get("test query")

        assert result == embedding

    def test_cache_returns_none_for_missing_key(self):
        """Cache should return None for keys not in cache."""
        cache = EmbeddingCache(maxsize=10)

        result = cache.get("nonexistent query")

        assert result is None

    def test_cache_normalized_keys(self):
        """Cache should normalize keys (lowercase, stripped whitespace)."""
        cache = EmbeddingCache(maxsize=10)
        embedding = [0.1, 0.2, 0.3]

        # Set with lowercase
        cache.set("test", embedding)

        # Get with various cases and whitespace - should all match
        assert cache.get("TEST") == embedding
        assert cache.get("Test") == embedding
        assert cache.get("  test  ") == embedding
        assert cache.get("  TEST  ") == embedding

    def test_cache_different_queries_different_embeddings(self):
        """Different queries should have different embeddings."""
        cache = EmbeddingCache(maxsize=10)
        embedding1 = [0.1, 0.2, 0.3]
        embedding2 = [0.4, 0.5, 0.6]

        cache.set("query one", embedding1)
        cache.set("query two", embedding2)

        assert cache.get("query one") == embedding1
        assert cache.get("query two") == embedding2
        assert cache.get("query one") != cache.get("query two")

    def test_cache_lru_eviction(self):
        """Cache should evict oldest entries when maxsize is reached."""
        cache = EmbeddingCache(maxsize=2)

        cache.set("first", [0.1])
        cache.set("second", [0.2])
        cache.set("third", [0.3])  # Should evict "first"

        assert cache.get("first") is None
        assert cache.get("second") == [0.2]
        assert cache.get("third") == [0.3]

    def test_cache_access_updates_lru_order(self):
        """Accessing a cache entry should move it to the end of the LRU queue."""
        cache = EmbeddingCache(maxsize=2)

        cache.set("first", [0.1])
        cache.set("second", [0.2])

        # Access "first" to move it to the end
        cache.get("first")

        # Add "third" - should evict "second" (now oldest)
        cache.set("third", [0.3])

        assert cache.get("first") == [0.1]
        assert cache.get("second") is None
        assert cache.get("third") == [0.3]

    def test_cache_stats(self):
        """Cache should track hits and misses correctly."""
        cache = EmbeddingCache(maxsize=10)

        # Initial stats
        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0

        # Add an entry
        cache.set("test", [0.1, 0.2])
        assert cache.stats["size"] == 1

        # Miss
        cache.get("nonexistent")
        assert cache.stats["misses"] == 1
        assert cache.stats["hits"] == 0

        # Hit
        cache.get("test")
        assert cache.stats["hits"] == 1
        assert cache.stats["misses"] == 1

        # Check hit rate
        assert cache.stats["hit_rate_percent"] == 50.0

    def test_cache_update_existing_key(self):
        """Updating an existing key should replace the value."""
        cache = EmbeddingCache(maxsize=10)

        cache.set("test", [0.1, 0.2])
        cache.set("test", [0.3, 0.4])

        assert cache.get("test") == [0.3, 0.4]
        assert cache.stats["size"] == 1  # Still only one entry


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
        embedding_service._embedding_cache = EmbeddingCache(maxsize=1000)

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
        embedding_service._embedding_cache = EmbeddingCache(maxsize=1000)

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
