"""Generic caching service with Redis backend and in-memory fallback.

Provides a reusable cache infrastructure for tag lists, organization lists,
dashboard stats, and other frequently-accessed, rarely-changing data.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CacheInterface:
    """Interface for cache implementations."""

    async def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache with optional TTL override."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete a specific key. Returns True if deleted."""
        ...

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching prefix. Returns count of deleted keys."""
        ...

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        ...


class InMemoryCache:
    """Thread-safe in-memory LRU cache with TTL support.

    Used as a fallback when Redis is unavailable or not configured.
    """

    def __init__(self, maxsize: int = 500, default_ttl: int = 300):
        self._cache: dict[str, Any] = {}
        self._access_order: list[str] = []
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        if key in self._cache:
            self._hits += 1
            # Update LRU order
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        self._misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache. TTL is ignored for in-memory cache."""
        _ = ttl  # TTL is not used for in-memory cache, but kept for interface
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self._maxsize:
            # Evict oldest entry
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._access_order.append(key)

    async def delete(self, key: str) -> bool:
        """Delete a specific key."""
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            return True
        return False

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching prefix."""
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]
            self._access_order.remove(key)
        return len(keys_to_delete)

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


class RedisCache:
    """Redis-backed cache with configurable prefix and TTL."""

    def __init__(self, redis_url: str, prefix: str = "", default_ttl: int = 300):
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
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

    def _make_key(self, key: str) -> str:
        """Create prefixed Redis key."""
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Any | None:
        """Get cached value by key."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            prefixed_key = self._make_key(key)
            data = await client.get(prefixed_key)
            if data:
                self._hits += 1
                return json.loads(data)
            self._misses += 1
            return None
        except RedisError as e:
            logger.warning("redis_cache_get_error", prefix=self._prefix, error=str(e))
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in Redis with TTL."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            prefixed_key = self._make_key(key)
            actual_ttl = ttl if ttl is not None else self._default_ttl
            await client.setex(prefixed_key, actual_ttl, json.dumps(value, default=str))
        except RedisError as e:
            logger.warning("redis_cache_set_error", prefix=self._prefix, error=str(e))

    async def delete(self, key: str) -> bool:
        """Delete a specific key."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            prefixed_key = self._make_key(key)
            result = await client.delete(prefixed_key)
            return result > 0
        except RedisError as e:
            logger.warning(
                "redis_cache_delete_error", prefix=self._prefix, error=str(e)
            )
            return False

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching prefix using SCAN."""
        from redis.exceptions import RedisError

        try:
            client = await self._get_client()
            # Use the provided prefix (which should include the cache prefix)
            pattern = f"{prefix}*"
            cursor = 0
            count = 0
            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    count += len(keys)
                    await client.delete(*keys)
                if cursor == 0:
                    break
            logger.info("cache_invalidated", prefix=prefix, keys_deleted=count)
            return count
        except RedisError as e:
            logger.warning("redis_cache_invalidate_error", prefix=prefix, error=str(e))
            return 0

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "type": "redis",
            "prefix": self._prefix,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
            "ttl_seconds": self._default_ttl,
        }


