"""Tests for AutoResolutionService."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.monday_sync import AutoResolutionRule, PreferredSource
from app.services.auto_resolution_service import AutoResolutionService


class TestListRules:
    """Tests for list_rules method."""

    @pytest.mark.asyncio
    async def test_list_rules_returns_ordered_by_priority(self):
        """Test rules are returned ordered by priority descending."""
        rule1 = MagicMock(spec=AutoResolutionRule)
        rule1.id = uuid4()
        rule1.priority = 1

        rule2 = MagicMock(spec=AutoResolutionRule)
        rule2.id = uuid4()
        rule2.priority = 10

        mock_db = AsyncMock()
        mock_db.scalar.return_value = 2
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            rule2,
            rule1,
        ]  # High priority first
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        rules, total = await service.list_rules()

        assert total == 2
        assert len(rules) == 2


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_rule_when_found(self):
        """Test rule is returned when found by ID."""
        rule = MagicMock(spec=AutoResolutionRule)
        rule.id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rule
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        result = await service.get_by_id(rule.id)

        assert result is not None
        assert result.id == rule.id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        """Test None is returned when rule not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        result = await service.get_by_id(uuid4())

        assert result is None


class TestCreate:
    """Tests for create method."""

    @pytest.mark.asyncio
    async def test_create_adds_rule_to_database(self):
        """Test create adds rule to database and returns it."""
        mock_db = AsyncMock()

        service = AutoResolutionService(mock_db)
        rule = await service.create(
            name="Test Rule",
            entity_type="contact",
            preferred_source=PreferredSource.NPD,
            field_name="email",
            is_enabled=True,
            priority=10,
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        assert rule is not None
        assert rule.name == "Test Rule"
        assert rule.entity_type == "contact"
        assert rule.preferred_source == PreferredSource.NPD


class TestUpdate:
    """Tests for update method."""

    @pytest.mark.asyncio
    async def test_update_modifies_existing_rule(self):
        """Test update modifies the existing rule."""
        rule = MagicMock(spec=AutoResolutionRule)
        rule.id = uuid4()
        rule.name = "Old Name"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rule
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        result = await service.update(
            rule_id=rule.id,
            name="New Name",
        )

        mock_db.flush.assert_called_once()
        assert result is not None
        assert rule.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        """Test update returns None when rule not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        result = await service.update(rule_id=uuid4(), name="New Name")

        assert result is None


class TestDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_removes_rule(self):
        """Test delete removes the rule from database."""
        rule = MagicMock(spec=AutoResolutionRule)
        rule.id = uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rule
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        result = await service.delete(rule.id)

        mock_db.delete.assert_called_once_with(rule)
        mock_db.flush.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        """Test delete returns False when rule not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        result = await service.delete(uuid4())

        mock_db.delete.assert_not_called()
        assert result is False


class TestFindMatchingRule:
    """Tests for find_matching_rule method."""

    @pytest.mark.asyncio
    async def test_field_specific_rule_takes_precedence(self):
        """Test field-specific rules match before entity-wide."""
        field_rule = MagicMock(spec=AutoResolutionRule)
        field_rule.id = uuid4()
        field_rule.entity_type = "contact"
        field_rule.field_name = "email"
        field_rule.is_enabled = True
        field_rule.priority = 5

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_first.return_value = field_rule
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        rule = await service.find_matching_rule("contact", "email")

        assert rule is not None
        assert rule.field_name == "email"

    @pytest.mark.asyncio
    async def test_entity_wide_rule_used_when_no_field_match(self):
        """Test entity-wide rule used when no field-specific rule."""
        entity_rule = MagicMock(spec=AutoResolutionRule)
        entity_rule.id = uuid4()
        entity_rule.entity_type = "contact"
        entity_rule.field_name = None
        entity_rule.is_enabled = True
        entity_rule.priority = 10

        mock_db = AsyncMock()
        # First query (field-specific) returns None
        mock_result1 = MagicMock()
        mock_result1.scalar_first.return_value = None
        # Second query (entity-wide) returns rule
        mock_result2 = MagicMock()
        mock_result2.scalar_first.return_value = entity_rule
        mock_db.execute.side_effect = [mock_result1, mock_result2]

        service = AutoResolutionService(mock_db)
        rule = await service.find_matching_rule("contact", "email")

        assert rule is not None
        assert rule.field_name is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_rule(self):
        """Test returns None when no rule matches."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_first.return_value = None
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        rule = await service.find_matching_rule("contact", "email")

        assert rule is None


class TestTryAutoResolve:
    """Tests for try_auto_resolve method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_rule_matches(self):
        """Test returns (True, rule, resolution_type) when rule matches."""
        rule = MagicMock(spec=AutoResolutionRule)
        rule.id = uuid4()
        rule.name = "Test Rule"
        rule.preferred_source = PreferredSource.NPD

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_first.return_value = rule
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        can_resolve, matched_rule, resolution_type = await service.try_auto_resolve(
            entity_type="contact",
            entity_id=uuid4(),
            conflict_fields=["email"],
            npd_data={"email": "npd@test.com"},
            monday_data={"email": "monday@test.com"},
        )

        assert can_resolve is True
        assert matched_rule is not None
        assert resolution_type == "keep_npd"

    @pytest.mark.asyncio
    async def test_returns_keep_monday_for_monday_source(self):
        """Test returns keep_monday when preferred source is monday."""
        rule = MagicMock(spec=AutoResolutionRule)
        rule.id = uuid4()
        rule.name = "Monday Rule"
        rule.preferred_source = PreferredSource.MONDAY

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_first.return_value = rule
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        can_resolve, matched_rule, resolution_type = await service.try_auto_resolve(
            entity_type="contact",
            entity_id=uuid4(),
            conflict_fields=["email"],
            npd_data={"email": "npd@test.com"},
            monday_data={"email": "monday@test.com"},
        )

        assert can_resolve is True
        assert matched_rule is not None
        assert resolution_type == "keep_monday"

    @pytest.mark.asyncio
    async def test_returns_false_when_no_rule_matches(self):
        """Test returns (False, None, None) when no rule matches."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_first.return_value = None
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        can_resolve, matched_rule, resolution_type = await service.try_auto_resolve(
            entity_type="contact",
            entity_id=uuid4(),
            conflict_fields=["email"],
            npd_data={},
            monday_data={},
        )

        assert can_resolve is False
        assert matched_rule is None
        assert resolution_type is None
