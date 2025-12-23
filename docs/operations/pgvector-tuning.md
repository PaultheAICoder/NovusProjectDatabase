# pgvector HNSW Index Tuning Guide

This document provides guidance for tuning the pgvector HNSW index used for semantic search on document chunks.

## Current Configuration

The HNSW (Hierarchical Navigable Small World) index on `document_chunks.embedding` uses default parameters:

```sql
CREATE INDEX ix_document_chunks_embedding
ON document_chunks
USING hnsw (embedding vector_cosine_ops);
```

Default HNSW parameters:
- `m = 16` (number of bi-directional links per node)
- `ef_construction = 64` (size of dynamic candidate list during index construction)

These defaults are suitable for up to ~10,000 vectors with good recall/performance balance.

## When to Tune

Consider tuning when:

1. **Vector search returns poor quality results** - Increase `ef_search` or rebuild with higher `m`
2. **Vector search is slow (>500ms)** - May need to reduce `ef_search` or use IVFFlat instead
3. **Dataset exceeds 100,000 document chunks** - Consider index partitioning or parameter adjustment

## Tuning Options

### Option 1: Adjust Search Quality at Query Time

For better recall without rebuilding the index:

```sql
-- Set before queries for better recall (default is 40)
SET hnsw.ef_search = 100;

-- For highest quality (slower)
SET hnsw.ef_search = 200;
```

**Trade-off**: Higher `ef_search` improves recall but increases query time.

### Option 2: Rebuild Index with Higher Quality Parameters

For datasets with 10,000+ chunks:

```sql
-- Drop existing index
DROP INDEX ix_document_chunks_embedding;

-- Rebuild with higher quality parameters
CREATE INDEX ix_document_chunks_embedding
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 24, ef_construction = 128);
```

**Parameter Guidelines**:
| Dataset Size | Recommended `m` | Recommended `ef_construction` |
|--------------|-----------------|------------------------------|
| < 10,000 | 16 (default) | 64 (default) |
| 10,000 - 100,000 | 24 | 128 |
| 100,000 - 1M | 32 | 256 |
| > 1M | Consider IVFFlat or partitioning |

### Option 3: Switch to IVFFlat for Very Large Datasets

For datasets with 1M+ vectors, IVFFlat may be more efficient:

```sql
-- IVFFlat index (faster build, needs more tuning)
CREATE INDEX ix_document_chunks_embedding_ivfflat
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Query with probe setting
SET ivfflat.probes = 10;
```

## Monitoring

### Check Index Size

```sql
-- Check index size in human-readable format
SELECT pg_size_pretty(pg_relation_size('ix_document_chunks_embedding'));
```

### Check Vector Count

```sql
-- Count embeddings (non-null only)
SELECT count(*) FROM document_chunks WHERE embedding IS NOT NULL;
```

### Analyze Query Performance

```sql
-- Enable timing and run EXPLAIN ANALYZE
\timing on

EXPLAIN ANALYZE
SELECT id, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) as similarity
FROM document_chunks
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

### Monitor Index Usage

```sql
-- Check if index is being used
SELECT schemaname, relname, indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE indexrelname = 'ix_document_chunks_embedding';
```

## Maintenance

### Rebuild Index After Large Data Changes

After bulk imports or deletes (>20% of data):

```sql
REINDEX INDEX ix_document_chunks_embedding;
```

### Update Statistics

```sql
ANALYZE document_chunks;
```

## Related Configuration

See also:
- Database connection pool settings in `backend/app/config.py`
- Search service implementation in `backend/app/services/search_service.py`
- Migration creating the index: `backend/alembic/versions/010_create_document_chunks.py`
