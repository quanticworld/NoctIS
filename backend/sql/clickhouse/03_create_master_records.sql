-- Master Records Table
-- Deduplicated entities with aggregated data from multiple sources
CREATE TABLE IF NOT EXISTS noctis.master_records
(
    -- Primary identifiers
    id String,
    status Enum8('silver' = 0, 'golden' = 1),
    confidence_score Float32,

    -- Timestamps
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now(),

    -- Validation
    validated_by String DEFAULT 'auto',
    matching_keys Array(String),

    -- Source tracking
    silver_ids Array(String),
    source_count UInt32,
    breach_names Array(String),
    first_seen DateTime,
    last_seen DateTime,

    -- Personal information (single values - best/most recent)
    email Nullable(String),
    username Nullable(String),
    phone Nullable(String),
    ip_address Nullable(String),

    -- Name fields
    full_name Nullable(String),
    first_name Nullable(String),
    last_name Nullable(String),
    gender Nullable(String),
    birth_date Nullable(Date),

    -- Location
    address Nullable(String),
    city Nullable(String),
    country Nullable(String),
    zip_code Nullable(String),

    -- Professional
    company Nullable(String),
    job_title Nullable(String),

    -- Online presence
    social_media Nullable(String),
    website Nullable(String),

    -- Aggregated arrays (all values from all sources)
    passwords Array(String),
    password_hashes Array(String),

    -- Email verification flags
    email_verified Bool DEFAULT false,
    phone_verified Bool DEFAULT false,

    -- Bloom filter indexes for fast lookups
    INDEX idx_email email TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_phone phone TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_status status TYPE set(0) GRANULARITY 1,
    INDEX idx_breach breach_names TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY status
ORDER BY (status, updated_at, id)
SETTINGS index_granularity = 8192;

-- Materialized view for master statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS noctis.master_stats
ENGINE = AggregatingMergeTree()
ORDER BY (status, date)
AS SELECT
    status,
    toDate(updated_at) AS date,
    count() AS count,
    avg(confidence_score) AS avg_confidence,
    avg(source_count) AS avg_sources
FROM noctis.master_records
GROUP BY status, date;
