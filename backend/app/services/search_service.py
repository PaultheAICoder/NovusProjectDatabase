"""Search service with PostgreSQL full-text search."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project, ProjectStatus


class SearchService:
    """Service for searching projects using PostgreSQL full-text search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_projects(
        self,
        query: str,
        *,
        status: Optional[list[ProjectStatus]] = None,
        organization_id: Optional[UUID] = None,
        tag_ids: Optional[list[UUID]] = None,
        owner_id: Optional[UUID] = None,
        sort_by: str = "relevance",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Project], int]:
        """
        Search projects using full-text search with filters.

        Returns tuple of (projects, total_count).
        """
        # Base query with eager loading
        base_query = select(Project).options(
            selectinload(Project.organization),
            selectinload(Project.owner),
            selectinload(Project.tags),
        )

        # Build conditions
        conditions = []

        # Full-text search if query provided
        ts_query = None
        if query and query.strip():
            # Convert query to tsquery - support phrases and OR
            search_terms = query.strip()
            ts_query = func.plainto_tsquery("english", search_terms)
            conditions.append(Project.search_vector.op("@@")(ts_query))

        # Status filter
        if status:
            conditions.append(Project.status.in_(status))

        # Organization filter
        if organization_id:
            conditions.append(Project.organization_id == organization_id)

        # Tag filter - all specified tags must be present
        if tag_ids:
            for tag_id in tag_ids:
                # Subquery to check tag membership
                tag_subquery = text("""
                    EXISTS (
                        SELECT 1 FROM project_tags
                        WHERE project_tags.project_id = projects.id
                        AND project_tags.tag_id = :tag_id
                    )
                """).bindparams(tag_id=tag_id)
                conditions.append(tag_subquery)

        # Owner filter
        if owner_id:
            conditions.append(Project.owner_id == owner_id)

        # Apply conditions
        if conditions:
            base_query = base_query.where(*conditions)

        # Count query
        count_query = select(func.count()).select_from(Project)
        if conditions:
            count_query = count_query.where(*conditions)
        total = await self.db.scalar(count_query)

        # Sorting
        if sort_by == "relevance" and ts_query is not None:
            # Sort by ts_rank for relevance
            rank = func.ts_rank(Project.search_vector, ts_query)
            if sort_order == "desc":
                base_query = base_query.order_by(rank.desc())
            else:
                base_query = base_query.order_by(rank.asc())
        elif sort_by == "name":
            if sort_order == "desc":
                base_query = base_query.order_by(Project.name.desc())
            else:
                base_query = base_query.order_by(Project.name.asc())
        elif sort_by == "start_date":
            if sort_order == "desc":
                base_query = base_query.order_by(Project.start_date.desc())
            else:
                base_query = base_query.order_by(Project.start_date.asc())
        else:  # Default to updated_at
            if sort_order == "desc":
                base_query = base_query.order_by(Project.updated_at.desc())
            else:
                base_query = base_query.order_by(Project.updated_at.asc())

        # Pagination
        offset = (page - 1) * page_size
        base_query = base_query.offset(offset).limit(page_size)

        # Execute
        result = await self.db.execute(base_query)
        projects = result.scalars().all()

        return list(projects), total or 0

    async def get_search_suggestions(
        self,
        query: str,
        limit: int = 10,
    ) -> list[str]:
        """
        Get search suggestions based on project names.

        Returns list of matching project names.
        """
        if not query or len(query) < 2:
            return []

        # Use ILIKE for prefix matching
        pattern = f"{query}%"
        stmt = (
            select(Project.name)
            .where(Project.name.ilike(pattern))
            .order_by(Project.name)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]
