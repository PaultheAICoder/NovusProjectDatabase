"""Tests for search service and search_vector model definitions."""

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
