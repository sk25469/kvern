# analytics

Persistence and query layer for KVern's observability data. Every request that passes through the proxy produces a trie event — hit or miss, shared depth, model, timestamp. This component stores those events and computes the metrics that make KVern's value visible.

---

## Responsibilities

- Write trie traversal events to SQLite on every request
- Record backend latency post-response
- Compute aggregate metrics on demand (hit rate, token reuse ratio, savings estimate)
- Support time-windowed queries (last 1h, 24h, 7d)
- Persist hot prefix snapshots from the trie

---

## Why SQLite

Zero infrastructure. Single file on disk. Can be inspected directly with any SQLite client (`sqlite3`, TablePlus, DBeaver) for debugging. No Postgres, no Redis, no Docker required to run Phase 1.

At realistic Phase 1 traffic (thousands of requests/day on a local dev setup), SQLite handles the write throughput without issue. The write path is async — it never blocks the proxy's critical path.

Migration to Postgres is a config change when Phase 3 requires it.

---

## Schema

```sql
CREATE TABLE prefix_events (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    REAL    NOT NULL,
    model                 TEXT    NOT NULL,
    request_id            TEXT    NOT NULL,
    prompt_tokens         INTEGER NOT NULL,
    shared_prefix_tokens  INTEGER,          -- null on miss
    is_hit                INTEGER NOT NULL, -- 0 or 1
    backend_latency_ms    REAL              -- filled post-response
);

CREATE TABLE hot_prefixes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    model        TEXT    NOT NULL,
    prefix_hash  TEXT    NOT NULL,  -- sha256 of token_ids for the prefix
    token_depth  INTEGER NOT NULL,
    count        INTEGER NOT NULL,
    last_seen    REAL    NOT NULL,
    first_seen   REAL    NOT NULL
);

CREATE INDEX idx_prefix_events_ts    ON prefix_events(ts);
CREATE INDEX idx_prefix_events_model ON prefix_events(model, ts);
```

`prefix_hash` in `hot_prefixes` is a SHA-256 of the token ID sequence for that prefix — used to deduplicate across trie snapshots without storing the full token sequence.

---

## Write path

Two write operations per request:

**On request arrival (async, fire-and-forget):**
```python
store.record_event(
    request_id=request_id,
    model=model,
    prompt_tokens=len(token_ids),
    shared_prefix_tokens=matched_depth if is_hit else None,
    is_hit=is_hit
)
```

**Post-response (async, fire-and-forget):**
```python
store.update_latency(request_id=request_id, latency_ms=elapsed_ms)
```

Both are dispatched as `asyncio.create_task()` — the proxy does not await them. If SQLite is temporarily slow or locked, requests are unaffected.

---

## Key metrics

| Metric | Formula | Meaning |
|---|---|---|
| Cache hit rate | `hits / total` | Fraction of requests sharing a meaningful prefix |
| Token reuse ratio | `sum(shared_prefix_tokens) / sum(prompt_tokens)` | Fraction of prompt tokens that were reuses |
| Theoretical savings | `token_reuse_ratio × 100%` | Proxy for FLOP reduction (Phase 2 makes this real) |
| Avg shared depth | `mean(shared_prefix_tokens) on hits` | How deep the average hit goes |
| Hot prefix count | Distinct prefixes above `MIN_PREFIX_TOKENS` with `count > N` | Size of the hot working set |

**Token reuse ratio is the headline number.** A ratio of 0.6 means 60% of all prompt tokens processed by the backend were already seen before — 60% of that compute could have been skipped with KV cache reuse. This is the number that justifies Phase 2.

---

## Files

| File | Purpose |
|---|---|
| `store.py` | Async SQLite write path — `record_event()`, `update_latency()` |
| `queries.py` | Read path — metric computation, time-windowed aggregations |
| `schema.sql` | Table definitions and indexes (applied at startup) |

---

## Configuration (from `config.yaml`)

```yaml
analytics:
  db_path: ./data/cache_analytics.db
  retention_days: 30
```

Rows older than `retention_days` are pruned on a daily schedule to keep the DB size bounded.

---

## Querying manually

```bash
sqlite3 ./data/cache_analytics.db

-- Hit rate last 24h
SELECT
  ROUND(AVG(is_hit) * 100, 1) AS hit_rate_pct,
  COUNT(*) AS total_requests
FROM prefix_events
WHERE ts > strftime('%s', 'now') - 86400;

-- Token reuse ratio
SELECT
  ROUND(
    SUM(COALESCE(shared_prefix_tokens, 0)) * 1.0 / SUM(prompt_tokens) * 100,
    1
  ) AS reuse_ratio_pct
FROM prefix_events
WHERE is_hit = 1;

-- Top 10 models by hit rate
SELECT model, ROUND(AVG(is_hit)*100,1) AS hit_rate_pct, COUNT(*) AS requests
FROM prefix_events
GROUP BY model
ORDER BY hit_rate_pct DESC
LIMIT 10;
```

---

## Phase roadmap

- **Phase 1:** SQLite write/read, metric computation, retention pruning
- **Phase 2:** Add `compute_saved_ms` column — populated with real measured latency savings once KV block reuse is wired; actual savings vs. theoretical savings become comparable
- **Phase 3:** Migrate to shared Postgres or Redis Streams for cross-replica analytics aggregation
