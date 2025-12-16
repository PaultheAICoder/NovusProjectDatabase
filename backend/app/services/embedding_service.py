"""Embedding service with Ollama integration and query embedding caching."""

import time

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """Thread-safe embedding cache with LRU eviction."""

    def __init__(self, maxsize: int = 1000):
        self._cache: dict[str, list[float]] = {}
        self._access_order: list[str] = []
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0

    def _normalize_key(self, text: str) -> str:
        """Normalize text for cache key."""
        return text.strip().lower()

    def get(self, text: str) -> list[float] | None:
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

    def set(self, text: str, embedding: list[float]) -> None:
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
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
        }


# Global cache instance
_embedding_cache = EmbeddingCache(maxsize=1000)


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

        Uses an in-memory LRU cache to avoid redundant HTTP calls for
        repeated queries (e.g., during pagination or filter changes).

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None if failed
        """
        if not text or not text.strip():
            return None

        # Check cache first
        cached = _embedding_cache.get(text)
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
                    _embedding_cache.set(text, embedding)
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
