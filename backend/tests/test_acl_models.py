"""Tests for ACL data models (Team, TeamMember, ProjectPermission, visibility)."""

import pytest
from pydantic import ValidationError

from app.models.project import Project
from app.models.project_permission import (
    PermissionLevel,
    ProjectPermission,
    ProjectVisibility,
)
from app.models.team import Team, TeamMember
from app.schemas.project_permission import (
    ProjectPermissionCreate,
    ProjectPermissionResponse,
    ProjectPermissionUpdate,
    ProjectVisibilityUpdate,
)
from app.schemas.team import (
    TeamCreate,
    TeamDetailResponse,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
)


class TestPermissionLevelEnum:
    """Tests for PermissionLevel enum."""

    def test_all_permission_levels_exist(self) -> None:
        """Verify all expected permission levels are defined."""
        expected = ["viewer", "editor", "owner"]
        actual = [p.value for p in PermissionLevel]
        assert set(expected) == set(actual)

    def test_permission_level_is_string_enum(self) -> None:
        """Verify PermissionLevel values are strings."""
        assert isinstance(PermissionLevel.VIEWER.value, str)
        assert isinstance(PermissionLevel.EDITOR.value, str)
        assert isinstance(PermissionLevel.OWNER.value, str)

    def test_permission_level_count(self) -> None:
        """Verify the count of permission levels."""
        assert len(PermissionLevel) == 3


class TestProjectVisibilityEnum:
    """Tests for ProjectVisibility enum."""

    def test_all_visibility_values_exist(self) -> None:
        """Verify all expected visibility values are defined."""
        expected = ["public", "restricted"]
        actual = [v.value for v in ProjectVisibility]
        assert set(expected) == set(actual)

    def test_visibility_is_string_enum(self) -> None:
        """Verify ProjectVisibility values are strings."""
        assert isinstance(ProjectVisibility.PUBLIC.value, str)
        assert isinstance(ProjectVisibility.RESTRICTED.value, str)

    def test_visibility_count(self) -> None:
        """Verify the count of visibility values."""
        assert len(ProjectVisibility) == 2


class TestTeamModel:
    """Tests for Team SQLAlchemy model."""

    def test_team_has_required_attributes(self) -> None:
        """Verify Team model has all required attributes."""
        assert hasattr(Team, "id")
        assert hasattr(Team, "name")
        assert hasattr(Team, "azure_ad_group_id")
        assert hasattr(Team, "description")
        assert hasattr(Team, "created_at")
        assert hasattr(Team, "updated_at")
        assert hasattr(Team, "members")

    def test_team_tablename(self) -> None:
        """Verify Team table name is correct."""
        assert Team.__tablename__ == "teams"


class TestTeamMemberModel:
    """Tests for TeamMember SQLAlchemy model."""

    def test_team_member_has_required_attributes(self) -> None:
        """Verify TeamMember model has all required attributes."""
        assert hasattr(TeamMember, "id")
        assert hasattr(TeamMember, "team_id")
        assert hasattr(TeamMember, "user_id")
        assert hasattr(TeamMember, "synced_at")
        assert hasattr(TeamMember, "team")
        assert hasattr(TeamMember, "user")

    def test_team_member_tablename(self) -> None:
        """Verify TeamMember table name is correct."""
        assert TeamMember.__tablename__ == "team_members"


class TestProjectPermissionModel:
    """Tests for ProjectPermission SQLAlchemy model."""

    def test_project_permission_has_required_attributes(self) -> None:
        """Verify ProjectPermission model has all required attributes."""
        assert hasattr(ProjectPermission, "id")
        assert hasattr(ProjectPermission, "project_id")
        assert hasattr(ProjectPermission, "user_id")
        assert hasattr(ProjectPermission, "team_id")
        assert hasattr(ProjectPermission, "permission_level")
        assert hasattr(ProjectPermission, "granted_by")
        assert hasattr(ProjectPermission, "granted_at")

    def test_project_permission_tablename(self) -> None:
        """Verify ProjectPermission table name is correct."""
        assert ProjectPermission.__tablename__ == "project_permissions"

    def test_project_permission_has_relationships(self) -> None:
        """Verify ProjectPermission has required relationships."""
        assert hasattr(ProjectPermission, "project")
        assert hasattr(ProjectPermission, "user")
        assert hasattr(ProjectPermission, "team")
        assert hasattr(ProjectPermission, "granter")


