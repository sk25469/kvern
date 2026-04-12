# LLM KV Cache Manager — Design Document

> **Status:** Draft v0.1  
> **Author:** Sahil  
> **Last Updated:** April 2026

---

## 1. Problem Statement

LLM inference is stateless by default. Every request — regardless of how much of the prompt was seen before — triggers a full forward pass through the model. This is computationally wasteful in any system where:

- A static system prompt is prepended to every request (multi-tenant SaaS, RAG pipelines)
- Users in a session re-send overlapping context (chat history growth)
- Multiple replicas serve the same high-frequency prompts independently

The KV (Key-Value) cache is the transformer's native mechanism for avoiding redundant computation — during attention, each token's Key and Value matrices only need to be computed once for a given prefix. The problem is that **existing serving infrastructure either doesn't expose this cache as a first-class primitive, or manages it naively**.

This project builds a **KV Cache Manager** — a control plane that sits above model serving infrastructure (initially vLLM / Ollama) to:

1. Track prefix reuse across requests
2. Inform (and eventually drive) smarter eviction decisions
3. Provide observable, measurable cost savings
4. Lay the foundation for cross-replica cache sharing

---

## 2. Goals and Non-Goals

### Goals

- **G1:** Intercept LLM inference requests and track shared prefixes via a token-level trie
- **G2:** Expose cache hit rate, hot prefixes, and theoretical compute savings as observable metrics
- **G3:** Implement pluggable eviction policies (LRU, LFU-with-decay, cost-aware) as pure logic, independent of GPU state
- **G4:** Be model-agnostic — support any model served via OpenAI-compatible `/v1/chat/completions` API
- **G5:** Be runnable without a GPU — CPU + Ollama is a valid development environment

### Non-Goals (for now)

- **NG1:** Direct manipulation of GPU KV blocks (Phase 2+)
- **NG2:** Cross-replica distributed cache (Phase 3+)
- **NG3:** Semantic / embedding-based caching (different problem, different project)
- **NG4:** Training or fine-tuning workflows
- **NG5:** Supporting non-OpenAI-compatible APIs in v1

---

## 3. Architecture Overview

```
                        ┌─────────────────────────────────────┐
                        │         KV Cache Manager             │
                        │                                      │
  Client Request ──────►│  ┌─────────┐     ┌───────────────┐  │
  (OpenAI-compat)       │  │  Proxy  │────►│  Tokenizer    │  │
                        │  │ FastAPI │     │  (per-model)  │  │
                        │  └────┬────┘     └──────┬────────┘  │
                        │       │                  │           │
                        │       │           token_ids[]        │
                        │       │                  │           │
                        │       │           ┌──────▼────────┐  │
                        │       │           │  Prefix Trie  │  │
                        │       │           │  (token-level)│  │
                        │       │           └──────┬────────┘  │
                        │       │                  │           │
                        │       │           ┌──────▼────────┐  │
                        │       │           │  Analytics    │  │
                        │       │           │  Store        │  │
                        │       │           └──────┬────────┘  │
                        │       │                  │           │
                        │  ┌────▼──────────────────▼────────┐  │
                        │  │      Eviction Policy Engine    │  │
                        │  │  (LRU / LFU / Cost-Aware)      │  │
                        │  └────────────────────────────────┘  │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                             ┌──────────────────┐
                             │  vLLM / Ollama   │
                             │  (model backend) │
                             └──────────────────┘
                                       │
                                       ▼
                              Response → Client
```

The manager is a **transparent proxy** — clients talk to it exactly as they would to a vLLM or OpenAI endpoint. It adds zero API surface changes.

---

## 4. Component Design

### 4.1 Proxy Layer

**Technology:** FastAPI (async, low overhead)

**Responsibilities:**
- Accept `/v1/chat/completions` requests (streaming and non-streaming)
- Extract model name and messages array
- Pass to tokenizer pipeline
- Forward request to configured backend
- Record response metadata (latency, token counts) post-response
- Return response to client unmodified

**Key design decision:** The proxy must be fully transparent. No request modification. No response modification. It observes and records — it does not interfere.

**Streaming note:** When `stream: true`, the proxy needs to buffer SSE chunks to capture the full completion token count for analytics. The stream is still forwarded to the client in real-time — buffering happens in parallel, not serially.

```
POST /v1/chat/completions
    │
    ├──► [async] Tokenize + Trie record
    │
    └──► Forward to backend ──► Stream to client
                    │
                    └──► [on complete] Record response metadata
```

---

### 4.2 Tokenizer Pipeline

**Responsibilities:**
- Map model name → correct tokenizer
- Apply model's chat template to serialize `messages[]` → flat token sequence
- Return `token_ids: list[int]`

