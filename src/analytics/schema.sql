-- KVern Analytics Database Schema
-- SQLite schema for tracking cache performance and prefix analytics

-- =============================================================================
-- Prefix Events Table
-- =============================================================================
-- Records every cache lookup event (hit or miss) with timing and context

CREATE TABLE IF NOT EXISTS prefix_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Timing and identification
    ts REAL NOT NULL,                    -- Unix timestamp of event
    request_id TEXT NOT NULL,            -- UUID for request tracking
    
    -- Request context
    model TEXT NOT NULL,                 -- Model name (llama3, mistral, etc.)
    prompt_tokens INTEGER NOT NULL,      -- Total prompt length in tokens
    
    -- Cache performance 
    shared_prefix_tokens INTEGER,        -- Tokens shared with cache (NULL = miss)
    is_hit INTEGER NOT NULL,             -- 0 or 1, cache hit indicator
    
    -- Backend performance
    backend_latency_ms REAL              -- Backend response time (filled post-response)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_prefix_events_ts ON prefix_events(ts);
CREATE INDEX IF NOT EXISTS idx_prefix_events_model ON prefix_events(model);
CREATE INDEX IF NOT EXISTS idx_prefix_events_hit ON prefix_events(is_hit);
CREATE INDEX IF NOT EXISTS idx_prefix_events_model_ts ON prefix_events(model, ts);

-- =============================================================================
-- Hot Prefixes Table  
-- =============================================================================
-- Tracks frequently accessed prefix patterns for optimization insights

CREATE TABLE IF NOT EXISTS hot_prefixes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Prefix identification
    model TEXT NOT NULL,                 -- Model this prefix belongs to
    prefix_hash TEXT NOT NULL,           -- SHA256 hash of token sequence (first 16 chars)
    token_depth INTEGER NOT NULL,        -- Prefix length in tokens
    
    -- Access patterns
    count INTEGER NOT NULL,              -- Number of times this prefix was accessed
    last_seen REAL NOT NULL,             -- Unix timestamp of most recent access
    first_seen REAL NOT NULL,            -- Unix timestamp of first access
    
    -- Constraint: one record per model+prefix combination
    UNIQUE(model, prefix_hash)
);

-- Indexes for hot prefix queries
CREATE INDEX IF NOT EXISTS idx_hot_prefixes_model ON hot_prefixes(model);
CREATE INDEX IF NOT EXISTS idx_hot_prefixes_count ON hot_prefixes(count);
CREATE INDEX IF NOT EXISTS idx_hot_prefixes_model_count ON hot_prefixes(model, count DESC);

-- =============================================================================
-- Views for Common Queries
-- =============================================================================

-- Overall cache performance summary
CREATE VIEW IF NOT EXISTS cache_performance_summary AS
SELECT 
    COUNT(*) as total_requests,
    SUM(is_hit) as cache_hits,
    ROUND(CAST(SUM(is_hit) AS FLOAT) / COUNT(*) * 100, 2) as hit_rate_pct,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(COALESCE(shared_prefix_tokens, 0)) as total_shared_tokens,
    ROUND(
        CAST(SUM(COALESCE(shared_prefix_tokens, 0)) AS FLOAT) / 
        SUM(prompt_tokens) * 100, 2
    ) as token_reuse_pct,
    ROUND(AVG(backend_latency_ms), 2) as avg_latency_ms,
    COUNT(DISTINCT model) as unique_models,
    MIN(ts) as first_event,
    MAX(ts) as last_event
FROM prefix_events;

-- Per-model performance breakdown  
CREATE VIEW IF NOT EXISTS model_performance AS
SELECT 
    model,
    COUNT(*) as requests,
    SUM(is_hit) as hits,
    ROUND(CAST(SUM(is_hit) AS FLOAT) / COUNT(*) * 100, 2) as hit_rate_pct,
    SUM(prompt_tokens) as total_prompt_tokens,
    SUM(COALESCE(shared_prefix_tokens, 0)) as shared_tokens,
    ROUND(
        CAST(SUM(COALESCE(shared_prefix_tokens, 0)) AS FLOAT) / 
        SUM(prompt_tokens) * 100, 2
    ) as token_reuse_pct,
    ROUND(AVG(prompt_tokens), 1) as avg_prompt_length,
    ROUND(AVG(backend_latency_ms), 2) as avg_latency_ms
FROM prefix_events
GROUP BY model;

-- Recent activity (last 24 hours)
CREATE VIEW IF NOT EXISTS recent_activity AS  
SELECT 
    model,
    COUNT(*) as requests_24h,
    SUM(is_hit) as hits_24h,
    ROUND(CAST(SUM(is_hit) AS FLOAT) / COUNT(*) * 100, 2) as hit_rate_24h_pct,
    MAX(ts) as last_request
FROM prefix_events
WHERE ts > (strftime('%s', 'now') - 86400)  -- Last 24 hours
GROUP BY model;

-- =============================================================================
-- Data Retention and Cleanup
-- =============================================================================

-- Trigger to automatically clean old data (optional, can be manually managed)
-- Uncomment and modify retention period as needed:

/*
CREATE TRIGGER IF NOT EXISTS cleanup_old_data
AFTER INSERT ON prefix_events
WHEN NEW.id % 1000 = 0  -- Check every 1000 inserts
BEGIN
    DELETE FROM prefix_events 
    WHERE ts < (strftime('%s', 'now') - 2592000);  -- 30 days retention
    
    DELETE FROM hot_prefixes 
    WHERE last_seen < (strftime('%s', 'now') - 2592000);  -- 30 days retention
END;
*/

-- =============================================================================
-- Common Query Examples (Reference)
-- =============================================================================

/*
-- Hit rate over time (hourly buckets)
SELECT 
    datetime(CAST(ts/3600 AS INTEGER)*3600, 'unixepoch') as hour,
    COUNT(*) as requests,
    SUM(is_hit) as hits,
    ROUND(CAST(SUM(is_hit) AS FLOAT) / COUNT(*) * 100, 2) as hit_rate_pct
FROM prefix_events
WHERE ts > (strftime('%s', 'now') - 86400)  -- Last 24 hours
GROUP BY CAST(ts/3600 AS INTEGER)
ORDER BY hour;

-- Top prefixes by access frequency
SELECT 
    h.model,
    h.token_depth,
    h.count,
    h.last_seen,
    datetime(h.last_seen, 'unixepoch') as last_seen_readable
FROM hot_prefixes h
ORDER BY h.count DESC
LIMIT 20;

-- Latency analysis by cache hit status
SELECT 
    CASE WHEN is_hit = 1 THEN 'Hit' ELSE 'Miss' END as cache_status,
    COUNT(*) as count,
    ROUND(AVG(backend_latency_ms), 2) as avg_latency_ms,
    ROUND(MIN(backend_latency_ms), 2) as min_latency_ms,
    ROUND(MAX(backend_latency_ms), 2) as max_latency_ms
FROM prefix_events
WHERE backend_latency_ms IS NOT NULL
GROUP BY is_hit;

-- Daily cache performance trend
SELECT 
    date(ts, 'unixepoch') as date,
    COUNT(*) as requests,
    SUM(is_hit) as hits,
    ROUND(CAST(SUM(is_hit) AS FLOAT) / COUNT(*) * 100, 2) as hit_rate_pct,
    SUM(prompt_tokens) as total_tokens,
    SUM(COALESCE(shared_prefix_tokens, 0)) as shared_tokens
FROM prefix_events
WHERE ts > (strftime('%s', 'now') - 604800)  -- Last 7 days
GROUP BY date(ts, 'unixepoch')
ORDER BY date;
*/