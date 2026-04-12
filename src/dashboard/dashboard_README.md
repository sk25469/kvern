# dashboard

A local Streamlit dashboard that makes KVern's analytics visible. It reads from the SQLite store and renders the metrics that tell you whether KVern is doing anything useful — hit rates, token reuse ratios, hot prefixes, and what the eviction policy would do right now.

This is a **read-only diagnostic tool**, not a control plane. It observes; it does not configure or trigger actions.

---

## Responsibilities

- Display real-time (auto-refreshing) aggregate metrics
- Show hit rate and token reuse ratio over configurable time windows
- List hot prefixes ranked by frequency
- Preview the current eviction policy's ranked candidate list
- Provide a per-model breakdown of all metrics

---

## Views

### Overview
The headline numbers at a glance:

| Metric | What it tells you |
|---|---|
| Cache hit rate | Are requests actually sharing prefixes? |
| Token reuse ratio | What fraction of prompt compute was redundant? |
| Theoretical savings | Estimated FLOP reduction if KV reuse was wired |
| Total requests (24h) | Traffic volume |
| Avg backend latency | Baseline for Phase 2 comparison |

### Hot Prefixes
A table of the top-N most reused prefixes:

- Token depth (how long the shared prefix is)
- Count (how many requests reused it)
- Last seen (recency)
- Model (which model owns this prefix path)

This is where you find your system prompt. If a 2000-token system prompt appears at the top with count=10,000, that's the single biggest KV cache win waiting to be unlocked in Phase 2.

### Timeline
Rolling hit rate and token reuse ratio over the last 1h / 24h / 7d. Useful for spotting traffic pattern changes — a drop in hit rate after a deploy usually means a system prompt changed.

### Eviction Preview
What the current eviction policy would remove if the trie hit its memory cap right now. Shows the bottom-N nodes ranked by eviction score with their depth, count, and last-seen. Useful for sanity-checking the policy before Phase 2 wires it to real GPU memory.

### Per-model Breakdown
All metrics segmented by model. Useful when serving multiple models — you might find LLaMA 3 has a 70% hit rate while Mistral has 20%, which tells you where to focus.

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit app — all views, layout, auto-refresh |

---

## Running

```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`. No authentication in Phase 1 — local tool only.

Auto-refresh interval: 30 seconds (configurable via Streamlit's `st.rerun()` with `time.sleep()`).

---

## Configuration (from `config.yaml`)

```yaml
dashboard:
  port: 8501
```

The dashboard reads `analytics.db_path` from the same config to connect to SQLite.

---

## Design constraints

**Read-only.** The dashboard never writes to the trie or the analytics store. It is a consumer of `analytics/queries.py` only.

**No authentication in Phase 1.** This is a local development tool. If KVern is deployed in a shared environment in Phase 3, dashboard access should be gated.

**No business logic.** Metric computation lives in `analytics/queries.py`, not in the dashboard. The dashboard is pure presentation — it calls query functions and renders results.

**Polling, not push.** The dashboard polls SQLite on a timer. In Phase 3 with Redis Streams, this could become a real-time subscription. Streamlit's architecture makes true push awkward, so polling is the right model for Phase 1.

---

## What a healthy dashboard looks like

After running KVern against a realistic workload for a few hours:

- **Hit rate ≥ 40%** — your traffic has meaningful prefix repetition (system prompts, RAG context, etc.)
- **Token reuse ratio ≥ 0.5** — more than half of prompt tokens are shared with prior requests
- **Hot prefixes table** — 1-3 prefixes dominating the top (typically: system prompt, RAG context template, few-shot examples)
- **Eviction preview** — only shallow, stale, low-count nodes in the candidate list (deep system prompt should never appear here)

If hit rate is < 5% after real traffic, the prompts are too varied for prefix caching to help — or the `MIN_PREFIX_TOKENS` threshold is too high.

---

## Phase roadmap

- **Phase 1:** All views implemented against SQLite; polling refresh; local only
- **Phase 2:** Add "Actual vs Theoretical Savings" panel — compares measured latency reduction (from KV block reuse) against the theoretical savings predicted from token reuse ratio
- **Phase 3:** Real-time metrics via Redis Streams subscription; per-replica cache hit breakdown
