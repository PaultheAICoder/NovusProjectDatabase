"""Document tag suggestion service.

This service analyzes document text content and suggests relevant tags
based on keyword extraction and matching against existing tags.
"""

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag

# Common English stop words to filter out from keyword extraction
STOP_WORDS = frozenset(
    {
        # Articles
        "the",
        "a",
        "an",
        # Prepositions
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "about",
        "into",
        "over",
        "after",
        "beneath",
        "under",
        "above",
        "between",
        "through",
        # Conjunctions
        "and",
        "or",
        "but",
        "nor",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        # Pronouns
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "ours",
        "ourselves",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
        "it",
        "its",
        "itself",
        "they",
        "them",
        "their",
        "theirs",
        "themselves",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        # Verbs (common)
        "is",
        "am",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "would",
        "should",
        "could",
        "ought",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "will",
        "may",
        # Adverbs
        "not",
        "very",
        "just",
        "also",
        "only",
        "even",
        "still",
        "already",
        "always",
        "never",
        "ever",
        "often",
        "sometimes",
        "usually",
        "here",
        "there",
        "now",
        "then",
        "today",
        "tomorrow",
        "yesterday",
        # Other common words
        "all",
        "each",
        "every",
        "any",
        "some",
        "no",
        "none",
        "one",
        "two",
        "three",
        "few",
        "many",
        "much",
        "more",
        "most",
        "other",
        "another",
        "such",
        "same",
        "different",
        "own",
        "new",
        "old",
        "first",
        "last",
        "next",
        "before",
        "because",
        "while",
        "where",
        "when",
        "why",
        "how",
        "than",
        "like",
        "too",
        # Document-specific common words
        "page",
        "pages",
        "section",
        "document",
        "file",
        "data",
        "table",
        "figure",
        "see",
        "use",
        "using",
        "used",
        "based",
        "following",
        "example",
        "note",
        "below",
        "however",
        "therefore",
        "thus",
        "furthermore",
        "moreover",
        "additionally",
        "finally",
        "firstly",
        "secondly",
        "thirdly",
        "etc",
    }
)


class DocumentTagSuggester:
    """Service for suggesting tags based on document content."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Async database session for querying tags
        """
        self.db = db

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract significant keywords from document text.

        Args:
            text: Document text content

        Returns:
            Set of keywords (lowercased) that appear frequently in the text
        """
        # Extract words (3+ chars, letters only)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Count frequency
        word_counts = Counter(words)

        # Return top frequent words (excluding stop words, minimum 2 occurrences)
        keywords = {
            word
            for word, count in word_counts.most_common(100)
            if word not in STOP_WORDS and count >= 2
        }

        return keywords

    async def suggest_tags_from_text(
        self,
        text: str,
        limit: int = 5,
    ) -> list[tuple[Tag, float]]:
        """Suggest tags based on document text content.

        Extracts keywords from the text and matches them against existing
        tag names and tag name words.

        Args:
            text: Document text content to analyze
            limit: Maximum number of tags to suggest

        Returns:
            List of (Tag, score) tuples sorted by relevance score (descending)
        """
        if not text or len(text) < 50:
            # Not enough content to analyze
            return []

        keywords = self._extract_keywords(text)

        if not keywords:
            return []

        # Fetch all tags
        result = await self.db.execute(select(Tag))
        all_tags = result.scalars().all()

        matches: list[tuple[Tag, float]] = []

        for tag in all_tags:
            tag_name_lower = tag.name.lower()
            tag_words = set(tag_name_lower.replace("-", " ").replace("_", " ").split())

            # Check for exact tag name match in keywords
            if tag_name_lower in keywords:
                # Exact match - highest score
                matches.append((tag, 1.0))
            elif tag_words & keywords:
                # Partial match - tag word appears in keywords
                # Score based on how many tag words match
                matching_words = tag_words & keywords
                score = 0.6 + (len(matching_words) / len(tag_words)) * 0.3
                matches.append((tag, score))
            else:
                # Check if tag name appears as substring in any keyword
                # This catches cases like "python" matching keyword "python3"
                for keyword in keywords:
                    if tag_name_lower in keyword or keyword in tag_name_lower:
                        matches.append((tag, 0.5))
                        break

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches[:limit]
