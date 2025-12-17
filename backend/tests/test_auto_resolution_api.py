"""Tests for auto-resolution API endpoint logic.

Tests the schema validation and service integration logic
for auto-resolution rule management.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.monday_sync import AutoResolutionRule, PreferredSource
from app.schemas.monday import (
    AutoResolutionRuleCreate,
    AutoResolutionRuleListResponse,
    AutoResolutionRuleReorderRequest,
    AutoResolutionRuleResponse,
    AutoResolutionRuleUpdate,
)
from app.services.auto_resolution_service import AutoResolutionService


class TestAutoResolutionSchemas:
    """Tests for auto-resolution Pydantic schemas."""

    def test_create_schema_valid(self):
        """Test valid create schema."""
        data = AutoResolutionRuleCreate(
            name="Test Rule",
            entity_type="contact",
            preferred_source=PreferredSource.NPD,
            is_enabled=True,
            priority=10,
        )
        assert data.name == "Test Rule"
        assert data.entity_type == "contact"
        assert data.preferred_source == PreferredSource.NPD

    def test_create_schema_all_entity_types(self):
        """Test all valid entity types."""
        for entity_type in ["contact", "organization", "*"]:
            data = AutoResolutionRuleCreate(
                name="Test Rule",
                entity_type=entity_type,
                preferred_source=PreferredSource.NPD,
            )
            assert data.entity_type == entity_type

    def test_create_schema_invalid_entity_type(self):
        """Test validation error for invalid entity_type."""
        with pytest.raises(ValidationError):
            AutoResolutionRuleCreate(
                name="Test Rule",
                entity_type="invalid",
                preferred_source=PreferredSource.NPD,
            )

    def test_create_schema_name_required(self):
        """Test name is required."""
        with pytest.raises(ValidationError):
            AutoResolutionRuleCreate(
                entity_type="contact",
                preferred_source=PreferredSource.NPD,
            )

    def test_update_schema_all_optional(self):
        """Test update schema allows partial updates."""
        data = AutoResolutionRuleUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.entity_type is None
        assert data.preferred_source is None

    def test_reorder_schema_requires_rule_ids(self):
        """Test reorder schema requires at least one rule_id."""
        with pytest.raises(ValidationError):
            AutoResolutionRuleReorderRequest(rule_ids=[])

    def test_reorder_schema_valid(self):
        """Test valid reorder schema."""
        rule_ids = [uuid4(), uuid4()]
        data = AutoResolutionRuleReorderRequest(rule_ids=rule_ids)
        assert len(data.rule_ids) == 2


class TestAutoResolutionServiceIntegration:
    """Integration tests for AutoResolutionService with endpoint logic."""

    @pytest.mark.asyncio
    async def test_list_rules_returns_list_response(self):
        """Test list_rules returns data for list response."""
        rule_id = uuid4()

        mock_rule = MagicMock(spec=AutoResolutionRule)
        mock_rule.id = rule_id
        mock_rule.name = "Test Rule"
        mock_rule.entity_type = "contact"
        mock_rule.field_name = "email"
        mock_rule.preferred_source = PreferredSource.NPD
        mock_rule.is_enabled = True
        mock_rule.priority = 10
        mock_rule.created_at = datetime.now(UTC)
        mock_rule.created_by_id = None

        mock_db = AsyncMock()
        mock_db.scalar.return_value = 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rule]
        mock_db.execute.return_value = mock_result

        service = AutoResolutionService(mock_db)
        rules, total = await service.list_rules()

        assert total == 1
        assert len(rules) == 1
        assert rules[0].name == "Test Rule"

        # Validate response schema works
        response = AutoResolutionRuleListResponse(
            rules=[AutoResolutionRuleResponse.model_validate(r) for r in rules],
            total=total,
        )
        assert response.total == 1

    @pytest.mark.asyncio
    async def test_create_rule_from_schema(self):
        """Test creating rule from create schema."""
        mock_db = AsyncMock()

        create_data = AutoResolutionRuleCreate(
            name="New Rule",
            entity_type="contact",
            field_name="email",
            preferred_source=PreferredSource.NPD,
            is_enabled=True,
            priority=5,
        )

        service = AutoResolutionService(mock_db)
        rule = await service.create(
            name=create_data.name,
            entity_type=create_data.entity_type,
            field_name=create_data.field_name,
            preferred_source=create_data.preferred_source,
            is_enabled=create_data.is_enabled,
            priority=create_data.priority,
            created_by_id=uuid4(),
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        assert rule.name == "New Rule"

    @pytest.mark.asyncio
    async def test_update_rule_from_schema(self):
        """Test updating rule from update schema."""
        rule_id = uuid4()
        mock_rule = MagicMock(spec=AutoResolutionRule)
        mock_rule.id = rule_id
        mock_rule.name = "Old Name"
        mock_rule.entity_type = "contact"
        mock_rule.field_name = None
        mock_rule.preferred_source = PreferredSource.NPD
        mock_rule.is_enabled = True
        mock_rule.priority = 5

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rule
        mock_db.execute.return_value = mock_result

        update_data = AutoResolutionRuleUpdate(
            name="Updated Name",
            is_enabled=False,
        )

        service = AutoResolutionService(mock_db)
        result = await service.update(
            rule_id=rule_id,
            name=update_data.name,
            entity_type=update_data.entity_type,
            field_name=update_data.field_name,
            preferred_source=update_data.preferred_source,
            is_enabled=update_data.is_enabled,
            priority=update_data.priority,
        )

        assert result is not None
        assert mock_rule.name == "Updated Name"
        assert mock_rule.is_enabled is False

    @pytest.mark.asyncio
    async def test_reorder_from_schema(self):
        """Test reordering rules from schema."""
        rule_id1 = uuid4()
        rule_id2 = uuid4()

        mock_rule1 = MagicMock(spec=AutoResolutionRule)
        mock_rule1.id = rule_id1
        mock_rule1.priority = 1
        mock_rule1.name = "Rule 1"
        mock_rule1.entity_type = "contact"
        mock_rule1.field_name = None
        mock_rule1.preferred_source = PreferredSource.NPD
        mock_rule1.is_enabled = True
        mock_rule1.created_at = datetime.now(UTC)
        mock_rule1.created_by_id = None

        mock_rule2 = MagicMock(spec=AutoResolutionRule)
        mock_rule2.id = rule_id2
        mock_rule2.priority = 2
        mock_rule2.name = "Rule 2"
        mock_rule2.entity_type = "contact"
        mock_rule2.field_name = None
        mock_rule2.preferred_source = PreferredSource.NPD
        mock_rule2.is_enabled = True
        mock_rule2.created_at = datetime.now(UTC)
        mock_rule2.created_by_id = None

        mock_db = AsyncMock()
        # Mock for reorder update calls
        mock_db.execute.return_value = MagicMock()
        # Mock for list_rules call after reorder
        mock_db.scalar.return_value = 2
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_rule2, mock_rule1]
        mock_db.execute.return_value = mock_result

        reorder_data = AutoResolutionRuleReorderRequest(
            rule_ids=[rule_id2, rule_id1]  # Swap order
        )

        service = AutoResolutionService(mock_db)
        rules = await service.reorder(reorder_data.rule_ids)

        # Should have called flush after updates
        mock_db.flush.assert_called()
        assert len(rules) == 2


class TestAutoResolutionResponseSchema:
    """Tests for response schema validation."""

    def test_response_from_rule_model(self):
        """Test creating response from rule model."""
        rule = MagicMock(spec=AutoResolutionRule)
        rule.id = uuid4()
        rule.name = "Test Rule"
        rule.entity_type = "contact"
        rule.field_name = "email"
        rule.preferred_source = PreferredSource.NPD
        rule.is_enabled = True
        rule.priority = 10
        rule.created_at = datetime.now(UTC)
        rule.created_by_id = None

        response = AutoResolutionRuleResponse.model_validate(rule)

        assert response.name == "Test Rule"
        assert response.entity_type == "contact"
        assert response.field_name == "email"
        assert response.preferred_source == PreferredSource.NPD
        assert response.is_enabled is True
        assert response.priority == 10
