"""Import service for bulk import with RAG assistance."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.project import Project, ProjectStatus
from app.models.tag import Tag
from app.models.user import User
from app.schemas.import_ import (
    AutofillResponse,
    ImportCommitResult,
    ImportRowPreview,
    ImportRowSuggestion,
    ImportRowUpdate,
    ImportRowValidation,
)
from app.services.embedding_service import EmbeddingService


# Column name mappings (CSV header -> internal field)
COLUMN_MAPPINGS = {
    # Name variations
    "name": "name",
    "project_name": "name",
    "project name": "name",
    "title": "name",
    # Organization variations
    "organization": "organization_name",
    "organization_name": "organization_name",
    "organization name": "organization_name",
    "org": "organization_name",
    "client": "organization_name",
    "company": "organization_name",
    # Description variations
    "description": "description",
    "desc": "description",
    "details": "description",
    "summary": "description",
    # Status variations
    "status": "status",
    "project_status": "status",
    "state": "status",
    # Date variations
    "start_date": "start_date",
    "start date": "start_date",
    "started": "start_date",
    "begin_date": "start_date",
    "end_date": "end_date",
    "end date": "end_date",
    "ended": "end_date",
    "finish_date": "end_date",
    # Location variations
    "location": "location",
    "loc": "location",
    "site": "location",
    # Owner variations
    "owner": "owner_email",
    "owner_email": "owner_email",
    "owner email": "owner_email",
    "project_owner": "owner_email",
    "pm": "owner_email",
    "project_manager": "owner_email",
    # Tags variations
    "tags": "tags",
    "tag": "tags",
    "labels": "tags",
    "categories": "tags",
    # Billing variations
    "billing_amount": "billing_amount",
    "billing amount": "billing_amount",
    "amount": "billing_amount",
    "budget": "billing_amount",
    "billing_recipient": "billing_recipient",
    "billing recipient": "billing_recipient",
    "bill_to": "billing_recipient",
    "billing_notes": "billing_notes",
    "billing notes": "billing_notes",
    # Notes variations
    "pm_notes": "pm_notes",
    "pm notes": "pm_notes",
    "notes": "pm_notes",
    # URL variations
    "monday_url": "monday_url",
    "monday": "monday_url",
    "jira_url": "jira_url",
    "jira": "jira_url",
    "gitlab_url": "gitlab_url",
    "gitlab": "gitlab_url",
}

# Status value mappings
STATUS_MAPPINGS = {
    "approved": ProjectStatus.APPROVED,
    "active": ProjectStatus.ACTIVE,
    "in progress": ProjectStatus.ACTIVE,
    "in_progress": ProjectStatus.ACTIVE,
    "ongoing": ProjectStatus.ACTIVE,
    "on hold": ProjectStatus.ON_HOLD,
    "on_hold": ProjectStatus.ON_HOLD,
    "paused": ProjectStatus.ON_HOLD,
    "completed": ProjectStatus.COMPLETED,
    "done": ProjectStatus.COMPLETED,
    "finished": ProjectStatus.COMPLETED,
    "cancelled": ProjectStatus.CANCELLED,
    "canceled": ProjectStatus.CANCELLED,
    "dropped": ProjectStatus.CANCELLED,
}


class ImportService:
    """Service for parsing and importing projects from CSV."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def parse_csv(
        self,
        content: bytes,
        filename: str,
    ) -> tuple[list[dict], dict[str, str]]:
        """
        Parse CSV content and return rows with column mappings.

        Returns tuple of (rows, column_mappings).
        """
        try:
            text = content.decode("utf-8-sig")  # Handle BOM
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))

        # Map column names
        column_mappings = {}
        for header in reader.fieldnames or []:
            normalized = header.lower().strip()
            if normalized in COLUMN_MAPPINGS:
                column_mappings[header] = COLUMN_MAPPINGS[normalized]

        rows = []
        for row in reader:
            mapped_row = {}
            for original, internal in column_mappings.items():
                value = row.get(original, "").strip()
                if value:
                    if internal == "tags":
                        # Parse tags as comma-separated list
                        mapped_row[internal] = [
                            t.strip() for t in value.split(",") if t.strip()
                        ]
                    else:
                        mapped_row[internal] = value
            rows.append(mapped_row)

        return rows, column_mappings

    async def validate_row(
        self,
        row: dict,
        row_number: int,
    ) -> ImportRowValidation:
        """Validate a single import row."""
        errors = []
        warnings = []

        # Required fields
        if not row.get("name"):
            errors.append("Name is required")

        if not row.get("organization_name"):
            errors.append("Organization is required")
        else:
            # Check if organization exists
            org_exists = await self._find_organization(row["organization_name"])
            if not org_exists:
                errors.append(f"Organization '{row['organization_name']}' not found")

        if not row.get("start_date"):
            errors.append("Start date is required")
        else:
            # Validate date format
            try:
                self._parse_date(row["start_date"])
            except ValueError:
                errors.append(f"Invalid start date format: {row['start_date']}")

        if row.get("end_date"):
            try:
                self._parse_date(row["end_date"])
            except ValueError:
                errors.append(f"Invalid end date format: {row['end_date']}")

        # Owner validation
        if row.get("owner_email"):
            owner = await self._find_user_by_email(row["owner_email"])
            if not owner:
                warnings.append(
                    f"Owner '{row['owner_email']}' not found, will use current user"
                )

        # Status validation
        if row.get("status"):
            if row["status"].lower() not in STATUS_MAPPINGS:
                warnings.append(
                    f"Unknown status '{row['status']}', will default to 'approved'"
                )

        # Location (required but can suggest)
        if not row.get("location"):
            warnings.append("Location is missing, will need to be provided")

        # Billing amount validation
        if row.get("billing_amount"):
            try:
                Decimal(row["billing_amount"].replace(",", "").replace("$", ""))
            except InvalidOperation:
                warnings.append(
                    f"Invalid billing amount: {row['billing_amount']}, will be ignored"
                )

        return ImportRowValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def preview_import(
        self,
        content: bytes,
        filename: str,
        include_suggestions: bool = True,
    ) -> tuple[list[ImportRowPreview], dict[str, str]]:
        """
        Parse CSV and return preview with validation and suggestions.

        Returns tuple of (row_previews, column_mappings).
        """
        rows, column_mappings = await self.parse_csv(content, filename)

        previews = []
        for idx, row in enumerate(rows):
            row_number = idx + 2  # Account for header row

            # Validate
            validation = await self.validate_row(row, row_number)

            # Resolve IDs
            org_id = None
            owner_id = None
            tag_ids = None

            if row.get("organization_name"):
                org = await self._find_organization(row["organization_name"])
                if org:
                    org_id = org.id

            if row.get("owner_email"):
                owner = await self._find_user_by_email(row["owner_email"])
                if owner:
                    owner_id = owner.id

            if row.get("tags"):
                tag_ids = await self._resolve_tags(row["tags"])

            # Get suggestions if requested and row has a name
            suggestions = None
            if include_suggestions and row.get("name"):
                suggestions = await self._generate_suggestions(row)

            preview = ImportRowPreview(
                row_number=row_number,
                name=row.get("name"),
                organization_name=row.get("organization_name"),
                description=row.get("description"),
                status=row.get("status"),
                start_date=row.get("start_date"),
                end_date=row.get("end_date"),
                location=row.get("location"),
                owner_email=row.get("owner_email"),
                tags=row.get("tags"),
                billing_amount=row.get("billing_amount"),
                billing_recipient=row.get("billing_recipient"),
                billing_notes=row.get("billing_notes"),
                pm_notes=row.get("pm_notes"),
                monday_url=row.get("monday_url"),
                jira_url=row.get("jira_url"),
                gitlab_url=row.get("gitlab_url"),
                validation=validation,
                suggestions=suggestions,
                resolved_organization_id=org_id,
                resolved_owner_id=owner_id,
                resolved_tag_ids=tag_ids,
            )
            previews.append(preview)

        return previews, column_mappings

    async def commit_import(
        self,
        rows: list[ImportRowUpdate],
        user_id: UUID,
        skip_invalid: bool = True,
    ) -> list[ImportCommitResult]:
        """
        Commit import rows as new projects.

        Returns list of results for each row.
        """
        results = []

        for row in rows:
            try:
                # Validate required fields
                if not row.name:
                    raise ValueError("Name is required")
                if not row.organization_id:
                    raise ValueError("Organization is required")
                if not row.start_date:
                    raise ValueError("Start date is required")
                if not row.location:
                    raise ValueError("Location is required")

                # Create project
                project = Project(
                    name=row.name,
                    organization_id=row.organization_id,
                    owner_id=row.owner_id or user_id,
                    description=row.description or "",
                    status=row.status or ProjectStatus.APPROVED,
                    start_date=row.start_date,
                    end_date=row.end_date,
                    location=row.location,
                    billing_amount=row.billing_amount,
                    billing_recipient=row.billing_recipient,
                    billing_notes=row.billing_notes,
                    pm_notes=row.pm_notes,
                    monday_url=row.monday_url,
                    jira_url=row.jira_url,
                    gitlab_url=row.gitlab_url,
                    created_by=user_id,
                    updated_by=user_id,
                )
                self.db.add(project)
                await self.db.flush()

                # Add tags
                if row.tag_ids:
                    from app.models.project import ProjectTag

                    for tag_id in row.tag_ids:
                        project_tag = ProjectTag(
                            project_id=project.id,
                            tag_id=tag_id,
                        )
                        self.db.add(project_tag)

                results.append(
                    ImportCommitResult(
                        row_number=row.row_number,
                        success=True,
                        project_id=project.id,
                    )
                )
            except Exception as e:
                if skip_invalid:
                    results.append(
                        ImportCommitResult(
                            row_number=row.row_number,
                            success=False,
                            error=str(e),
                        )
                    )
                else:
                    raise

        return results

    async def autofill_project(
        self,
        name: str,
        existing_description: Optional[str] = None,
        organization_id: Optional[UUID] = None,
    ) -> AutofillResponse:
        """
        Generate AI suggestions for project fields based on name and context.

        Uses RAG to find similar projects and suggest field values.
        """
        # Generate embedding for the project name
        query_embedding = await self.embedding_service.generate_embedding(name)

        if not query_embedding:
            return AutofillResponse(confidence=0.0)

        # Find similar projects using vector search
        similar_projects = await self._find_similar_projects(
            query_embedding, organization_id, limit=5
        )

        if not similar_projects:
            return AutofillResponse(confidence=0.0)

        # Analyze similar projects to suggest fields
        suggested_description = None
        tag_suggestions: dict[str, int] = {}

        for project in similar_projects:
            # Collect common tags
            for tag in project.tags:
                tag_suggestions[tag.name] = tag_suggestions.get(tag.name, 0) + 1

        # Sort tags by frequency
        sorted_tags = sorted(tag_suggestions.items(), key=lambda x: x[1], reverse=True)
        suggested_tag_names = [t[0] for t in sorted_tags[:5]]

        # Resolve tag IDs
        suggested_tag_ids = await self._resolve_tags(suggested_tag_names)

        # Calculate confidence based on how many similar projects were found
        confidence = min(len(similar_projects) / 5, 1.0) * 0.8

        return AutofillResponse(
            suggested_description=suggested_description,
            suggested_tags=suggested_tag_names,
            suggested_tag_ids=suggested_tag_ids,
            confidence=confidence,
        )

    async def _generate_suggestions(self, row: dict) -> ImportRowSuggestion:
        """Generate AI suggestions for a row."""
        name = row.get("name", "")

        if not name:
            return ImportRowSuggestion(confidence=0.0)

        # Generate embedding for the project name
        query_embedding = await self.embedding_service.generate_embedding(name)

        if not query_embedding:
            return ImportRowSuggestion(confidence=0.0)

        # Find similar projects
        similar_projects = await self._find_similar_projects(
            query_embedding, None, limit=3
        )

        if not similar_projects:
            return ImportRowSuggestion(confidence=0.0)

        # Collect suggestions from similar projects
        tag_suggestions: dict[str, int] = {}
        org_suggestions: dict[UUID, int] = {}
        owner_suggestions: dict[UUID, int] = {}

        for project in similar_projects:
            for tag in project.tags:
                tag_suggestions[tag.name] = tag_suggestions.get(tag.name, 0) + 1
            org_suggestions[project.organization_id] = (
                org_suggestions.get(project.organization_id, 0) + 1
            )
            owner_suggestions[project.owner_id] = (
                owner_suggestions.get(project.owner_id, 0) + 1
            )

        # Get top suggestions
        sorted_tags = sorted(tag_suggestions.items(), key=lambda x: x[1], reverse=True)
        suggested_tags = [t[0] for t in sorted_tags[:3]]

        sorted_orgs = sorted(org_suggestions.items(), key=lambda x: x[1], reverse=True)
        suggested_org = sorted_orgs[0][0] if sorted_orgs else None

        sorted_owners = sorted(
            owner_suggestions.items(), key=lambda x: x[1], reverse=True
        )
        suggested_owner = sorted_owners[0][0] if sorted_owners else None

        confidence = min(len(similar_projects) / 3, 1.0) * 0.7

        return ImportRowSuggestion(
            suggested_tags=suggested_tags if suggested_tags else None,
            suggested_organization_id=suggested_org,
            suggested_owner_id=suggested_owner,
            confidence=confidence,
        )

    async def _find_similar_projects(
        self,
        query_embedding: list[float],
        organization_id: Optional[UUID],
        limit: int = 5,
    ) -> list[Project]:
        """Find similar projects using vector search on project names/descriptions."""
        from sqlalchemy.orm import selectinload

        # For now, we'll use a simple name similarity approach
        # In production, you'd want embeddings on projects too
        stmt = (
            select(Project)
            .options(
                selectinload(Project.tags),
            )
            .order_by(Project.created_at.desc())
            .limit(limit * 2)
        )

        if organization_id:
            stmt = stmt.where(Project.organization_id == organization_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all()[:limit])

    async def _find_organization(self, name: str) -> Optional[Organization]:
        """Find organization by name (case-insensitive)."""
        stmt = select(Organization).where(
            func.lower(Organization.name) == name.lower()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_user_by_email(self, email: str) -> Optional[User]:
        """Find user by email (case-insensitive)."""
        stmt = select(User).where(func.lower(User.email) == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _resolve_tags(self, tag_names: list[str]) -> list[UUID]:
        """Resolve tag names to IDs, creating freeform tags if needed."""
        if not tag_names:
            return []

        tag_ids = []
        for name in tag_names:
            stmt = select(Tag).where(func.lower(Tag.name) == name.lower())
            result = await self.db.execute(stmt)
            tag = result.scalar_one_or_none()

            if tag:
                tag_ids.append(tag.id)

        return tag_ids

    def _parse_date(self, value: str) -> date:
        """Parse date from various formats."""
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Could not parse date: {value}")
