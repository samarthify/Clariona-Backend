-- Validate DB migration (run against NEW pgvector DB after restore + alembic upgrade)
-- Usage: psql "$NEW_DATABASE_URL" -f scripts/validate_db_migration.sql

\echo '=== PostgreSQL Version ==='
SELECT version();

\echo ''
\echo '=== Extensions (expect: vector) ==='
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'plpgsql');

\echo ''
\echo '=== Row counts (compare with OLD DB) ==='
SELECT 'sentiment_data' AS tbl, count(*) AS cnt FROM sentiment_data
UNION ALL
SELECT 'processing_clusters', count(*) FROM processing_clusters
UNION ALL
SELECT 'sentiment_embeddings', count(*) FROM sentiment_embeddings
UNION ALL
SELECT 'cluster_mentions', count(*) FROM cluster_mentions
UNION ALL
SELECT 'mention_topics', count(*) FROM mention_topics
UNION ALL
SELECT 'topic_issues', count(*) FROM topic_issues;

\echo ''
\echo '=== New columns (expect cluster_id, embedding_vec, centroid_vec) ==='
SELECT table_name, column_name
FROM information_schema.columns
WHERE (table_name = 'sentiment_data' AND column_name = 'cluster_id')
   OR (table_name = 'sentiment_embeddings' AND column_name = 'embedding_vec')
   OR (table_name = 'processing_clusters' AND column_name IN ('centroid_vec', 'sum_vec'));

\echo ''
\echo '=== Queue tables (expect analysis_queue, cluster_pending_queue) ==='
SELECT tablename FROM pg_tables WHERE schemaname = 'public'
AND tablename IN ('analysis_queue', 'cluster_pending_queue');
