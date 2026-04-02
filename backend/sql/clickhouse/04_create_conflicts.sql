-- Conflicts Table
-- Field-level conflicts detected during deduplication
CREATE TABLE IF NOT EXISTS noctis.conflicts
(
    -- Primary identifiers
    id String,
    master_id String,
    silver_id String,

    -- Conflict details
    field_name String,
    status Enum8('pending' = 0, 'resolved' = 1, 'ignored' = 2),

    -- Conflicting values
    existing_value String,
    new_value String,
    existing_source String,
    new_source String,

    -- Timestamps
    created_at DateTime DEFAULT now(),
    resolved_at Nullable(DateTime),

    -- Resolution
    resolved_value Nullable(String),
    resolved_by Nullable(String),

    -- Indexes
    INDEX idx_master master_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_status status TYPE set(0) GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY status
ORDER BY (status, created_at, id)
SETTINGS index_granularity = 8192;

-- Materialized view for conflict statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS noctis.conflict_stats
ENGINE = AggregatingMergeTree()
ORDER BY (status, date, field_name)
AS SELECT
    status,
    toDate(created_at) AS date,
    field_name,
    count() AS count
FROM noctis.conflicts
GROUP BY status, date, field_name;
