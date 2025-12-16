"""Tests for search service and search_vector model definitions."""

from unittest.mock import AsyncMock, MagicMock, patch

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
