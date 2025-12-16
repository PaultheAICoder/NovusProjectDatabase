"""Embedding service with Ollama integration and query embedding caching."""

import json
import time
from typing import Protocol

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingCacheInterface(Protocol):
    """Interface for embedding cache implementations."""

    async def get(self, text: str) -> list[float] | None:
        """Get embedding from cache."""
        ...

    async def set(self, text: str, embedding: list[float]) -> None:
        """Store embedding in cache."""
        ...

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        ...


class InMemoryEmbeddingCache:
    """Thread-safe in-memory embedding cache with LRU eviction."""

    def __init__(self, maxsize: int = 1000):
        self._cache: dict[str, list[float]] = {}
        self._access_order: list[str] = []
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0

    def _normalize_key(self, text: str) -> str:
        """Normalize text for cache key."""
        return text.strip().lower()

    async def get(self, text: str) -> list[float] | None:
        """Get embedding from cache."""
        key = self._normalize_key(text)
        if key in self._cache:
            self._hits += 1
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        self._misses += 1
        return None

    async def set(self, text: str, embedding: list[float]) -> None:
        """Store embedding in cache."""
        key = self._normalize_key(text)
        if key in self._cache:
            # Update existing
            self._access_order.remove(key)
        elif len(self._cache) >= self._maxsize:
            # Evict oldest
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = embedding
        self._access_order.append(key)

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "type": "in_memory",
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
        }


class RedisEmbeddingCache:
    """Redis-backed embedding cache with TTL support."""

    def __init__(self, redis_url: str, ttl_seconds: int = 86400, prefix: str = "emb:"):
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._prefix = prefix
        self._client = None
        self._hits = 0
        self._misses = 0

    async def _get_client(self):
        """Get or create Redis client (lazy initialization)."""
        if self._client is None:
            from redis.asyncio import Redis as AsyncRedis

            self._client = AsyncRedis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    def _normalize_key(self, text: str) -> str:
        """Normalize text for cache key."""
        return self._prefix + text.strip().lower()

    async def get(self, text: str) -> list[float] | None:
        """Get embedding from Redis cache."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            key = self._normalize_key(text)
            data = await client.get(key)
            if data:
                self._hits += 1
                return json.loads(data)
            self._misses += 1
            return None
        except RedisError as e:
            logger.warning("redis_cache_get_error", error=str(e))
            self._misses += 1
            return None

    async def set(self, text: str, embedding: list[float]) -> None:
        """Store embedding in Redis with TTL."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            key = self._normalize_key(text)
            await client.setex(key, self._ttl, json.dumps(embedding))
        except RedisError as e:
            logger.warning("redis_cache_set_error", error=str(e))

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "type": "redis",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
            "ttl_seconds": self._ttl,
        }

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


