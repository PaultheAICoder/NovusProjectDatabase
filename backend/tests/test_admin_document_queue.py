"""Tests for admin document queue management endpoints and service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.document_queue import (
    DocumentProcessingQueue,
    DocumentQueueOperation,
    DocumentQueueStatus,
)
from app.schemas.document_queue import (
    DocumentQueueItemResponse,
    DocumentQueueListResponse,
    DocumentQueueStatsResponse,
)
from app.services.document_queue_service import DocumentQueueService


class TestDocumentQueueServiceGetAllItems:
    """Tests for DocumentQueueService.get_all_items method."""

    @pytest.mark.asyncio
    async def test_get_all_items_returns_paginated_results(self):
        """Test that get_all_items returns paginated queue items."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.PENDING
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 1
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = None
        mock_queue_item.next_retry = now + timedelta(minutes=5)
        mock_queue_item.created_at = now
        mock_queue_item.started_at = None
        mock_queue_item.completed_at = None

        mock_db = AsyncMock()
        mock_db.scalar.return_value = 1
        mock_result = MagicMock()
        # get_all_items returns tuples of (queue_item, document_name)
        mock_result.all.return_value = [(mock_queue_item, "test_document.pdf")]
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        items, total = await service.get_all_items(page=1, page_size=20)

        assert total == 1
        assert len(items) == 1
        assert items[0][0].document_id == document_id
        assert items[0][1] == "test_document.pdf"

    @pytest.mark.asyncio
    async def test_get_all_items_filters_by_status(self):
        """Test that status filter is applied correctly."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        items, total = await service.get_all_items(
            page=1,
            page_size=20,
            status=DocumentQueueStatus.FAILED,
        )

        assert total == 0
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_get_all_items_pagination(self):
        """Test that pagination works correctly."""
        mock_db = AsyncMock()
        mock_db.scalar.return_value = 50  # Total 50 items
        now = datetime.now(UTC)

        mock_items = []
        for _ in range(10):
            mock_item = MagicMock(spec=DocumentProcessingQueue)
            mock_item.id = uuid4()
            mock_item.document_id = uuid4()
            mock_item.status = DocumentQueueStatus.PENDING
            mock_item.operation = DocumentQueueOperation.PROCESS
            mock_item.attempts = 0
            mock_item.max_attempts = 5
            mock_item.error_message = None
            mock_item.next_retry = now
            mock_item.created_at = now
            mock_item.started_at = None
            mock_item.completed_at = None
            mock_items.append((mock_item, f"document_{_}.pdf"))

        mock_result = MagicMock()
        mock_result.all.return_value = mock_items
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        items, total = await service.get_all_items(page=2, page_size=10)

        assert total == 50
        assert len(items) == 10


class TestDocumentQueueServiceStats:
    """Tests for DocumentQueueService.get_queue_stats method."""

    @pytest.mark.asyncio
    async def test_get_queue_stats_returns_counts(self):
        """Test that stats returns counts by status."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        # Mock the result rows
        mock_rows = [
            MagicMock(status=DocumentQueueStatus.PENDING, count=5),
            MagicMock(status=DocumentQueueStatus.FAILED, count=3),
            MagicMock(status=DocumentQueueStatus.COMPLETED, count=10),
        ]
        mock_result.all.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        stats = await service.get_queue_stats()

        assert stats["pending"] == 5
        assert stats["failed"] == 3
        assert stats["completed"] == 10
        assert stats["in_progress"] == 0


