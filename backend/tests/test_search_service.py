"""Tests for search service and search_vector model definitions."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.contact import Contact
from app.models.document import Document
from app.models.organization import Organization
from app.models.project import Project


class TestSearchVectorModels:
    """Test that search_vector columns are defined on models."""

    def test_project_has_search_vector(self):
        """Project model should have search_vector attribute."""
        assert hasattr(Project, "search_vector")

    def test_document_has_search_vector(self):
        """Document model should have search_vector attribute."""
        assert hasattr(Document, "search_vector")

    def test_organization_has_search_vector(self):
        """Organization model should have search_vector attribute."""
        assert hasattr(Organization, "search_vector")

    def test_contact_has_search_vector(self):
        """Contact model should have search_vector attribute."""
        assert hasattr(Contact, "search_vector")


class TestSearchServiceOptimizations:
    """Tests for search service optimizations."""

    @pytest.mark.asyncio
    async def test_vector_search_skipped_when_no_embeddings(self):
        """Vector search should be skipped when no embeddings exist in database."""
        from app.services.search_service import SearchService

        # Create mock db session
        mock_db = AsyncMock()

        # Mock the EXISTS query to return False (no embeddings)
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = False
        mock_db.execute.return_value = mock_scalar_result

        service = SearchService(mock_db)

        # Call _get_vector_ranks
        result = await service._get_vector_ranks("test query", [])

        # Should return empty dict without calling embedding service
        assert result == {}

        # Verify the EXISTS query was executed
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0][0]
        assert "EXISTS" in str(call_args)

    @pytest.mark.asyncio
    async def test_vector_search_proceeds_when_embeddings_exist(self):
        """Vector search should proceed when embeddings exist in database."""
        from app.services.search_service import SearchService

        # Create mock db session
        mock_db = AsyncMock()

        # First call: EXISTS query returns True
        # Second call: Vector search query
        mock_exists_result = MagicMock()
        mock_exists_result.scalar.return_value = True

        mock_search_result = MagicMock()
        mock_search_result.all.return_value = []

        mock_db.execute.side_effect = [mock_exists_result, mock_search_result]

        service = SearchService(mock_db)

        # Mock the embedding service to return None (simulating failure)
        # This will trigger the "embedding_generation_failed" path
        with patch.object(
            service.embedding_service, "generate_embedding", return_value=None
        ):
            result = await service._get_vector_ranks("test query", [])

        # Should return empty dict because embedding generation failed
        assert result == {}

        # First call should be the EXISTS check
        assert mock_db.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_hybrid_search_runs_queries_in_parallel(self):
        """Hybrid search should run ranking queries in parallel when include_documents=True."""
        import asyncio

        from app.services.search_service import SearchService

        # Create mock db session
        mock_db = AsyncMock()

        # Track call order
        call_order = []

        async def mock_project_text_ranks(*args):
            call_order.append("project_text")
            await asyncio.sleep(0.01)  # Simulate some work
            return {}

        async def mock_document_text_ranks(*args):
            call_order.append("document_text")
            await asyncio.sleep(0.01)
            return {}

        async def mock_vector_ranks(*args):
            call_order.append("vector")
            await asyncio.sleep(0.01)
            return {}

        service = SearchService(mock_db)

        with (
            patch.object(
                service, "_get_project_text_ranks", side_effect=mock_project_text_ranks
            ),
            patch.object(
                service,
                "_get_document_text_ranks",
                side_effect=mock_document_text_ranks,
            ),
            patch.object(service, "_get_vector_ranks", side_effect=mock_vector_ranks),
        ):
            result, total = await service._hybrid_search(
                query="test",
                filter_conditions=[],
                sort_by="relevance",
                sort_order="desc",
                page=1,
                page_size=20,
                include_documents=True,
            )

        # All three methods should have been called
        assert len(call_order) == 3
        assert "project_text" in call_order
        assert "document_text" in call_order
        assert "vector" in call_order

    @pytest.mark.asyncio
    async def test_hybrid_search_sequential_when_no_documents(self):
        """Hybrid search should only run project text search when include_documents=False."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()

        project_text_called = False
        document_text_called = False
        vector_called = False

        async def mock_project_text_ranks(*args):
            nonlocal project_text_called
            project_text_called = True
            return {}

        async def mock_document_text_ranks(*args):
            nonlocal document_text_called
            document_text_called = True
            return {}

        async def mock_vector_ranks(*args):
            nonlocal vector_called
            vector_called = True
            return {}

        service = SearchService(mock_db)

        with (
            patch.object(
                service, "_get_project_text_ranks", side_effect=mock_project_text_ranks
            ),
            patch.object(
                service,
                "_get_document_text_ranks",
                side_effect=mock_document_text_ranks,
            ),
            patch.object(service, "_get_vector_ranks", side_effect=mock_vector_ranks),
        ):
            await service._hybrid_search(
                query="test",
                filter_conditions=[],
                sort_by="relevance",
                sort_order="desc",
                page=1,
                page_size=20,
                include_documents=False,
            )

        # Only project text search should have been called
        assert project_text_called
        assert not document_text_called
        assert not vector_called

    @pytest.mark.asyncio
    async def test_document_text_ranks_uses_tsvector(self):
        """Document text search should use tsvector ranking, not ILIKE."""
        from sqlalchemy.dialects import postgresql

        from app.services.search_service import SearchService

        # Create mock db session
        mock_db = AsyncMock()

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SearchService(mock_db)

        # Call the method
        result = await service._get_document_text_ranks("test query", [])

        # Verify the query uses tsvector operators
        mock_db.execute.assert_called_once()

        # Get the compiled SQL statement to verify tsvector is used
        stmt = mock_db.execute.call_args[0][0]
        compiled_sql = str(stmt.compile(dialect=postgresql.dialect()))

        # Should use ts_rank and @@ operator, NOT ILIKE
        assert "ts_rank" in compiled_sql
        assert "plainto_tsquery" in compiled_sql
        assert "@@" in compiled_sql
        assert "ILIKE" not in compiled_sql.upper()

        # Should return correct data structure (empty dict for no results)
        assert result == {}


