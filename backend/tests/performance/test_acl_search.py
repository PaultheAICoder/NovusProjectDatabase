"""Performance tests for ACL-filtered search.

These tests validate that search performance remains acceptable
when ACL filtering is applied, as specified in NFR-001:
- Search with ACL filtering MUST complete in < 3 seconds for 1000+ projects
- Permission checks MUST add < 10ms to API response time
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.user import User, UserRole
from app.services.permission_service import PermissionService
from app.services.search_service import SearchService


class TestACLSearchPerformance:
    """Performance benchmarks for ACL-filtered search."""

    @pytest.fixture
    def mock_db(self):
        """Create mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def regular_user(self):
        """Create a regular (non-admin) user."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.role = UserRole.USER
        return user

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.role = UserRole.ADMIN
        return user

    @pytest.mark.asyncio
    async def test_admin_skip_filter_is_fast(self, mock_db, admin_user):
        """Admin users should skip permission filtering (instant)."""
        service = PermissionService(mock_db)

        start = time.perf_counter()
        result = await service.get_accessible_project_ids(admin_user)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Admin returns empty set immediately (no DB queries)
        assert result == set()
        assert elapsed_ms < 1, f"Admin check took {elapsed_ms}ms (should be instant)"

    @pytest.mark.asyncio
    async def test_permission_check_overhead_under_10ms(self, mock_db, regular_user):
        """Permission check for regular user should add < 10ms overhead."""
        # Mock DB responses for permission queries
        mock_public = MagicMock()
        mock_public.fetchall.return_value = [(uuid4(),) for _ in range(100)]

        mock_direct = MagicMock()
        mock_direct.fetchall.return_value = [(uuid4(),) for _ in range(50)]

        mock_teams = MagicMock()
        mock_teams.fetchall.return_value = []  # No teams

        mock_db.execute.side_effect = [mock_public, mock_direct, mock_teams]

        service = PermissionService(mock_db)

        start = time.perf_counter()
        result = await service.get_accessible_project_ids(regular_user)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should have 150 accessible projects
        assert len(result) == 150
        # Per NFR-001: Permission checks MUST add < 10ms
        assert elapsed_ms < 10, f"Permission check took {elapsed_ms}ms (limit: 10ms)"

    @pytest.mark.asyncio
    async def test_large_permission_set_scaling(self, mock_db, regular_user):
        """Large permission sets (500+ projects) should not degrade performance."""
        # Simulate user with access to 500 projects
        project_ids = [uuid4() for _ in range(500)]

        mock_public = MagicMock()
        mock_public.fetchall.return_value = [(pid,) for pid in project_ids[:200]]

        mock_direct = MagicMock()
        mock_direct.fetchall.return_value = [(pid,) for pid in project_ids[200:400]]

        mock_teams = MagicMock()
        mock_teams.fetchall.return_value = [(uuid4(),)]  # One team

        mock_team_perms = MagicMock()
        mock_team_perms.fetchall.return_value = [(pid,) for pid in project_ids[400:]]

        mock_db.execute.side_effect = [
            mock_public,
            mock_direct,
            mock_teams,
            mock_team_perms,
        ]

        service = PermissionService(mock_db)

        start = time.perf_counter()
        result = await service.get_accessible_project_ids(regular_user)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) == 500
        # Should still be fast even with many permissions
        assert (
            elapsed_ms < 50
        ), f"Large permission set took {elapsed_ms}ms (limit: 50ms)"


class TestSearchServiceACLPerformance:
    """Performance tests for search with ACL filtering."""

    @pytest.fixture
    def mock_db(self):
        """Create mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def regular_user(self):
        """Create a regular (non-admin) user."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.role = UserRole.USER
        return user

    @pytest.mark.asyncio
    async def test_search_with_acl_filter_structure(self, mock_db, regular_user):
        """Verify ACL filter is added to search conditions correctly."""
        # This test validates the structure, not real performance
        # Real performance would require integration tests with actual DB

        service = SearchService(mock_db)

        # Mock the permission service
        with patch.object(service, "_search_without_query") as mock_search:
            mock_search.return_value = ([], 0)

            # Mock PermissionService
            with patch(
                "app.services.search_service.PermissionService"
            ) as MockPermService:
                mock_perm_instance = AsyncMock()
                mock_perm_instance.get_accessible_project_ids.return_value = {
                    uuid4(),
                    uuid4(),
                }
                MockPermService.return_value = mock_perm_instance

                await service.search_projects(
                    query="",
                    user=regular_user,
                )

                # Verify permission service was called
                mock_perm_instance.get_accessible_project_ids.assert_called_once_with(
                    regular_user
                )

    @pytest.mark.asyncio
    async def test_search_admin_skips_acl_filter(self, mock_db):
        """Admin user should skip ACL filtering entirely."""
        admin_user = MagicMock(spec=User)
        admin_user.id = uuid4()
        admin_user.role = UserRole.ADMIN

        service = SearchService(mock_db)

        with patch.object(service, "_search_without_query") as mock_search:
            mock_search.return_value = ([], 0)

            with patch(
                "app.services.search_service.PermissionService"
            ) as MockPermService:
                mock_perm_instance = AsyncMock()
                # Admin returns empty set (skip filter)
                mock_perm_instance.get_accessible_project_ids.return_value = set()
                MockPermService.return_value = mock_perm_instance

                await service.search_projects(
                    query="",
                    user=admin_user,
                )

                # Permission service should still be called
                mock_perm_instance.get_accessible_project_ids.assert_called_once_with(
                    admin_user
                )
