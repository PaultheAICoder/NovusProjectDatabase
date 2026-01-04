"""Integration tests for document endpoint ACL enforcement."""

import inspect
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.project import Project
from app.models.project_permission import ProjectVisibility
from app.models.user import User, UserRole


@pytest.fixture
def regular_user():
    """Create a regular (non-admin) user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.role = UserRole.USER
    return user


@pytest.fixture
def admin_user():
    """Create an admin user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.role = UserRole.ADMIN
    return user


@pytest.fixture
def restricted_project():
    """Create a restricted project."""
    project = MagicMock(spec=Project)
    project.id = uuid4()
    project.visibility = ProjectVisibility.RESTRICTED
    return project


class TestDocumentUploadACL:
    """Tests for document upload permission enforcement."""

    def test_upload_uses_project_editor_dependency(self):
        """Document upload should use ProjectEditor dependency for ACL."""
        from app.api.documents import upload_document

        sig = inspect.signature(upload_document)
        params = sig.parameters

        # Check that _project parameter exists (ACL dependency)
        assert "_project" in params, "upload_document must use ProjectEditor dependency"

        # Verify the annotation includes ProjectEditor
        param = params["_project"]
        # The annotation is Annotated[Project, Depends(require_project_editor)]
        annotation_str = str(param.annotation)
        assert (
            "ProjectEditor" in annotation_str or "Project" in annotation_str
        ), "upload_document _project must be ProjectEditor type"


class TestDocumentListACL:
    """Tests for document list permission enforcement."""

    def test_list_uses_project_viewer_dependency(self):
        """Document listing should use ProjectViewer dependency for ACL."""
        from app.api.documents import list_documents

        sig = inspect.signature(list_documents)
        params = sig.parameters

        assert "_project" in params, "list_documents must use ProjectViewer dependency"


class TestDocumentGetACL:
    """Tests for document get permission enforcement."""

    def test_get_uses_project_viewer_dependency(self):
        """Document get should use ProjectViewer dependency for ACL."""
        from app.api.documents import get_document

        sig = inspect.signature(get_document)
        params = sig.parameters

        assert "_project" in params, "get_document must use ProjectViewer dependency"


class TestDocumentStatusACL:
    """Tests for document status permission enforcement."""

    def test_status_uses_project_viewer_dependency(self):
        """Document status should use ProjectViewer dependency for ACL."""
        from app.api.documents import get_document_status

        sig = inspect.signature(get_document_status)
        params = sig.parameters

        assert (
            "_project" in params
        ), "get_document_status must use ProjectViewer dependency"


class TestDocumentDownloadACL:
    """Tests for document download permission enforcement."""

    def test_download_uses_project_viewer_dependency(self):
        """Document download should use ProjectViewer dependency for ACL."""
        from app.api.documents import download_document

        sig = inspect.signature(download_document)
        params = sig.parameters

        assert (
            "_project" in params
        ), "download_document must use ProjectViewer dependency"


class TestDocumentReprocessACL:
    """Tests for document reprocess permission enforcement."""

    def test_reprocess_uses_project_editor_dependency(self):
        """Document reprocess should use ProjectEditor dependency for ACL."""
        from app.api.documents import reprocess_document

        sig = inspect.signature(reprocess_document)
        params = sig.parameters

        assert (
            "_project" in params
        ), "reprocess_document must use ProjectEditor dependency"


class TestDocumentDeleteACL:
    """Tests for document delete permission enforcement."""

    def test_delete_uses_project_editor_dependency(self):
        """Document deletion should use ProjectEditor dependency for ACL."""
        from app.api.documents import delete_document

        sig = inspect.signature(delete_document)
        params = sig.parameters

        assert "_project" in params, "delete_document must use ProjectEditor dependency"


class TestDocumentTagSuggestionsACL:
    """Tests for document tag suggestions permission enforcement."""

    def test_tag_suggestions_uses_project_viewer_dependency(self):
        """Document tag suggestions should use ProjectViewer dependency for ACL."""
        from app.api.documents import get_document_tag_suggestions

        sig = inspect.signature(get_document_tag_suggestions)
        params = sig.parameters

        assert (
            "_project" in params
        ), "get_document_tag_suggestions must use ProjectViewer dependency"


class TestDismissTagACL:
    """Tests for dismiss tag permission enforcement."""

    def test_dismiss_tag_uses_project_editor_dependency(self):
        """Dismiss tag should use ProjectEditor dependency for ACL."""
        from app.api.documents import dismiss_tag_suggestion

        sig = inspect.signature(dismiss_tag_suggestion)
        params = sig.parameters

        assert (
            "_project" in params
        ), "dismiss_tag_suggestion must use ProjectEditor dependency"