class FallbackEmbeddingCache:
    """
    Embedding cache with automatic fallback to in-memory cache on Redis failures.

    Tries Redis first, falls back to in-memory if Redis is unavailable or errors.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int = 86400,
        maxsize: int = 10000,
    ):
        self._redis_cache: RedisEmbeddingCache | None = None
        self._memory_cache = InMemoryEmbeddingCache(maxsize=maxsize)
        self._using_fallback = False
        self._redis_available = False

        if redis_url:
            self._redis_cache = RedisEmbeddingCache(
                redis_url=redis_url,
                ttl_seconds=ttl_seconds,
            )
            self._redis_available = True

    async def _check_redis_health(self) -> bool:
        """Check if Redis is available."""
        if not self._redis_cache:
            return False
        try:
            client = await self._redis_cache._get_client()
            await client.ping()
            return True
        except Exception:
            return False

    async def get(self, text: str) -> list[float] | None:
        """Get embedding, trying Redis first then fallback."""
        if self._redis_cache and not self._using_fallback:
            try:
                result = await self._redis_cache.get(text)
                if result is not None:
                    return result
                # Cache miss in Redis - also check memory (for fallback entries)
            except Exception as e:
                logger.warning(
                    "redis_cache_fallback_triggered",
                    operation="get",
                    error=str(e),
                )
                self._using_fallback = True

        # Use memory cache (either as primary or fallback)
        return await self._memory_cache.get(text)

    async def set(self, text: str, embedding: list[float]) -> None:
        """Set embedding in cache(s)."""
        # Always set in memory cache for fallback
        await self._memory_cache.set(text, embedding)

        if self._redis_cache and not self._using_fallback:
            try:
                await self._redis_cache.set(text, embedding)
            except Exception as e:
                logger.warning(
                    "redis_cache_fallback_triggered",
                    operation="set",
                    error=str(e),
                )
                self._using_fallback = True

    @property
    def stats(self) -> dict:
        """Return combined cache statistics."""
        if self._redis_cache and not self._using_fallback:
            redis_stats = self._redis_cache.stats
            redis_stats["fallback_active"] = False
            return redis_stats
        else:
            memory_stats = self._memory_cache.stats
            memory_stats["fallback_active"] = self._using_fallback
            memory_stats["redis_configured"] = self._redis_cache is not None
            return memory_stats


def create_embedding_cache() -> FallbackEmbeddingCache:
    """
    Create embedding cache instance based on configuration.

    Returns FallbackEmbeddingCache which uses Redis if configured,
    otherwise falls back to in-memory cache.
    """
    settings = get_settings()

    if settings.is_redis_configured:
        logger.info(
            "embedding_cache_init",
            cache_type="redis",
            ttl_seconds=settings.embedding_cache_ttl,
        )
        return FallbackEmbeddingCache(
            redis_url=settings.redis_url,
            ttl_seconds=settings.embedding_cache_ttl,
            maxsize=settings.embedding_cache_maxsize,
        )
    else:
        logger.info(
            "embedding_cache_init",
            cache_type="in_memory",
            maxsize=settings.embedding_cache_maxsize,
        )
        return FallbackEmbeddingCache(
            redis_url=None,
            maxsize=settings.embedding_cache_maxsize,
        )


# Global cache instance (created on first import)
_embedding_cache = create_embedding_cache()


class EmbeddingService:
    """Service for generating embeddings using Ollama."""

    # Token approximation: ~4 characters per token on average
    CHARS_PER_TOKEN = 4
    CHUNK_SIZE_TOKENS = 512
    CHUNK_OVERLAP_PERCENT = 0.12

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.ollama_embedding_model
        self.base_url = self.settings.ollama_base_url

    @property
    def chunk_size_chars(self) -> int:
        """Get chunk size in characters."""
        return self.CHUNK_SIZE_TOKENS * self.CHARS_PER_TOKEN

    @property
    def chunk_overlap_chars(self) -> int:
        """Get chunk overlap in characters."""
        return int(self.chunk_size_chars * self.CHUNK_OVERLAP_PERCENT)

    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks.

        Uses 512 tokens (approx 2048 chars) per chunk with 12% overlap.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        chunk_size = self.chunk_size_chars
        overlap = self.chunk_overlap_chars
        step = chunk_size - overlap

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence or word boundary
            if end < len(text):
                # Look for sentence end near the chunk boundary
                for boundary in [".\n", ". ", "!\n", "! ", "?\n", "? "]:
                    idx = text.rfind(boundary, start + step, end)
                    if idx != -1:
                        end = idx + len(boundary)
                        break
                else:
                    # Fall back to word boundary
                    space_idx = text.rfind(" ", start + step, end)
                    if space_idx != -1:
                        end = space_idx + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start += step
            if start + step >= len(text) and start < len(text):
                # Last chunk - include remaining text
                remaining = text[start:].strip()
                if remaining and remaining != chunks[-1] if chunks else True:
                    chunks.append(remaining)
                break

        return chunks

    async def generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate embedding for text using Ollama.

        Uses a cache (Redis if configured, otherwise in-memory LRU) to avoid
        redundant HTTP calls for repeated queries (e.g., during pagination
        or filter changes).

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None if failed
        """
        if not text or not text.strip():
            return None

        # Check cache first
        cached = await _embedding_cache.get(text)
        if cached is not None:
            logger.debug(
                "embedding_cache_hit",
                query_length=len(text),
                cache_stats=_embedding_cache.stats,
            )
            return cached

        # Cache miss - generate embedding
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text,
                    },
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")

                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if embedding:
                    # Store in cache
                    await _embedding_cache.set(text, embedding)
                    logger.debug(
                        "embedding_cache_miss",
                        query_length=len(text),
                        generation_time_ms=round(elapsed_ms, 2),
                        cache_stats=_embedding_cache.stats,
                    )

                return embedding
        except httpx.HTTPError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            # Log error but don't raise - embeddings are optional
            logger.warning(
                "embedding_generation_failed",
                error=str(e),
                error_type=type(e).__name__,
                elapsed_ms=round(elapsed_ms, 2),
            )
            return None

    async def generate_embeddings_batch(
        self,
        texts: list[str],
    ) -> list[list[float] | None]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings (None for failed items)
        """
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings


# Backward compatibility: Keep EmbeddingCache as alias for InMemoryEmbeddingCache
EmbeddingCache = InMemoryEmbeddingCache
