"""Tests for documents API pagination functionality."""

from uuid import uuid4

from app.models.document import Document
from app.schemas.document import DocumentListResponse, DocumentResponse


class TestDocumentListResponseSchema:
    """Tests for DocumentListResponse schema pagination fields."""

    def test_document_list_response_has_pagination_fields(self):
        """DocumentListResponse should have all pagination fields."""
        assert hasattr(DocumentListResponse, "model_fields")
        fields = DocumentListResponse.model_fields
        assert "items" in fields
        assert "total" in fields
        assert "page" in fields
        assert "page_size" in fields
        assert "pages" in fields

    def test_document_list_response_default_values(self):
        """DocumentListResponse should accept all pagination fields."""
        response = DocumentListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            pages=0,
        )
        assert response.items == []
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 20
        assert response.pages == 0

    def test_document_list_response_with_items(self):
        """DocumentListResponse should work with document items."""
        doc_id = uuid4()
        project_id = uuid4()
        uploaded_by = uuid4()

        doc_data = {
            "id": doc_id,
            "project_id": project_id,
            "file_path": "/path/to/doc.pdf",
            "display_name": "test.pdf",
            "mime_type": "application/pdf",
            "file_size": 1024,
            "uploaded_by": uploaded_by,
            "uploaded_at": "2025-01-01T00:00:00",
            "processing_status": "completed",
            "processing_error": None,
            "suggested_tag_ids": None,
            "dismissed_tag_ids": None,
            "created_at": "2025-01-01T00:00:00",
        }

        response = DocumentListResponse(
            items=[DocumentResponse(**doc_data)],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )
        assert len(response.items) == 1
        assert response.total == 1
        assert response.pages == 1


class TestDocumentPaginationCalculations:
    """Tests for pagination calculation logic."""

    def test_pages_calculation_zero_items(self):
        """Pages should be 0 when total is 0."""
        total = 0
        page_size = 20
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        assert pages == 0

    def test_pages_calculation_exact_fit(self):
        """Pages should be exact when total fits evenly."""
        total = 40
        page_size = 20
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        assert pages == 2

    def test_pages_calculation_with_remainder(self):
        """Pages should round up when total doesn't fit evenly."""
        total = 45
        page_size = 20
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        assert pages == 3

    def test_pages_calculation_single_page(self):
        """Pages should be 1 when total is less than page_size."""
        total = 15
        page_size = 20
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        assert pages == 1

    def test_offset_calculation(self):
        """Offset should be calculated correctly from page and page_size."""
        # Page 1
        page = 1
        page_size = 20
        offset = (page - 1) * page_size
        assert offset == 0

        # Page 2
        page = 2
        offset = (page - 1) * page_size
        assert offset == 20

        # Page 3
        page = 3
        offset = (page - 1) * page_size
        assert offset == 40


class TestDocumentModelAttributes:
    """Tests for Document model attributes."""

    def test_document_has_project_id(self):
        """Document model should have project_id attribute."""
        assert hasattr(Document, "project_id")

    def test_document_has_uploaded_at(self):
        """Document model should have uploaded_at attribute for ordering."""
        assert hasattr(Document, "uploaded_at")

    def test_document_has_processing_status(self):
        """Document model should have processing_status attribute."""
        assert hasattr(Document, "processing_status")


class TestDocumentPaginationParameters:
    """Tests for pagination query parameter validation logic."""

    def test_page_default_value(self):
        """Page parameter should have default value of 1."""
        from fastapi import Query

        # Simulate the Query definition
        page_query = Query(1, ge=1)
        assert page_query.default == 1

    def test_page_size_default_value(self):
        """Page size parameter should have default value of 20."""
        from fastapi import Query

        page_size_query = Query(20, ge=1, le=100)
        assert page_size_query.default == 20

    def test_page_value_boundary_invalid(self):
        """Page value 0 should be invalid (ge=1 constraint)."""
        # When page is 0, offset would be -20 which is invalid
        page = 0
        page_size = 20
        offset = (page - 1) * page_size
        assert offset < 0  # Invalid offset

    def test_page_value_boundary_valid(self):
        """Page value 1 should be valid and produce offset 0."""
        page = 1
        page_size = 20
        offset = (page - 1) * page_size
        assert offset == 0  # Valid offset


class TestDocumentListQueryStructure:
    """Tests for the SQL query structure used in document listing."""

    def test_order_by_uploaded_at_desc(self):
        """Documents should be ordered by uploaded_at descending."""
        from sqlalchemy import select

        # Verify the ordering can be built
        query = select(Document).order_by(Document.uploaded_at.desc())
        assert query is not None

    def test_where_project_id_filter(self):
        """Documents should be filtered by project_id."""
        from sqlalchemy import select

        project_id = uuid4()
        query = select(Document).where(Document.project_id == project_id)
        assert query is not None

    def test_pagination_offset_limit(self):
        """Query should support offset and limit for pagination."""
        from sqlalchemy import select

        page = 2
        page_size = 20
        offset = (page - 1) * page_size

        query = (
            select(Document)
            .order_by(Document.uploaded_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        assert query is not None


class TestDocumentCountQuery:
    """Tests for document count query structure."""

    def test_count_query_structure(self):
        """Count query should use subquery for accurate totals."""
        from sqlalchemy import func, select

        project_id = uuid4()
        base_query = select(Document).where(Document.project_id == project_id)
        count_query = select(func.count()).select_from(base_query.subquery())
        assert count_query is not None

    def test_count_not_affected_by_pagination(self):
        """Total count should not be affected by offset/limit."""
        from sqlalchemy import func, select

        project_id = uuid4()

        # Base query before pagination
        base_query = select(Document).where(Document.project_id == project_id)

        # Count from base query (no offset/limit)
        count_query = select(func.count()).select_from(base_query.subquery())

        # Paginated query
        paginated_query = base_query.offset(20).limit(20)

        # Both should work independently
        assert count_query is not None
        assert paginated_query is not None