**Why token IDs, not strings:**  
The trie keys on token IDs, not raw text. Two prompts that are identical after chat-template application must produce the same token sequence. String-level hashing breaks down across whitespace variants, role label differences, etc.

**Chat template application:**  
Each model has a chat template (Jinja2 format, stored in `tokenizer_config.json` on HuggingFace). This template defines how `[{role, content}]` → flat string → token IDs. We must apply this correctly, otherwise trie paths diverge for semantically identical conversations.

```python
# Pseudocode
class TokenizerPipeline:
    _registry: dict[str, PreTrainedTokenizer] = {}

    def tokenize(self, model: str, messages: list[dict]) -> list[int]:
        tokenizer = self._get_or_load(model)
        # Apply chat template: messages → flat string
        text = tokenizer.apply_chat_template(messages, tokenize=False)
        # Tokenize: string → token IDs
        return tokenizer.encode(text)

    def _get_or_load(self, model: str) -> PreTrainedTokenizer:
        if model not in self._registry:
            self._registry[model] = AutoTokenizer.from_pretrained(MODEL_MAP[model])
        return self._registry[model]
```

**Model map:** A config file maps model names (as they appear in API requests) to HuggingFace tokenizer identifiers.

---

### 4.3 Prefix Trie

The core data structure. Token-level trie where each path from root → node represents a prefix seen in at least one request.

**Node structure:**

```python
@dataclass
class TrieNode:
    children: dict[int, 'TrieNode']   # token_id → child node
    count: int = 0                     # times this prefix was terminal or traversed
    last_seen: float = 0.0             # unix timestamp of last access
    first_seen: float = 0.0            # unix timestamp of first access
    token_depth: int = 0               # depth in trie = prefix length in tokens
    model: str = ""                    # which model this prefix belongs to
    
    # Future (Phase 2): bridge to actual KV block
    block_ids: list[str] = field(default_factory=list)
```

**Key operations:**

```
insert(token_ids)     → walk trie, create nodes, increment counts
lookup(token_ids)     → return longest matching prefix + match depth
eviction_candidates() → return nodes ranked by eviction score
hot_prefixes(n)       → return top-N nodes by count, above min_depth threshold
```

**Trie segmentation:** Each model gets its own root node. Token IDs are model-specific — the same string produces different IDs across different tokenizers. Mixing them in one trie would be incorrect.

```
trie_roots: dict[str, TrieNode]  # model_name → root
```

**Minimum prefix depth:** Very short prefixes (< 20 tokens) are noise. We only record a trie hit if the shared prefix is above `MIN_PREFIX_TOKENS` (configurable, default: 32 tokens = ~24 words). This avoids polluting the trie with trivial common prefixes like role tokens.

**Concurrency:** The trie is mutated on every request. In an async FastAPI context, mutations must be protected. Options:
- `asyncio.Lock` per model root (simple, correct for single-process)
- Read-write lock for lookup vs. insert separation (better throughput)
- Immutable trie with copy-on-write (overengineered for v1)

Use `asyncio.Lock` per model in v1.

---

### 4.4 Analytics Store

**Responsibilities:**
- Persist trie traversal events (hit/miss, depth, model, timestamp)
- Compute aggregate metrics on demand
- Support time-windowed queries (last 1h, 24h, 7d)

**Storage:** SQLite in v1. Fast enough for single-process, zero infrastructure dependency, easy to query with raw SQL for debugging.

**Schema:**

```sql
CREATE TABLE prefix_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,           -- unix timestamp
    model       TEXT NOT NULL,
    request_id  TEXT NOT NULL,           -- uuid per request
    prompt_tokens INTEGER NOT NULL,      -- total prompt token count
    shared_prefix_tokens INTEGER,        -- tokens shared with trie (null = miss)
    is_hit      INTEGER NOT NULL,        -- 0 or 1
    backend_latency_ms REAL              -- filled post-response
);

CREATE TABLE hot_prefixes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    model       TEXT NOT NULL,
    prefix_hash TEXT NOT NULL,           -- sha256 of token_ids for the prefix
    token_depth INTEGER NOT NULL,
    count       INTEGER NOT NULL,
    last_seen   REAL NOT NULL,
    first_seen  REAL NOT NULL
);
```

**Key metrics exposed:**

| Metric | Formula |
|---|---|
| Cache hit rate | `hits / total_requests` |
| Token reuse ratio | `sum(shared_prefix_tokens) / sum(prompt_tokens)` |
| Theoretical compute savings | `token_reuse_ratio * 100%` (proxy for FLOP reduction) |
| Hot prefix count | Distinct prefixes above `MIN_PREFIX_TOKENS` with `count > threshold` |
| Avg shared prefix depth | `mean(shared_prefix_tokens)` on hits |

---

### 4.5 Eviction Policy Engine

Pure logic layer — no GPU, no tensors. Takes a snapshot of trie node metadata and returns an ordered eviction list.

