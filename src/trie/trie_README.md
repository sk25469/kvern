# trie

The core data structure of KVern. A **token-level prefix trie** where each path from root to node represents a token sequence seen in at least one prior request. Every request walks this trie to find how much of its prompt was already processed in a previous request — that shared depth is the reuse signal.

---

## Responsibilities

- Insert token ID sequences from incoming requests
- Look up the longest matching prefix for a given token sequence
- Track frequency, recency, and depth metadata per node
- Expose hot prefix queries (top-N most reused prefixes)
- Produce eviction candidate lists for the eviction engine
- Enforce per-model isolation (separate trie root per model)

---

## Node structure

```python
@dataclass
class TrieNode:
    children:    dict[int, 'TrieNode']  # token_id → child
    count:       int   = 0              # times this prefix was traversed
    last_seen:   float = 0.0            # unix timestamp of last access
    first_seen:  float = 0.0            # unix timestamp of creation
    token_depth: int   = 0              # depth = prefix length in tokens
    model:       str   = ""             # owning model

    # Phase 2 bridge
    block_ids: list[str] = field(default_factory=list)
```

`count` is incremented on every `insert()` traversal — not just at the terminal node, but at every node along the path. This means a node's count represents how many requests shared *at least* this prefix, which is the right metric for eviction scoring.

---

## Operations

### `insert(model, token_ids)`
Walk the trie from the model root, creating nodes as needed. Increment `count` and update `last_seen` at every node along the path. `first_seen` is set only on node creation.

### `lookup(model, token_ids) → (matched_depth, is_hit)`
Walk the trie from the model root. Return the depth of the longest matching prefix and whether it exceeded `MIN_PREFIX_TOKENS`. Does not modify the trie.

### `hot_prefixes(model, n) → list[TrieNode]`
Return the top-N nodes by `count` with `token_depth >= MIN_PREFIX_TOKENS`. Used by the dashboard and eviction engine.

### `eviction_candidates(model) → list[TrieNode]`
Return all leaf nodes (or nodes above `MAX_NODES_PER_MODEL` threshold) sorted by the configured eviction policy score. Consumed by the eviction engine.

---

## Per-model isolation

Token ID spaces are model-specific. The same string tokenizes to different IDs across different models. Mixing them in a single trie produces false prefix matches.

Each model gets its own root node:

```python
_roots: dict[str, TrieNode] = {}

def _get_root(model: str) -> TrieNode:
    if model not in _roots:
        _roots[model] = TrieNode(children={}, model=model)
    return _roots[model]
```

---

## Minimum prefix depth

Short prefixes are noise. Role tokens, BOS tokens, and common preamble appear in virtually every request — treating them as cache hits is meaningless.

Only prefixes longer than `MIN_PREFIX_TOKENS` (default: 32, configurable) are counted as hits. Insert still walks the full sequence, but `lookup()` only returns `is_hit=True` above this threshold.

---

## Concurrency

The trie is mutated on every request. In an async FastAPI process, concurrent requests can race on `insert()`. Each model root is protected by its own `asyncio.Lock`:

```python
_locks: dict[str, asyncio.Lock] = {}
```

`lookup()` is read-only and does not require a lock — Python's GIL provides sufficient protection for dict reads in a single-process context.

For Phase 3 (multi-process or distributed), this moves to a Redis-backed shared structure with distributed locking.

---

## Memory cap and eviction trigger

When a model's node count exceeds `MAX_NODES_PER_MODEL` (default: 50,000), the trie manager signals the eviction engine to prune. Eviction removes leaf nodes first, preserving deep shared paths.

A single node with a 1000-token path uses roughly:
- `TrieNode` dataclass: ~200 bytes
- `children` dict entry in parent: ~50 bytes

At 50,000 nodes: ~12MB per model. Acceptable for Phase 1.

---

## Path compression (future)

The current implementation is an uncompressed trie — every token gets its own node. For long unique suffixes (a conversation tail seen only once), this wastes memory.

A Patricia trie (radix trie) compresses runs of single-child nodes into one edge. This is tracked as open question Q6 in `DESIGN.md` and is not implemented in Phase 1.

---

## Files

| File | Purpose |
|---|---|
| `node.py` | `TrieNode` dataclass definition |
| `prefix_trie.py` | `insert`, `lookup`, `hot_prefixes`, `eviction_candidates` |
| `trie_manager.py` | Per-model root registry, lock management, memory cap enforcement |

---

## Configuration (from `config.yaml`)

```yaml
trie:
  min_prefix_tokens: 32       # ignore hits below this depth
  max_nodes_per_model: 50000  # trigger eviction above this
```

---

## Testing

The trie can be tested entirely without a model, GPU, or running proxy. Tests operate on synthetic token ID sequences.

Core test cases:
- Insert and lookup: shared prefix correctly identified at exact depth
- No false positives: distinct prefixes produce `is_hit=False`
- Count accumulation: repeated inserts increment counts at every node on the path
- Model isolation: same token sequence under different model names walks separate tries
- Min depth threshold: a hit at depth 10 returns `is_hit=False` when `MIN_PREFIX_TOKENS=32`
- Concurrent inserts: no data corruption under concurrent async inserts

See `tests/test_trie.py`.

---

## Phase roadmap

- **Phase 1:** Full trie implementation, per-model isolation, concurrency control, memory cap
- **Phase 2:** `block_ids` field populated — bridge to actual vLLM KV block IDs; eviction drives GPU memory
- **Phase 3:** Redis-backed distributed trie for cross-replica prefix sharing; path compression if memory pressure warrants it
