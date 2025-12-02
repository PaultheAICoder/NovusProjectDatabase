"""Search service with hybrid search (PostgreSQL full-text + vector search with RRF)."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentChunk
from app.models.project import Project, ProjectStatus
from app.services.embedding_service import EmbeddingService


class SearchService:
    """Service for searching projects using hybrid search (text + vector + RRF fusion)."""

    # RRF constant - higher values give more weight to lower-ranked results
    RRF_K = 60

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

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
        include_documents: bool = True,
    ) -> tuple[list[Project], int]:
        """
        Search projects using hybrid search with filters.

        Combines:
        1. Full-text search on project fields (ts_vector)
        2. Full-text search on document content
        3. Vector similarity search on document embeddings
        4. RRF (Reciprocal Rank Fusion) to combine rankings

        Returns tuple of (projects, total_count).
        """
        # Base conditions for filtering
        filter_conditions = self._build_filter_conditions(
            status=status,
            organization_id=organization_id,
            tag_ids=tag_ids,
            owner_id=owner_id,
        )

        # If no query, just return filtered projects
        if not query or not query.strip():
            return await self._search_without_query(
                filter_conditions=filter_conditions,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                page_size=page_size,
            )

        # Perform hybrid search with RRF fusion
        return await self._hybrid_search(
            query=query.strip(),
            filter_conditions=filter_conditions,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
            include_documents=include_documents,
        )

    def _build_filter_conditions(
        self,
        status: Optional[list[ProjectStatus]],
        organization_id: Optional[UUID],
        tag_ids: Optional[list[UUID]],
        owner_id: Optional[UUID],
    ) -> list:
        """Build filter conditions for search queries."""
        conditions = []

        if status:
            conditions.append(Project.status.in_(status))

        if organization_id:
            conditions.append(Project.organization_id == organization_id)

        if tag_ids:
            for tag_id in tag_ids:
                tag_subquery = text("""
                    EXISTS (
                        SELECT 1 FROM project_tags
                        WHERE project_tags.project_id = projects.id
                        AND project_tags.tag_id = :tag_id
                    )
                """).bindparams(tag_id=tag_id)
                conditions.append(tag_subquery)

        if owner_id:
            conditions.append(Project.owner_id == owner_id)

        return conditions

    async def _search_without_query(
        self,
        filter_conditions: list,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Project], int]:
        """Search projects without a text query (filters only)."""
        base_query = select(Project).options(
            selectinload(Project.organization),
            selectinload(Project.owner),
            selectinload(Project.tags),
        )

        if filter_conditions:
            base_query = base_query.where(*filter_conditions)

        # Count query
        count_query = select(func.count()).select_from(Project)
        if filter_conditions:
            count_query = count_query.where(*filter_conditions)
        total = await self.db.scalar(count_query)

        # Sorting
        base_query = self._apply_sorting(base_query, sort_by, sort_order, ts_query=None)

        # Pagination
        offset = (page - 1) * page_size
        base_query = base_query.offset(offset).limit(page_size)

        result = await self.db.execute(base_query)
        projects = result.scalars().all()

        return list(projects), total or 0

    async def _hybrid_search(
        self,
        query: str,
        filter_conditions: list,
        sort_by: str,
        sort_order: str,
        page: int,
        page_size: int,
        include_documents: bool,
    ) -> tuple[list[Project], int]:
        """
        Perform hybrid search combining full-text and vector search with RRF.

        RRF Formula: score = sum(1 / (k + rank_i)) for each ranking source
        """
        # Get rankings from different sources
        project_text_ranks = await self._get_project_text_ranks(query, filter_conditions)

        document_text_ranks = {}
        vector_ranks = {}

        if include_documents:
            document_text_ranks = await self._get_document_text_ranks(
                query, filter_conditions
            )
            vector_ranks = await self._get_vector_ranks(query, filter_conditions)

        # Combine all project IDs
        all_project_ids = set(project_text_ranks.keys())
        all_project_ids.update(document_text_ranks.keys())
        all_project_ids.update(vector_ranks.keys())

        if not all_project_ids:
            return [], 0

        # Calculate RRF scores
        rrf_scores: dict[UUID, float] = {}
        for project_id in all_project_ids:
            score = 0.0
            if project_id in project_text_ranks:
                score += 1.0 / (self.RRF_K + project_text_ranks[project_id])
            if project_id in document_text_ranks:
                score += 1.0 / (self.RRF_K + document_text_ranks[project_id])
            if project_id in vector_ranks:
                score += 1.0 / (self.RRF_K + vector_ranks[project_id])
            rrf_scores[project_id] = score

        # Sort by RRF score (or other sort criteria if specified)
        if sort_by == "relevance":
            sorted_ids = sorted(
                rrf_scores.keys(),
                key=lambda pid: rrf_scores[pid],
                reverse=(sort_order == "desc"),
            )
        else:
            # For non-relevance sorts, we still need to respect the RRF filtering
            sorted_ids = list(rrf_scores.keys())

        total = len(sorted_ids)

        # Pagination
        offset = (page - 1) * page_size
        page_ids = sorted_ids[offset : offset + page_size]

        if not page_ids:
            return [], total

        # Fetch full project objects
        base_query = (
            select(Project)
            .options(
                selectinload(Project.organization),
                selectinload(Project.owner),
                selectinload(Project.tags),
            )
            .where(Project.id.in_(page_ids))
        )

        result = await self.db.execute(base_query)
        projects_dict = {p.id: p for p in result.scalars().all()}

        # Maintain sort order
        if sort_by == "relevance":
            projects = [projects_dict[pid] for pid in page_ids if pid in projects_dict]
        else:
            # Apply non-relevance sorting
            projects = list(projects_dict.values())
            projects = self._sort_projects(projects, sort_by, sort_order)

        return projects, total

    async def _get_project_text_ranks(
        self,
        query: str,
        filter_conditions: list,
    ) -> dict[UUID, int]:
        """Get project rankings from full-text search on project fields."""
        ts_query = func.plainto_tsquery("english", query)

        # Query for projects matching the text search
        stmt = (
            select(
                Project.id,
                func.ts_rank(Project.search_vector, ts_query).label("rank"),
            )
            .where(Project.search_vector.op("@@")(ts_query))
        )

        if filter_conditions:
            stmt = stmt.where(*filter_conditions)

        stmt = stmt.order_by(literal_column("rank").desc())

        result = await self.db.execute(stmt)
        rows = result.all()

        # Convert to rank positions (1-indexed)
        return {row.id: idx + 1 for idx, row in enumerate(rows)}

    async def _get_document_text_ranks(
        self,
        query: str,
        filter_conditions: list,
    ) -> dict[UUID, int]:
        """Get project rankings from full-text search on document content."""
        # Create a text search query for document content
        search_pattern = f"%{query}%"

        # Find projects with documents containing the search text
        # We use ILIKE for simplicity; could add tsvector to documents later
        stmt = (
            select(
                Document.project_id,
                func.count(Document.id).label("match_count"),
            )
            .where(Document.extracted_text.ilike(search_pattern))
            .group_by(Document.project_id)
            .order_by(literal_column("match_count").desc())
        )

        # Apply project filter conditions via a subquery
        if filter_conditions:
            project_ids_subquery = (
                select(Project.id).where(*filter_conditions).scalar_subquery()
            )
            stmt = stmt.where(Document.project_id.in_(project_ids_subquery))

        result = await self.db.execute(stmt)
        rows = result.all()

        return {row.project_id: idx + 1 for idx, row in enumerate(rows)}

    async def _get_vector_ranks(
        self,
        query: str,
        filter_conditions: list,
    ) -> dict[UUID, int]:
        """Get project rankings from vector similarity search on document chunks."""
        # Generate embedding for the query
        query_embedding = await self.embedding_service.generate_embedding(query)

        if not query_embedding:
            return {}

        # Find most similar document chunks using cosine distance
        # pgvector uses <=> for cosine distance (lower is better)
        embedding_literal = f"[{','.join(str(x) for x in query_embedding)}]"

        stmt = text("""
            SELECT DISTINCT ON (d.project_id)
                d.project_id,
                dc.embedding <=> :embedding AS distance
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.embedding IS NOT NULL
            ORDER BY d.project_id, dc.embedding <=> :embedding
        """).bindparams(embedding=embedding_literal)

        result = await self.db.execute(stmt)
        rows = result.all()

        # Apply filter conditions separately (for simplicity)
        project_ids_to_keep = set()
        if filter_conditions:
            filter_stmt = select(Project.id).where(*filter_conditions)
            filter_result = await self.db.execute(filter_stmt)
            project_ids_to_keep = {row[0] for row in filter_result.all()}
            rows = [row for row in rows if row.project_id in project_ids_to_keep]

        # Sort by distance (ascending - lower is better)
        sorted_rows = sorted(rows, key=lambda r: r.distance)

        return {row.project_id: idx + 1 for idx, row in enumerate(sorted_rows)}

    def _apply_sorting(
        self,
        query,
        sort_by: str,
        sort_order: str,
        ts_query=None,
    ):
        """Apply sorting to a query."""
        if sort_by == "relevance" and ts_query is not None:
            rank = func.ts_rank(Project.search_vector, ts_query)
            if sort_order == "desc":
                return query.order_by(rank.desc())
            else:
                return query.order_by(rank.asc())
        elif sort_by == "name":
            if sort_order == "desc":
                return query.order_by(Project.name.desc())
            else:
                return query.order_by(Project.name.asc())
        elif sort_by == "start_date":
            if sort_order == "desc":
                return query.order_by(Project.start_date.desc())
            else:
                return query.order_by(Project.start_date.asc())
        else:  # Default to updated_at
            if sort_order == "desc":
                return query.order_by(Project.updated_at.desc())
            else:
                return query.order_by(Project.updated_at.asc())

    def _sort_projects(
        self,
        projects: list[Project],
        sort_by: str,
        sort_order: str,
    ) -> list[Project]:
        """Sort a list of projects in memory."""
        reverse = sort_order == "desc"

        if sort_by == "name":
            return sorted(projects, key=lambda p: p.name, reverse=reverse)
        elif sort_by == "start_date":
            return sorted(projects, key=lambda p: p.start_date, reverse=reverse)
        else:  # updated_at
            return sorted(projects, key=lambda p: p.updated_at, reverse=reverse)

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

    async def search_documents(
        self,
        query: str,
        project_id: Optional[UUID] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Search documents by content using vector similarity.

        Returns matching document chunks with context.
        """
        query_embedding = await self.embedding_service.generate_embedding(query)

        if not query_embedding:
            return []

        embedding_literal = f"[{','.join(str(x) for x in query_embedding)}]"

        # Build query for similar chunks
        if project_id:
            stmt = text("""
                SELECT
                    dc.id as chunk_id,
                    dc.content,
                    dc.chunk_index,
                    d.id as document_id,
                    d.display_name,
                    d.project_id,
                    dc.embedding <=> :embedding AS distance
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.embedding IS NOT NULL
                  AND d.project_id = :project_id
                ORDER BY dc.embedding <=> :embedding
                LIMIT :limit
            """).bindparams(
                embedding=embedding_literal,
                project_id=project_id,
                limit=limit,
            )
        else:
            stmt = text("""
                SELECT
                    dc.id as chunk_id,
                    dc.content,
                    dc.chunk_index,
                    d.id as document_id,
                    d.display_name,
                    d.project_id,
                    dc.embedding <=> :embedding AS distance
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> :embedding
                LIMIT :limit
            """).bindparams(embedding=embedding_literal, limit=limit)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "chunk_id": str(row.chunk_id),
                "content": row.content,
                "chunk_index": row.chunk_index,
                "document_id": str(row.document_id),
                "document_name": row.display_name,
                "project_id": str(row.project_id),
                "similarity": 1 - row.distance,  # Convert distance to similarity
            }
            for row in rows
        ]