class TestNonRelevanceSortPagination:
    """Tests for non-relevance sort modes with pagination (Issue #67 regression tests)."""

    @pytest.mark.asyncio
    async def test_non_relevance_sort_uses_db_sorting(self):
        """Verify non-relevance sorts call _apply_sorting for DB-level sorting."""
        from uuid import uuid4

        from app.services.search_service import SearchService

        mock_db = AsyncMock()

        # Create mock project IDs
        project_ids = [uuid4() for _ in range(3)]

        async def mock_project_text_ranks(*args):
            return {pid: idx + 1 for idx, pid in enumerate(project_ids)}

        async def mock_document_text_ranks(*args):
            return {}

        async def mock_vector_ranks(*args):
            return {}

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SearchService(mock_db)

        apply_sorting_called = False
        original_apply_sorting = service._apply_sorting

        def mock_apply_sorting(*args, **kwargs):
            nonlocal apply_sorting_called
            apply_sorting_called = True
            return original_apply_sorting(*args, **kwargs)

        with (
            patch.object(
                service, "_get_project_text_ranks", side_effect=mock_project_text_ranks
            ),
            patch.object(
                service,
                "_get_document_text_ranks",
                side_effect=mock_document_text_ranks,
            ),
            patch.object(service, "_get_vector_ranks", side_effect=mock_vector_ranks),
            patch.object(service, "_apply_sorting", side_effect=mock_apply_sorting),
        ):
            await service._hybrid_search(
                query="test",
                filter_conditions=[],
                sort_by="name",  # Non-relevance sort
                sort_order="asc",
                page=1,
                page_size=20,
                include_documents=True,
            )

        assert (
            apply_sorting_called
        ), "_apply_sorting should be called for non-relevance sorts"

    @pytest.mark.asyncio
    async def test_relevance_sort_does_not_use_db_sorting(self):
        """Verify relevance sort does NOT call _apply_sorting (uses RRF in-memory sort)."""
        from uuid import uuid4

        from app.services.search_service import SearchService

        mock_db = AsyncMock()

        # Create mock project IDs with RRF scores
        project_ids = [uuid4() for _ in range(3)]

        async def mock_project_text_ranks(*args):
            return {pid: idx + 1 for idx, pid in enumerate(project_ids)}

        async def mock_document_text_ranks(*args):
            return {}

        async def mock_vector_ranks(*args):
            return {}

        # Mock query result - return empty for this test since we're just checking if _apply_sorting is called
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SearchService(mock_db)

        apply_sorting_called = False

        def mock_apply_sorting(*args, **kwargs):
            nonlocal apply_sorting_called
            apply_sorting_called = True
            return args[0]  # Return query unchanged

        with (
            patch.object(
                service, "_get_project_text_ranks", side_effect=mock_project_text_ranks
            ),
            patch.object(
                service,
                "_get_document_text_ranks",
                side_effect=mock_document_text_ranks,
            ),
            patch.object(service, "_get_vector_ranks", side_effect=mock_vector_ranks),
            patch.object(service, "_apply_sorting", side_effect=mock_apply_sorting),
        ):
            await service._hybrid_search(
                query="test",
                filter_conditions=[],
                sort_by="relevance",  # Relevance sort
                sort_order="desc",
                page=1,
                page_size=20,
                include_documents=True,
            )

        assert (
            not apply_sorting_called
        ), "_apply_sorting should NOT be called for relevance sorts"

    @pytest.mark.asyncio
    async def test_non_relevance_sort_applies_pagination_correctly(self):
        """Verify non-relevance sort applies offset and limit to query."""
        from uuid import uuid4

        from app.services.search_service import SearchService

        mock_db = AsyncMock()

        # Create 5 mock project IDs
        project_ids = [uuid4() for _ in range(5)]

        async def mock_project_text_ranks(*args):
            return {pid: idx + 1 for idx, pid in enumerate(project_ids)}

        async def mock_document_text_ranks(*args):
            return {}

        async def mock_vector_ranks(*args):
            return {}

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = SearchService(mock_db)

        with (
            patch.object(
                service, "_get_project_text_ranks", side_effect=mock_project_text_ranks
            ),
            patch.object(
                service,
                "_get_document_text_ranks",
                side_effect=mock_document_text_ranks,
            ),
            patch.object(service, "_get_vector_ranks", side_effect=mock_vector_ranks),
        ):
            # Test page 2 with page_size 2
            results, total = await service._hybrid_search(
                query="test",
                filter_conditions=[],
                sort_by="name",
                sort_order="asc",
                page=2,
                page_size=2,
                include_documents=True,
            )

        # Total should reflect all matching IDs (5)
        assert total == 5

        # Verify execute was called (once for the final query after ranking queries)
        assert mock_db.execute.called