class FallbackCache:
    """Cache with automatic fallback to in-memory on Redis failures.

    Tries Redis first, falls back to in-memory cache on errors.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        prefix: str = "",
        default_ttl: int = 300,
        maxsize: int = 500,
    ):
        self._redis_cache: RedisCache | None = None
        self._memory_cache = InMemoryCache(maxsize=maxsize, default_ttl=default_ttl)
        self._using_fallback = False
        self._prefix = prefix
        self._default_ttl = default_ttl

        if redis_url:
            self._redis_cache = RedisCache(
                redis_url=redis_url,
                prefix=prefix,
                default_ttl=default_ttl,
            )

    async def get(self, key: str) -> Any | None:
        """Get from Redis first, fallback to memory on error."""
        if self._redis_cache and not self._using_fallback:
            try:
                result = await self._redis_cache.get(key)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning(
                    "cache_fallback_triggered",
                    prefix=self._prefix,
                    operation="get",
                    error=str(e),
                )
                self._using_fallback = True

        return await self._memory_cache.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store in both caches for redundancy."""
        await self._memory_cache.set(key, value, ttl)

        if self._redis_cache and not self._using_fallback:
            try:
                await self._redis_cache.set(key, value, ttl)
            except Exception as e:
                logger.warning(
                    "cache_fallback_triggered",
                    prefix=self._prefix,
                    operation="set",
                    error=str(e),
                )
                self._using_fallback = True

    async def delete(self, key: str) -> bool:
        """Delete from both caches."""
        memory_deleted = await self._memory_cache.delete(key)
        redis_deleted = False

        if self._redis_cache and not self._using_fallback:
            try:
                redis_deleted = await self._redis_cache.delete(key)
            except Exception as e:
                logger.warning(
                    "cache_delete_error",
                    prefix=self._prefix,
                    error=str(e),
                )

        return memory_deleted or redis_deleted

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching prefix in both caches."""
        memory_count = await self._memory_cache.invalidate_prefix(prefix)

        if self._redis_cache and not self._using_fallback:
            try:
                redis_count = await self._redis_cache.invalidate_prefix(prefix)
                return redis_count
            except Exception as e:
                logger.warning(
                    "cache_invalidate_error",
                    prefix=prefix,
                    error=str(e),
                )

        return memory_count

    async def close(self) -> None:
        """Close Redis connection if open."""
        if self._redis_cache:
            await self._redis_cache.close()

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


async def get_or_set(
    cache: FallbackCache,
    key: str,
    factory: Callable[[], Awaitable[T]],
    ttl: int | None = None,
) -> T:
    """Cache-aside pattern helper.

    Returns cached value if exists, otherwise calls factory,
    caches result, and returns it.

    Args:
        cache: The cache instance to use.
        key: Cache key.
        factory: Async callable that produces the value on cache miss.
        ttl: Optional TTL override.

    Returns:
        The cached or freshly computed value.
    """
    cached = await cache.get(key)
    if cached is not None:
        return cached

    value = await factory()
    await cache.set(key, value, ttl)
    return value


# Global cache instances (lazy initialization)
_tag_cache: FallbackCache | None = None
_org_cache: FallbackCache | None = None
_dashboard_cache: FallbackCache | None = None


def get_tag_cache() -> FallbackCache:
    """Get or create tag list cache."""
    global _tag_cache
    if _tag_cache is None:
        settings = get_settings()
        _tag_cache = FallbackCache(
            redis_url=settings.redis_url if settings.is_redis_configured else None,
            prefix="tags:",
            default_ttl=settings.tag_cache_ttl,
        )
        logger.info(
            "tag_cache_init",
            cache_type="redis" if settings.is_redis_configured else "in_memory",
            ttl_seconds=settings.tag_cache_ttl,
        )
    return _tag_cache


def get_org_cache() -> FallbackCache:
    """Get or create organization list cache."""
    global _org_cache
    if _org_cache is None:
        settings = get_settings()
        _org_cache = FallbackCache(
            redis_url=settings.redis_url if settings.is_redis_configured else None,
            prefix="orgs:",
            default_ttl=settings.org_cache_ttl,
        )
        logger.info(
            "org_cache_init",
            cache_type="redis" if settings.is_redis_configured else "in_memory",
            ttl_seconds=settings.org_cache_ttl,
        )
    return _org_cache


def get_dashboard_cache() -> FallbackCache:
    """Get or create dashboard stats cache."""
    global _dashboard_cache
    if _dashboard_cache is None:
        settings = get_settings()
        _dashboard_cache = FallbackCache(
            redis_url=settings.redis_url if settings.is_redis_configured else None,
            prefix="dash:",
            default_ttl=settings.dashboard_cache_ttl,
        )
        logger.info(
            "dashboard_cache_init",
            cache_type="redis" if settings.is_redis_configured else "in_memory",
            ttl_seconds=settings.dashboard_cache_ttl,
        )
    return _dashboard_cache


async def invalidate_tag_cache() -> int:
    """Invalidate all tag cache entries."""
    cache = get_tag_cache()
    count = await cache.invalidate_prefix("tags:")
    logger.info("tag_cache_invalidated", keys_deleted=count)
    return count


async def invalidate_org_cache() -> int:
    """Invalidate all organization cache entries."""
    cache = get_org_cache()
    count = await cache.invalidate_prefix("orgs:")
    logger.info("org_cache_invalidated", keys_deleted=count)
    return count


async def invalidate_dashboard_cache() -> int:
    """Invalidate all dashboard cache entries."""
    cache = get_dashboard_cache()
    count = await cache.invalidate_prefix("dash:")
    logger.info("dashboard_cache_invalidated", keys_deleted=count)
    return count


def reset_caches() -> None:
    """Reset all cache instances. Primarily for testing."""
    global _tag_cache, _org_cache, _dashboard_cache
    _tag_cache = None
    _org_cache = None
    _dashboard_cache = None
