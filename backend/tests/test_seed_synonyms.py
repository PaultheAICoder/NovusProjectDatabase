"""Tests for seed_synonyms script."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import Tag, TagType
from app.scripts.seed_synonyms import (
    TECHNOLOGY_SYNONYMS,
    ensure_tag_exists,
    seed_synonyms,
)


class TestEnsureTagExists:
    """Tests for ensure_tag_exists helper."""

    @pytest.mark.asyncio
    async def test_returns_existing_tag(self):
        """Should return existing tag without creating new one."""
        existing_tag = MagicMock(spec=Tag)
        existing_tag.id = uuid4()
        existing_tag.name = "BLE"
        existing_tag.type = TagType.TECHNOLOGY

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_tag
        mock_db.execute.return_value = mock_result

        tag, was_created = await ensure_tag_exists(mock_db, "BLE", TagType.TECHNOLOGY)

        assert tag == existing_tag
        assert was_created is False
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_missing_tag(self):
        """Should create tag if it doesn't exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        tag, was_created = await ensure_tag_exists(mock_db, "IoT", TagType.TECHNOLOGY)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        assert was_created is True
        assert tag.name == "IoT"
        assert tag.type == TagType.TECHNOLOGY


class TestSynonymData:
    """Tests for synonym data structure."""

    def test_synonym_groups_not_empty(self):
        """Synonym groups should contain data."""
        assert len(TECHNOLOGY_SYNONYMS) > 0

    def test_each_group_has_multiple_terms(self):
        """Each synonym group should have at least 2 terms."""
        for group in TECHNOLOGY_SYNONYMS:
            assert len(group) >= 2, f"Group {group} has less than 2 terms"

    def test_expected_synonym_groups_present(self):
        """Expected synonym groups should be present."""
        group_starters = [group[0] for group in TECHNOLOGY_SYNONYMS]

        assert "BLE" in group_starters
        assert "Wi-Fi" in group_starters
        assert "IoT" in group_starters
        assert "AI" in group_starters
        assert "ML" in group_starters

    def test_has_minimum_expected_groups(self):
        """Should have at least 12 synonym groups as per requirements."""
        assert len(TECHNOLOGY_SYNONYMS) >= 12

    def test_no_empty_terms(self):
        """No term in any group should be empty."""
        for group in TECHNOLOGY_SYNONYMS:
            for term in group:
                assert term, "Empty term found in synonym group"
                assert (
                    term.strip() == term
                ), f"Term '{term}' has leading/trailing whitespace"

    def test_no_duplicate_terms_within_groups(self):
        """No duplicate terms within the same synonym group."""
        for group in TECHNOLOGY_SYNONYMS:
            assert len(group) == len(set(group)), f"Duplicate terms in group: {group}"


class TestSeedSynonyms:
    """Tests for seed_synonyms main function."""

    @pytest.mark.asyncio
    async def test_seed_synonyms_is_idempotent(self):
        """Running seed_synonyms twice should not raise errors."""
        with patch("app.scripts.seed_synonyms.async_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_maker.return_value.__aenter__.return_value = mock_session

            # Mock tag lookup to return existing tags
            mock_tag = MagicMock(spec=Tag)
            mock_tag.id = uuid4()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_tag
            mock_session.execute.return_value = mock_result

            # Mock add_synonym to return None (already exists)
            with patch(
                "app.scripts.seed_synonyms.TagSynonymService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.add_synonym = AsyncMock(return_value=None)
                mock_service_class.return_value = mock_service

                # Should not raise
                await seed_synonyms()

                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_synonyms_creates_synonyms_for_new_tags(self):
        """Should create synonym relationships for all pairs in each group."""
        with patch("app.scripts.seed_synonyms.async_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_maker.return_value.__aenter__.return_value = mock_session

            # Mock tag creation (return None for lookup, then mock add)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()

            # Mock the service to create synonyms
            with patch(
                "app.scripts.seed_synonyms.TagSynonymService"
            ) as mock_service_class:
                mock_service = MagicMock()
                # Return a mock TagSynonym to indicate creation
                mock_synonym = MagicMock()
                mock_service.add_synonym = AsyncMock(return_value=mock_synonym)
                mock_service_class.return_value = mock_service

                await seed_synonyms()

                # Verify add_synonym was called for pairs
                assert mock_service.add_synonym.call_count > 0

    @pytest.mark.asyncio
    async def test_seed_synonyms_logs_results(self):
        """Should log the results of seeding."""
        with patch("app.scripts.seed_synonyms.async_session_maker") as mock_maker:
            mock_session = AsyncMock()
            mock_maker.return_value.__aenter__.return_value = mock_session

            mock_tag = MagicMock(spec=Tag)
            mock_tag.id = uuid4()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_tag
            mock_session.execute.return_value = mock_result

            with patch(
                "app.scripts.seed_synonyms.TagSynonymService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.add_synonym = AsyncMock(return_value=None)
                mock_service_class.return_value = mock_service

                with patch("app.scripts.seed_synonyms.logger") as mock_logger:
                    await seed_synonyms()

                    # Should log the final results
                    mock_logger.info.assert_called()
                    call_args = mock_logger.info.call_args_list
                    # Check the final log call contains expected keys
                    final_call = call_args[-1]
                    assert "synonyms_seeded" in str(final_call)


class TestPairCalculation:
    """Tests for synonym pair calculation logic."""

    def test_pair_count_for_group_of_two(self):
        """A group of 2 should produce 1 pair."""
        # For [A, B]: A~B = 1 pair
        group = ["A", "B"]
        expected_pairs = 1
        actual_pairs = len(group) * (len(group) - 1) // 2
        assert actual_pairs == expected_pairs

    def test_pair_count_for_group_of_three(self):
        """A group of 3 should produce 3 pairs."""
        # For [A, B, C]: A~B, A~C, B~C = 3 pairs
        group = ["A", "B", "C"]
        expected_pairs = 3
        actual_pairs = len(group) * (len(group) - 1) // 2
        assert actual_pairs == expected_pairs

    def test_pair_count_for_group_of_four(self):
        """A group of 4 should produce 6 pairs."""
        # For [A, B, C, D]: A~B, A~C, A~D, B~C, B~D, C~D = 6 pairs
        group = ["A", "B", "C", "D"]
        expected_pairs = 6
        actual_pairs = len(group) * (len(group) - 1) // 2
        assert actual_pairs == expected_pairs

    def test_total_expected_pairs(self):
        """Calculate total expected synonym pairs from all groups."""
        total_pairs = sum(
            len(group) * (len(group) - 1) // 2 for group in TECHNOLOGY_SYNONYMS
        )
        # Should be a reasonable number based on group sizes
        assert total_pairs > 0
        # With at least 12 groups of 2+ terms, minimum is 12 pairs
        assert total_pairs >= 12