**Interface:**

```python
class EvictionPolicy(ABC):
    @abstractmethod
    def rank(self, nodes: list[TrieNode]) -> list[TrieNode]:
        """Return nodes ordered from most to least evictable."""
        ...
```

**Implemented policies:**

**LRU (baseline):**
```
score = current_time - last_seen
```
Higher score = evict first.

**LFU-with-decay:**
```
score = count / (1 + decay_rate * (current_time - first_seen))
```
Lower score = evict first. Frequency decays over time — a prefix hot last week is less valuable than one hot today.

**Cost-aware:**
```
recompute_cost = token_depth * COST_PER_TOKEN
eviction_score = recompute_cost / (count * recency_weight)
```
Evict nodes where the recompute cost is low *and* the reuse frequency doesn't justify keeping them. A 2000-token system prompt used 500 times/day is never evicted. A 50-token prefix used twice last week is a candidate.

**Policy selection:** Configurable via `config.yaml`. Default: `cost_aware`.

---

### 4.6 Dashboard

**Technology:** Streamlit (v1) — fast to build, runs locally, no frontend complexity.

**Views:**

1. **Overview** — hit rate, token reuse ratio, total requests, savings estimate
2. **Hot Prefixes** — table of top-N prefixes by count, with depth and last-seen
3. **Timeline** — hit rate over time (rolling 1h/24h window)
4. **Eviction Preview** — what the current policy would evict if cache pressure hit

No authentication in v1. Local tool only.

---

## 5. Data Flow: Single Request

```
1. Client → POST /v1/chat/completions {model, messages, ...}

2. Proxy:
   a. Assign request_id (UUID)
   b. Extract model, messages
   c. Pass to TokenizerPipeline → token_ids[]

3. PrefixTrie.lookup(model, token_ids):
   a. Walk trie from root
   b. Find longest matching prefix
   c. Return (matched_depth, is_hit)

4. PrefixTrie.insert(model, token_ids):
   a. Walk trie, creating nodes as needed
   b. Increment counts, update timestamps

5. AnalyticsStore.record_event(request_id, model, prompt_tokens, shared_prefix_tokens, is_hit)

6. Proxy → forward original request to backend (vLLM / Ollama)

7. Backend → response (streaming or complete)

8. Proxy → response to client

9. [post-response] AnalyticsStore.update_latency(request_id, backend_latency_ms)
```

Steps 3-5 are async and happen concurrently with step 6. The proxy does not wait for trie operations before forwarding — analytics must not add latency to the critical path.

---

## 6. Configuration

`config.yaml`:

```yaml
proxy:
  host: 0.0.0.0
  port: 8080

backend:
  url: http://localhost:11434   # Ollama default
  timeout_seconds: 120

tokenizer:
  model_map:
    llama3: meta-llama/Meta-Llama-3-8B-Instruct
    mistral: mistralai/Mistral-7B-Instruct-v0.2
    # add models as needed

trie:
  min_prefix_tokens: 32         # ignore prefixes shorter than this
  max_nodes_per_model: 50000    # memory cap — trigger eviction above this

eviction:
  policy: cost_aware            # lru | lfu_decay | cost_aware
  cost_per_token: 1.0           # relative unit, tunable
  decay_rate: 0.01              # for lfu_decay policy

analytics:
  db_path: ./data/cache_analytics.db
  retention_days: 30

dashboard:
  port: 8501
```

---

## 7. Phased Roadmap

### Phase 1 — Observability (current scope)
**Goal:** Know exactly what's happening with prefix reuse. No GPU required.

- [ ] Proxy layer (FastAPI, transparent forwarding)
- [ ] Tokenizer pipeline (HuggingFace, chat template application)
- [ ] Prefix trie (insert, lookup, hot prefix queries)
- [ ] Analytics store (SQLite, event recording)
- [ ] Eviction policy engine (LRU, LFU-decay, cost-aware — pure logic)
- [ ] Dashboard (Streamlit, key metrics)
- [ ] Config system (YAML, model map)
- [ ] Tests for trie and eviction policies (no model needed)

**Exit criteria:** Can run against a local Ollama instance, see real hit rates and hot prefixes from actual traffic.

---

### Phase 2 — vLLM Integration (GPU required)
**Goal:** Actually influence eviction decisions in vLLM's block manager.

- [ ] Fork / patch vLLM block manager to expose eviction hooks
- [ ] Map trie nodes → vLLM block IDs (bridge the control plane to data plane)
- [ ] Drive eviction from cost-aware policy instead of LRU
- [ ] Measure actual cache hit rate improvement vs. baseline vLLM
- [ ] CPU block offload: serialize evicted KV blocks to CPU RAM (safetensors)
- [ ] Reload path: restore KV blocks from CPU RAM on cache miss

