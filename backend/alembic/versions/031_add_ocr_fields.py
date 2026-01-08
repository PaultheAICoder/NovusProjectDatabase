"""Add OCR metadata fields to documents table.

Revision ID: 031
Revises: 030
Create Date: 2026-01-07

Adds fields to track OCR processing status and quality:
- ocr_processed: Whether OCR was used for text extraction
- ocr_confidence: Average confidence score (0.0-1.0)
- ocr_processed_at: When OCR processing completed
- ocr_error: Error message if OCR failed
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "031"
down_revision: str | None = "030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add OCR metadata fields to documents table."""
    op.add_column(
        "documents",
        sa.Column(
            "ocr_processed", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "documents",
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("ocr_processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("ocr_error", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    """Remove OCR metadata fields from documents table."""
    op.drop_column("documents", "ocr_error")
    op.drop_column("documents", "ocr_processed_at")
    op.drop_column("documents", "ocr_confidence")
    op.drop_column("documents", "ocr_processed")