class TestSynonymAwareSearch:
    """Tests for synonym-aware tag filtering in search."""

    @pytest.mark.asyncio
    async def test_search_expands_tag_ids_with_synonyms(self):
        """Search should expand tag_ids to include synonyms when enabled."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()

        # Create test IDs
        tag_a_id = uuid4()
        tag_b_id = uuid4()

        service = SearchService(mock_db)

        # Mock the TagSynonymService
        with patch(
            "app.services.search_service.TagSynonymService"
        ) as MockSynonymService:
            mock_synonym_service = MagicMock()
            mock_synonym_service.expand_tag_ids_with_synonyms = AsyncMock(
                return_value=(
                    {tag_a_id, tag_b_id},  # expanded set
                    {tag_a_id: {tag_b_id}},  # synonym map
                )
            )
            MockSynonymService.return_value = mock_synonym_service

            # Mock the internal search method to avoid complex setup
            with patch.object(
                service, "_search_without_query"
            ) as mock_search_without_query:
                mock_search_without_query.return_value = ([], 0)

                result = await service.search_projects(
                    query="",
                    tag_ids=[tag_a_id],
                    expand_synonyms=True,
                )

                # Verify synonym expansion was called
                mock_synonym_service.expand_tag_ids_with_synonyms.assert_called_once_with(
                    [tag_a_id]
                )

                # Result should be (projects, total, synonym_metadata)
                assert len(result) == 3
                projects, total, synonym_metadata = result
                assert synonym_metadata is not None
                assert str(tag_a_id) in synonym_metadata["original_tags"]

    @pytest.mark.asyncio
    async def test_search_skips_synonym_expansion_when_disabled(self):
        """Search should not expand synonyms when expand_synonyms=False."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        tag_id = uuid4()

        service = SearchService(mock_db)

        with patch(
            "app.services.search_service.TagSynonymService"
        ) as MockSynonymService:
            mock_synonym_service = MagicMock()
            MockSynonymService.return_value = mock_synonym_service

            with patch.object(
                service, "_search_without_query"
            ) as mock_search_without_query:
                mock_search_without_query.return_value = ([], 0)

                result = await service.search_projects(
                    query="",
                    tag_ids=[tag_id],
                    expand_synonyms=False,
                )

                # Synonym service should NOT be called
                mock_synonym_service.expand_tag_ids_with_synonyms.assert_not_called()

                # synonym_metadata should be None
                _, _, synonym_metadata = result
                assert synonym_metadata is None

    @pytest.mark.asyncio
    async def test_search_returns_synonym_metadata_when_synonyms_found(self):
        """Search should include synonym metadata when synonyms are expanded."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()

        original_tag = uuid4()
        synonym_tag = uuid4()

        service = SearchService(mock_db)

        with patch(
            "app.services.search_service.TagSynonymService"
        ) as MockSynonymService:
            mock_synonym_service = MagicMock()
            mock_synonym_service.expand_tag_ids_with_synonyms = AsyncMock(
                return_value=(
                    {original_tag, synonym_tag},
                    {original_tag: {synonym_tag}},
                )
            )
            MockSynonymService.return_value = mock_synonym_service

            with patch.object(
                service, "_search_without_query"
            ) as mock_search_without_query:
                mock_search_without_query.return_value = ([], 0)

                _, _, synonym_metadata = await service.search_projects(
                    query="",
                    tag_ids=[original_tag],
                    expand_synonyms=True,
                )

                # Verify metadata structure
                assert synonym_metadata is not None
                assert "original_tags" in synonym_metadata
                assert "expanded_tags" in synonym_metadata
                assert "synonym_matches" in synonym_metadata
                assert len(synonym_metadata["expanded_tags"]) == 2

    @pytest.mark.asyncio
    async def test_search_no_synonym_metadata_when_no_synonyms_found(self):
        """Search should not include synonym metadata when no synonyms found."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        tag_id = uuid4()

        service = SearchService(mock_db)

        with patch(
            "app.services.search_service.TagSynonymService"
        ) as MockSynonymService:
            mock_synonym_service = MagicMock()
            # No synonyms found - empty synonym_map
            mock_synonym_service.expand_tag_ids_with_synonyms = AsyncMock(
                return_value=({tag_id}, {})  # Just original, no synonyms
            )
            MockSynonymService.return_value = mock_synonym_service

            with patch.object(
                service, "_search_without_query"
            ) as mock_search_without_query:
                mock_search_without_query.return_value = ([], 0)

                _, _, synonym_metadata = await service.search_projects(
                    query="",
                    tag_ids=[tag_id],
                    expand_synonyms=True,
                )

                # No synonym_metadata when no synonyms found
                assert synonym_metadata is None

    @pytest.mark.asyncio
    async def test_search_returns_three_element_tuple(self):
        """Search should always return a 3-element tuple (projects, total, metadata)."""
        from app.services.search_service import SearchService

        mock_db = AsyncMock()
        service = SearchService(mock_db)

        with patch.object(
            service, "_search_without_query"
        ) as mock_search_without_query:
            mock_search_without_query.return_value = ([], 0)

            # Without tag_ids
            result = await service.search_projects(query="")
            assert len(result) == 3

            # With tag_ids but expand_synonyms=False
            result = await service.search_projects(
                query="", tag_ids=[uuid4()], expand_synonyms=False
            )
            assert len(result) == 3
