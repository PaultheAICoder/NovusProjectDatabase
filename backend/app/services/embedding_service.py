"""Embedding service with Ollama integration."""

import httpx

from app.config import get_settings


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

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None if failed
        """
        if not text or not text.strip():
            return None

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
                return data.get("embedding")
        except httpx.HTTPError as e:
            # Log error but don't raise - embeddings are optional
            print(f"Error generating embedding: {e}")
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