class TestProjectVisibilityField:
    """Tests for visibility field on Project model."""

    def test_project_has_visibility_attribute(self) -> None:
        """Verify Project model has visibility attribute."""
        assert hasattr(Project, "visibility")

    def test_project_has_permissions_relationship(self) -> None:
        """Verify Project model has permissions relationship."""
        assert hasattr(Project, "permissions")


class TestTeamSchemas:
    """Tests for Team Pydantic schemas."""

    def test_team_create_requires_azure_ad_group_id(self) -> None:
        """Verify TeamCreate requires azure_ad_group_id."""
        with pytest.raises(ValidationError):
            TeamCreate(name="Test Team")  # Missing azure_ad_group_id

    def test_team_create_valid(self) -> None:
        """Verify TeamCreate accepts valid data."""
        team = TeamCreate(
            name="Engineering",
            azure_ad_group_id="12345-abcde-67890",
            description="Engineering team",
        )
        assert team.name == "Engineering"
        assert team.azure_ad_group_id == "12345-abcde-67890"
        assert team.description == "Engineering team"

    def test_team_update_all_fields_optional(self) -> None:
        """Verify TeamUpdate has all optional fields."""
        team = TeamUpdate()
        assert team.name is None
        assert team.description is None

    def test_team_response_has_model_config(self) -> None:
        """Verify TeamResponse has from_attributes config."""
        assert TeamResponse.model_config.get("from_attributes") is True

    def test_team_detail_response_includes_members(self) -> None:
        """Verify TeamDetailResponse inherits from TeamResponse and has members."""
        # Check inheritance
        assert issubclass(TeamDetailResponse, TeamResponse)


class TestProjectPermissionSchemas:
    """Tests for ProjectPermission Pydantic schemas."""

    def test_permission_create_requires_user_or_team(self) -> None:
        """Verify ProjectPermissionCreate requires user_id or team_id."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectPermissionCreate(permission_level=PermissionLevel.VIEWER)
        assert "user_id or team_id must be provided" in str(exc_info.value)

    def test_permission_create_rejects_both_user_and_team(self) -> None:
        """Verify ProjectPermissionCreate rejects both user_id and team_id."""
        from uuid import uuid4

        with pytest.raises(ValidationError) as exc_info:
            ProjectPermissionCreate(
                user_id=uuid4(),
                team_id=uuid4(),
                permission_level=PermissionLevel.VIEWER,
            )
        assert "Only one of user_id or team_id can be provided" in str(exc_info.value)

    def test_permission_create_with_user_id_valid(self) -> None:
        """Verify ProjectPermissionCreate works with user_id."""
        from uuid import uuid4

        user_id = uuid4()
        perm = ProjectPermissionCreate(
            user_id=user_id,
            permission_level=PermissionLevel.EDITOR,
        )
        assert perm.user_id == user_id
        assert perm.team_id is None
        assert perm.permission_level == PermissionLevel.EDITOR

    def test_permission_create_with_team_id_valid(self) -> None:
        """Verify ProjectPermissionCreate works with team_id."""
        from uuid import uuid4

        team_id = uuid4()
        perm = ProjectPermissionCreate(
            team_id=team_id,
            permission_level=PermissionLevel.OWNER,
        )
        assert perm.team_id == team_id
        assert perm.user_id is None
        assert perm.permission_level == PermissionLevel.OWNER

    def test_permission_update_only_permission_level(self) -> None:
        """Verify ProjectPermissionUpdate only has permission_level."""
        update = ProjectPermissionUpdate(permission_level=PermissionLevel.VIEWER)
        assert update.permission_level == PermissionLevel.VIEWER

    def test_visibility_update_schema(self) -> None:
        """Verify ProjectVisibilityUpdate works correctly."""
        update = ProjectVisibilityUpdate(visibility=ProjectVisibility.RESTRICTED)
        assert update.visibility == ProjectVisibility.RESTRICTED

    def test_permission_response_has_model_config(self) -> None:
        """Verify ProjectPermissionResponse has from_attributes config."""
        assert ProjectPermissionResponse.model_config.get("from_attributes") is True


class TestTeamMemberSchemas:
    """Tests for TeamMember Pydantic schemas."""

    def test_team_member_response_has_model_config(self) -> None:
        """Verify TeamMemberResponse has from_attributes config."""
        assert TeamMemberResponse.model_config.get("from_attributes") is True
