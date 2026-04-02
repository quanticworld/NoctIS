-- Silver Records Table
-- Raw imported data from breaches
CREATE TABLE IF NOT EXISTS noctis.silver_records
(
    -- Primary identifiers
    id String,
    source_id String,
    breach_name String,
    source_file String,
    imported_at DateTime DEFAULT now(),
    master_id Nullable(String),

    -- Personal information
    email Nullable(String),
    username Nullable(String),
    phone Nullable(String),
    password Nullable(String),
    password_hash Nullable(String),
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
    domain Nullable(String),
    notes Nullable(String),

    -- Normalized fields for fuzzy matching
    email_normalized Nullable(String),
    name_soundex Nullable(String),
    phone_normalized Nullable(String),

    -- Bloom filter indexes for fast lookups
    INDEX idx_email email TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_phone phone TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_breach breach_name TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_master master_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_email_norm email_normalized TYPE bloom_filter(0.01) GRANULARITY 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(imported_at)
ORDER BY (breach_name, imported_at, id)
SETTINGS index_granularity = 8192;
