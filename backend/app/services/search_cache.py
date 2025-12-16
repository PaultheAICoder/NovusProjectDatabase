"""Search result caching service with Redis backend."""

import hashlib
import json

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SearchCacheInterface:
    """Interface for search cache implementations."""

    async def get(self, cache_key: str) -> dict | None:
        """Get cached search results."""
        ...

    async def set(self, cache_key: str, results: dict) -> None:
        """Store search results in cache."""
        ...

    async def invalidate_all(self) -> int:
        """Invalidate all search cache entries. Returns count of deleted keys."""
        ...

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        ...


class InMemorySearchCache:
    """In-memory search cache for fallback when Redis unavailable."""

    def __init__(self, maxsize: int = 500):
        self._cache: dict[str, dict] = {}
        self._access_order: list[str] = []
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0

    async def get(self, cache_key: str) -> dict | None:
        """Get cached search results."""
        if cache_key in self._cache:
            self._hits += 1
            self._access_order.remove(cache_key)
            self._access_order.append(cache_key)
            return self._cache[cache_key]
        self._misses += 1
        return None

    async def set(self, cache_key: str, results: dict) -> None:
        """Store search results in cache."""
        if cache_key in self._cache:
            self._access_order.remove(cache_key)
        elif len(self._cache) >= self._maxsize:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        self._cache[cache_key] = results
        self._access_order.append(cache_key)

    async def invalidate_all(self) -> int:
        """Invalidate all entries."""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        return count

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


class RedisSearchCache:
    """Redis-backed search result cache with TTL and pattern-based invalidation."""

    CACHE_PREFIX = "search:"

    def __init__(self, redis_url: str, ttl_seconds: int = 300):
        self._redis_url = redis_url
        self._ttl = ttl_seconds
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

    def _make_key(self, cache_key: str) -> str:
        """Create prefixed Redis key."""
        return f"{self.CACHE_PREFIX}{cache_key}"

    async def get(self, cache_key: str) -> dict | None:
        """Get cached search results."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            key = self._make_key(cache_key)
            data = await client.get(key)
            if data:
                self._hits += 1
                return json.loads(data)
            self._misses += 1
            return None
        except RedisError as e:
            logger.warning("redis_search_cache_get_error", error=str(e))
            self._misses += 1
            return None

    async def set(self, cache_key: str, results: dict) -> None:
        """Store search results in Redis with TTL."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            key = self._make_key(cache_key)
            await client.setex(key, self._ttl, json.dumps(results, default=str))
        except RedisError as e:
            logger.warning("redis_search_cache_set_error", error=str(e))

    async def invalidate_all(self) -> int:
        """Invalidate all search cache entries using pattern matching."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            pattern = f"{self.CACHE_PREFIX}*"
            cursor = 0
            count = 0
            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    count += len(keys)
                    await client.delete(*keys)
                if cursor == 0:
                    break
            logger.info("search_cache_invalidated", keys_deleted=count)
            return count
        except RedisError as e:
            logger.warning("redis_search_cache_invalidate_error", error=str(e))
            return 0

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


class FallbackSearchCache:
    """Search cache with automatic fallback to in-memory on Redis failures."""

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int = 300,
        maxsize: int = 500,
    ):
        self._redis_cache: RedisSearchCache | None = None
        self._memory_cache = InMemorySearchCache(maxsize=maxsize)
        self._using_fallback = False

        if redis_url:
            self._redis_cache = RedisSearchCache(
                redis_url=redis_url,
                ttl_seconds=ttl_seconds,
            )

    async def get(self, cache_key: str) -> dict | None:
        """Get from Redis first, fallback to memory on error."""
        if self._redis_cache and not self._using_fallback:
            try:
                result = await self._redis_cache.get(cache_key)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(
                    "search_cache_fallback_triggered",
                    operation="get",
                    error=str(e),
                )
                self._using_fallback = True

        return await self._memory_cache.get(cache_key)

    async def set(self, cache_key: str, results: dict) -> None:
        """Store in both caches for redundancy."""
        await self._memory_cache.set(cache_key, results)

        if self._redis_cache and not self._using_fallback:
            try:
                await self._redis_cache.set(cache_key, results)
            except Exception as e:
                logger.warning(
                    "search_cache_fallback_triggered",
                    operation="set",
                    error=str(e),
                )
                self._using_fallback = True

    async def invalidate_all(self) -> int:
        """Invalidate all entries in both caches."""
        memory_count = await self._memory_cache.invalidate_all()

        if self._redis_cache and not self._using_fallback:
            try:
                redis_count = await self._redis_cache.invalidate_all()
                return redis_count
            except Exception as e:
                logger.warning(
                    "search_cache_invalidate_error",
                    error=str(e),
                )

        return memory_count

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


def generate_cache_key(
    query: str,
    status: list[str] | None,
    organization_id: str | None,
    tag_ids: list[str] | None,
    owner_id: str | None,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> str:
    """
    Generate deterministic cache key from search parameters.

    Uses MD5 hash of normalized parameters for consistent key generation.
    """
    # Normalize parameters
    params = {
        "q": query.strip().lower() if query else "",
        "status": sorted(status) if status else None,
        "org_id": str(organization_id) if organization_id else None,
        "tag_ids": sorted(str(t) for t in tag_ids) if tag_ids else None,
        "owner_id": str(owner_id) if owner_id else None,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": page,
        "page_size": page_size,
    }

    # Create deterministic string representation
    param_str = json.dumps(params, sort_keys=True)

    # Hash for shorter key
    key_hash = hashlib.md5(param_str.encode()).hexdigest()

    return key_hash


def create_search_cache() -> FallbackSearchCache:
    """Create search cache instance based on configuration."""
    settings = get_settings()

    if settings.is_redis_configured and settings.search_cache_enabled:
        logger.info(
            "search_cache_init",
            cache_type="redis",
            ttl_seconds=settings.search_cache_ttl,
        )
        return FallbackSearchCache(
            redis_url=settings.redis_url,
            ttl_seconds=settings.search_cache_ttl,
        )
    elif settings.search_cache_enabled:
        logger.info(
            "search_cache_init",
            cache_type="in_memory",
        )
        return FallbackSearchCache(redis_url=None)
    else:
        logger.info("search_cache_disabled")
        return FallbackSearchCache(redis_url=None, maxsize=0)


# Global cache instance
_search_cache: FallbackSearchCache | None = None


def get_search_cache() -> FallbackSearchCache:
    """Get or create the global search cache instance."""
    global _search_cache
    if _search_cache is None:
        _search_cache = create_search_cache()
    return _search_cache


async def invalidate_search_cache() -> int:
    """Invalidate all search cache entries. Call on data changes."""
    cache = get_search_cache()
    return await cache.invalidate_all()