**Exit criteria:** Measurable reduction in prompt processing time for repeated prefixes vs. vanilla vLLM.

---

### Phase 3 — Distributed Cache (multi-replica)
**Goal:** Share KV cache across multiple vLLM replicas.

- [ ] Shared metadata store (Redis) for cross-replica trie state
- [ ] KV block serialization and transport layer (same-host: shared memory; cross-host: gRPC + safetensors)
- [ ] Coherence protocol: which replica owns which blocks
- [ ] Cache warming on replica startup (pre-populate from hot prefix list)
- [ ] Load balancer integration: route requests with known-hot prefixes to the replica holding those blocks

**Exit criteria:** Two replicas sharing a prefix show no redundant recomputation for that prefix.

---

## 8. Key Design Decisions and Rationale

| Decision | Rationale |
|---|---|
| Token IDs as trie keys, not strings | String equality is insufficient — same string tokenizes differently across models. Trie must operate on the same token sequence the model sees. |
| Proxy is non-invasive (no request modification) | Trust boundary. We observe, we don't interfere. If the manager crashes, it fails open — requests still reach the backend. |
| Eviction policy is pure logic (no GPU state) | Separates concerns. Policy can be tested, benchmarked, and swapped without a GPU. Bridge to actual KV blocks is Phase 2. |
| SQLite for analytics in v1 | Zero infrastructure. Single file. Easy to inspect with any SQLite client. PostgreSQL is premature. |
| Per-model trie roots | Token ID spaces are model-specific. Mixing them would produce incorrect prefix matches. |
| Async trie operations off critical path | Analytics must not add latency. Trie insert and DB write happen concurrently with backend forwarding. |
| Min prefix depth threshold | Short prefixes (role tokens, boilerplate) are universal noise. Only prefixes above the threshold represent meaningful reuse opportunity. |
| Chat template application before tokenizing | The model processes the templated token sequence, not raw message content. Trie must match on what the model actually sees. |

---

## 9. Open Questions

- **Q1:** What's the right `min_prefix_tokens` default? 32 is a guess. Need real traffic data to calibrate.
- **Q2:** How do we handle tokenizer version drift? Same model, different tokenizer versions → different token IDs for the same string. Need tokenizer pinning.
- **Q3:** For streaming responses, what's the right buffer strategy to capture completion tokens without adding perceived latency?
- **Q4:** Should the trie persist across restarts? SQLite-backed trie vs. in-memory with warm-up from analytics DB on startup.
- **Q5:** How do we handle multi-turn conversation growth? Each turn extends the prefix — the trie could grow very deep for long sessions. Need a max-depth cap or path compression.
- **Q6:** Path compression (Patricia trie / radix trie) — when does it become necessary? At 50k nodes? 500k?

---

## 10. Repository Structure

```
llm-kv-cache-manager/
├── README.md
├── DESIGN.md                    ← this file
├── config.yaml                  ← default config
├── pyproject.toml
│
├── proxy/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI app, entry point
│   ├── middleware.py             ← request interception, request_id assignment
│   └── backend.py               ← httpx client, backend forwarding
│
├── tokenizer/
│   ├── __init__.py
│   ├── pipeline.py              ← model → tokenizer mapping, chat template application
│   └── model_map.py             ← model name → HuggingFace identifier
│
├── trie/
│   ├── __init__.py
│   ├── node.py                  ← TrieNode dataclass
│   ├── prefix_trie.py           ← trie operations (insert, lookup, hot prefixes)
│   └── trie_manager.py          ← per-model trie registry, concurrency control
│
├── eviction/
│   ├── __init__.py
│   ├── base.py                  ← EvictionPolicy ABC
│   ├── lru.py
│   ├── lfu_decay.py
│   └── cost_aware.py
│
├── analytics/
│   ├── __init__.py
│   ├── store.py                 ← SQLite write path
│   ├── queries.py               ← read queries, metric computation
│   └── schema.sql
│
├── dashboard/
│   └── app.py                   ← Streamlit dashboard
│
└── tests/
    ├── test_trie.py
    ├── test_eviction.py
    ├── test_tokenizer.py
    └── fixtures/
        └── sample_conversations.json
```

---

## 11. Success Metrics

| Metric | Phase 1 Target | Phase 2 Target |
|---|---|---|
| Proxy overhead | < 5ms p99 added latency | < 5ms p99 |
| Token reuse ratio (on realistic workloads) | Measured and reported | Measured and reported |
| Cache hit rate (trie-level) | Measured | ≥ 40% on templated workloads |
| Prompt processing speedup | N/A (no GPU) | Measurable reduction vs. vanilla vLLM |
| Test coverage (trie + eviction) | ≥ 80% | ≥ 80% |

---

*This document is a living spec. Update it as decisions get made or invalidated by implementation reality.*