class TestDocumentQueueServiceManualRetry:
    """Tests for DocumentQueueService.manual_retry method."""

    @pytest.mark.asyncio
    async def test_manual_retry_success(self):
        """Test manual retry resets item to pending."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.FAILED
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = "Max retries exceeded"
        mock_queue_item.next_retry = None
        mock_queue_item.created_at = now
        mock_queue_item.started_at = None
        mock_queue_item.completed_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        service = DocumentQueueService(mock_db)
        result = await service.manual_retry(queue_id, reset_attempts=False)

        assert result is not None
        assert result.status == DocumentQueueStatus.PENDING
        assert result.next_retry is not None
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_manual_retry_with_reset_attempts(self):
        """Test manual retry resets attempt count when requested."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.FAILED
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = "Max retries exceeded"
        mock_queue_item.next_retry = None
        mock_queue_item.created_at = now
        mock_queue_item.started_at = None
        mock_queue_item.completed_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        service = DocumentQueueService(mock_db)
        result = await service.manual_retry(queue_id, reset_attempts=True)

        assert result is not None
        assert result.attempts == 0

    @pytest.mark.asyncio
    async def test_manual_retry_not_found(self):
        """Test manual retry returns None for missing item."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        result = await service.manual_retry(uuid4())

        assert result is None


class TestDocumentQueueServiceCancelItem:
    """Tests for DocumentQueueService.cancel_item method."""

    @pytest.mark.asyncio
    async def test_cancel_item_success(self):
        """Test cancel_item removes pending item."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.PENDING
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 0
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = None
        mock_queue_item.next_retry = now
        mock_queue_item.created_at = now
        mock_queue_item.started_at = None
        mock_queue_item.completed_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        service = DocumentQueueService(mock_db)
        result = await service.cancel_item(queue_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_item_fails_for_in_progress(self):
        """Test cancel_item returns False for in_progress item."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.IN_PROGRESS
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 1
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = None
        mock_queue_item.next_retry = None
        mock_queue_item.created_at = now
        mock_queue_item.started_at = now
        mock_queue_item.completed_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        result = await service.cancel_item(queue_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_item_fails_for_completed(self):
        """Test cancel_item returns False for completed item."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.COMPLETED
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 1
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = None
        mock_queue_item.next_retry = None
        mock_queue_item.created_at = now
        mock_queue_item.started_at = now
        mock_queue_item.completed_at = now

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        result = await service.cancel_item(queue_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_item_fails_for_failed(self):
        """Test cancel_item returns False for failed item."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.FAILED
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = "Error"
        mock_queue_item.next_retry = None
        mock_queue_item.created_at = now
        mock_queue_item.started_at = now
        mock_queue_item.completed_at = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_queue_item
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        result = await service.cancel_item(queue_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_item_not_found(self):
        """Test cancel_item returns False for missing item."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = DocumentQueueService(mock_db)
        result = await service.cancel_item(uuid4())

        assert result is False


class TestDocumentQueueSchemas:
    """Tests for document queue Pydantic schemas."""

    def test_document_queue_item_response(self):
        """Test DocumentQueueItemResponse schema."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        response = DocumentQueueItemResponse(
            id=queue_id,
            document_id=document_id,
            document_name="test_document.pdf",
            status=DocumentQueueStatus.PENDING,
            operation=DocumentQueueOperation.PROCESS,
            attempts=2,
            max_attempts=5,
            error_message=None,
            next_retry=now + timedelta(minutes=5),
            created_at=now,
            started_at=None,
            completed_at=None,
        )

        assert response.id == queue_id
        assert response.document_id == document_id
        assert response.document_name == "test_document.pdf"
        assert response.status == DocumentQueueStatus.PENDING
        assert response.attempts == 2

    def test_document_queue_item_response_with_error(self):
        """Test DocumentQueueItemResponse schema with error message."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        response = DocumentQueueItemResponse(
            id=queue_id,
            document_id=document_id,
            document_name="test_document.pdf",
            status=DocumentQueueStatus.FAILED,
            operation=DocumentQueueOperation.REPROCESS,
            attempts=5,
            max_attempts=5,
            error_message="Connection timeout to embedding service",
            next_retry=None,
            created_at=now,
            started_at=now,
            completed_at=None,
        )

        assert response.status == DocumentQueueStatus.FAILED
        assert response.error_message == "Connection timeout to embedding service"
        assert response.operation == DocumentQueueOperation.REPROCESS

    def test_document_queue_list_response(self):
        """Test DocumentQueueListResponse schema."""
        response = DocumentQueueListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            has_more=False,
        )

        assert response.total == 0
        assert response.has_more is False

    def test_document_queue_stats_response(self):
        """Test DocumentQueueStatsResponse schema."""
        response = DocumentQueueStatsResponse(
            pending=5,
            in_progress=2,
            completed=100,
            failed=3,
            total=110,
        )

        assert response.pending == 5
        assert response.in_progress == 2
        assert response.completed == 100
        assert response.failed == 3
        assert response.total == 110


class TestDocumentQueueListResponseValidation:
    """Tests for creating response objects from service output."""

    @pytest.mark.asyncio
    async def test_create_response_from_service_output(self):
        """Test creating DocumentQueueListResponse from service items."""
        queue_id = uuid4()
        document_id = uuid4()
        now = datetime.now(UTC)

        mock_queue_item = MagicMock(spec=DocumentProcessingQueue)
        mock_queue_item.id = queue_id
        mock_queue_item.document_id = document_id
        mock_queue_item.status = DocumentQueueStatus.FAILED
        mock_queue_item.operation = DocumentQueueOperation.PROCESS
        mock_queue_item.attempts = 5
        mock_queue_item.max_attempts = 5
        mock_queue_item.error_message = "API error"
        mock_queue_item.next_retry = None
        mock_queue_item.created_at = now
        mock_queue_item.started_at = now
        mock_queue_item.completed_at = None

        # Simulate what the endpoint does
        items_with_names = [(mock_queue_item, "test.pdf")]
        total = 1
        page = 1
        page_size = 20

        response_items = []
        for queue_item, document_name in items_with_names:
            item_dict = {
                "id": queue_item.id,
                "document_id": queue_item.document_id,
                "document_name": document_name,
                "status": queue_item.status,
                "operation": queue_item.operation,
                "attempts": queue_item.attempts,
                "max_attempts": queue_item.max_attempts,
                "error_message": queue_item.error_message,
                "next_retry": queue_item.next_retry,
                "created_at": queue_item.created_at,
                "started_at": queue_item.started_at,
                "completed_at": queue_item.completed_at,
            }
            response_items.append(DocumentQueueItemResponse(**item_dict))

        response = DocumentQueueListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total,
        )

        assert isinstance(response, DocumentQueueListResponse)
        assert len(response.items) == 1
        assert response.items[0].document_name == "test.pdf"
        assert response.items[0].status == DocumentQueueStatus.FAILED
        assert response.has_more is False
