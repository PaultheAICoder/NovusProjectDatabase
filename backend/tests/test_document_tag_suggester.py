"""Tests for document tag suggestion service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.document_tag_suggester import STOP_WORDS, DocumentTagSuggester


class TestKeywordExtraction:
    """Tests for keyword extraction from document text."""

    def test_extract_keywords_basic(self):
        """Should extract keywords from sample text."""
        db_mock = MagicMock()
        suggester = DocumentTagSuggester(db_mock)

        text = """
        This document discusses Python programming and machine learning.
        Python is a great programming language for machine learning projects.
        We also cover testing methodologies and automation testing.
        """

        keywords = suggester._extract_keywords(text)

        # Common words that appear multiple times should be included
        assert "python" in keywords
        assert "programming" in keywords
        assert "machine" in keywords
        assert "learning" in keywords
        assert "testing" in keywords

    def test_extract_keywords_filters_stopwords(self):
        """Should filter out common stop words."""
        db_mock = MagicMock()
        suggester = DocumentTagSuggester(db_mock)

        text = """
        The Python programming language is very popular.
        Python is used for programming and many applications.
        It is also great for automation and testing.
        """

        keywords = suggester._extract_keywords(text)

        # Stop words should NOT be in keywords
        assert "the" not in keywords
        assert "and" not in keywords
        assert "for" not in keywords
        assert "is" not in keywords
        assert "it" not in keywords
        assert "also" not in keywords
        assert "very" not in keywords

        # Actual keywords should be present (must appear at least twice)
        assert "python" in keywords
        assert "programming" in keywords

    def test_extract_keywords_minimum_frequency(self):
        """Should only include words that appear at least twice."""
        db_mock = MagicMock()
        suggester = DocumentTagSuggester(db_mock)

        text = """
        Python is great. Python is popular.
        Unique word appears only once.
        """

        keywords = suggester._extract_keywords(text)

        # Python appears twice
        assert "python" in keywords

        # "unique" and "appears" only appear once
        assert "unique" not in keywords
        assert "appears" not in keywords

    def test_extract_keywords_minimum_length(self):
        """Should only include words with 3+ characters."""
        db_mock = MagicMock()
        suggester = DocumentTagSuggester(db_mock)

        text = """
        AI AI AI ML ML ML Python Python.
        OK OK OK at at at.
        """

        keywords = suggester._extract_keywords(text)

        # Two-letter words should be excluded
        assert "ai" not in keywords
        assert "ml" not in keywords
        assert "ok" not in keywords
        assert "at" not in keywords

        # Python (6 chars) should be included
        assert "python" in keywords


class TestTagMatching:
    """Tests for matching keywords to tags."""

    @pytest.mark.asyncio
    async def test_suggest_tags_exact_match(self):
        """Should match when tag name exactly appears in text."""
        # Create mock tags
        python_tag = MagicMock()
        python_tag.id = uuid4()
        python_tag.name = "Python"

        java_tag = MagicMock()
        java_tag.id = uuid4()
        java_tag.name = "Java"

        # Setup mock database
        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [python_tag, java_tag]
        db_mock.execute.return_value = result_mock

        suggester = DocumentTagSuggester(db_mock)

        text = """
        This document is about Python programming.
        Python is a great language for automation.
        We use Python for testing and development.
        """

        suggestions = await suggester.suggest_tags_from_text(text)

        # Should suggest Python (exact match)
        assert len(suggestions) > 0
        tag_names = [tag.name for tag, _ in suggestions]
        assert "Python" in tag_names

        # Java should NOT be suggested (not in text)
        assert "Java" not in tag_names

    @pytest.mark.asyncio
    async def test_suggest_tags_partial_match(self):
        """Should match when tag word appears in keywords."""
        # Create mock tag with multiple words
        ml_tag = MagicMock()
        ml_tag.id = uuid4()
        ml_tag.name = "machine-learning"

        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [ml_tag]
        db_mock.execute.return_value = result_mock

        suggester = DocumentTagSuggester(db_mock)

        text = """
        This document covers machine learning concepts.
        Machine learning is used for predictions.
        Learning algorithms are important for machine intelligence.
        """

        suggestions = await suggester.suggest_tags_from_text(text)

        # Should suggest machine-learning (partial word match)
        assert len(suggestions) > 0
        tag_names = [tag.name for tag, _ in suggestions]
        assert "machine-learning" in tag_names

    @pytest.mark.asyncio
    async def test_suggest_tags_no_matches(self):
        """Should return empty list when no tags match."""
        java_tag = MagicMock()
        java_tag.id = uuid4()
        java_tag.name = "Java"

        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [java_tag]
        db_mock.execute.return_value = result_mock

        suggester = DocumentTagSuggester(db_mock)

        text = """
        This document is about Python programming.
        Python is used for automation testing.
        """

        suggestions = await suggester.suggest_tags_from_text(text)

        # No tags should match
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    async def test_suggest_tags_respects_limit(self):
        """Should respect the limit parameter."""
        # Create many mock tags
        tags = []
        for i in range(10):
            tag = MagicMock()
            tag.id = uuid4()
            tag.name = f"Tag{i}"
            tags.append(tag)

        db_mock = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = tags
        db_mock.execute.return_value = result_mock

        suggester = DocumentTagSuggester(db_mock)

        # Create text that matches many tags
        text = " ".join([f"Tag{i} Tag{i}" for i in range(10)])

        suggestions = await suggester.suggest_tags_from_text(text, limit=3)

        # Should return at most 3 suggestions
        assert len(suggestions) <= 3

    @pytest.mark.asyncio
    async def test_suggest_tags_short_text(self):
        """Should return empty list for very short text."""
        db_mock = AsyncMock()
        suggester = DocumentTagSuggester(db_mock)

        # Text too short (< 50 chars)
        text = "Short text"

        suggestions = await suggester.suggest_tags_from_text(text)

        assert len(suggestions) == 0
        # Should not even query the database
        db_mock.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_suggest_tags_empty_text(self):
        """Should return empty list for empty text."""
        db_mock = AsyncMock()
        suggester = DocumentTagSuggester(db_mock)

        suggestions = await suggester.suggest_tags_from_text("")

        assert len(suggestions) == 0
        db_mock.execute.assert_not_called()


class TestStopWords:
    """Tests for stop words configuration."""

    def test_stop_words_includes_common_words(self):
        """Stop words should include common English words."""
        assert "the" in STOP_WORDS
        assert "and" in STOP_WORDS
        assert "for" in STOP_WORDS
        assert "with" in STOP_WORDS

    def test_stop_words_includes_document_terms(self):
        """Stop words should include document-specific terms."""
        assert "page" in STOP_WORDS
        assert "document" in STOP_WORDS
        assert "section" in STOP_WORDS

    def test_stop_words_is_frozenset(self):
        """Stop words should be immutable."""
        assert isinstance(STOP_WORDS, frozenset)
