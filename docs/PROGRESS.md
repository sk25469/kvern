# LLM KV Cache Manager — Progress Log

> **Author:** Sahil  
> **Last Updated:** April 12, 2026  
> **Status:** Phase 1 — Notebook Prototype Complete

---

## Session 1 — Notebook Prototype (April 12, 2026)

### What Was Built

A self-contained Colab notebook validating the core data structures and pipeline described in DESIGN.md — no FastAPI, no SQLite, no GPU. Pure logic proof.

**Stack:** `transformers` (HuggingFace), `meta-llama/Llama-3.2-1B-Instruct`, Python dataclasses.

---

### 1. Tokenizer Pipeline — Validated

Confirmed the full pipeline: `messages[]` → chat template → flat string → token IDs.

```python
model_id = "meta-llama/Llama-3.2-1B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_id)

messages = [
    {"role": "system", "content": "You are a helpful coding assistant."},
    {"role": "user", "content": "How do I build a Trie in Python?"}
]

templated_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
token_ids = tokenizer.encode(templated_text)
# Total: 52 tokens
```

Confirmed that `apply_chat_template` must happen before `encode` — the model processes the templated sequence, not raw message content. This matches the design decision in §8.

---

### 2. MiniTrie — Implemented

```python
@dataclass
class MiniNode:
    token_id: int
    children: Dict[int, 'MiniNode'] = field(default_factory=dict)
    count: int = 1

class MiniTrie:
    def insert(self, tokens: List[int]): ...
    def find_prefix(self, tokens: List[int]) -> int: ...  # returns match length
    def get_total_nodes(self): ...
    def evict(self, target_node_count): ...  # leaf-eviction by count
```

Simpler than the full `TrieNode` spec in DESIGN.md §4.3 — no `last_seen`, `first_seen`, `token_depth`, or `block_ids`. Sufficient to validate the structural logic.

---

### 3. Multi-Turn Prefix Sharing — Validated

```
Turn 1: system prompt + "Hello!"           → inserted as root path
Turn 2: Turn 1 history + "Explain Tries."  → find_prefix() matched all of Turn 1
```

`find_prefix()` returned the full length of Turn 1's token sequence as the shared prefix for Turn 2 — meaning in a real serving scenario, all those KV entries would be reusable. The efficiency metric printed correctly.

---

### 4. Trie Visualization — Implemented

```python
def visualize(node, tokenizer, indent="", is_last=True):
    token_text = tokenizer.decode([node.token_id]).replace("\n", "\\n")
    # ... recursive tree print with ├── / └── markers
```

Output (truncated):
```
ROOT
└── '<|begin_of_text|>' (ID: 128000, Hits: 6)
    └── '<|begin_of_text|>' (ID: 128000, Hits: 6)
        └── '<|start_header_id|>' (ID: 128006, Hits: 6)
            └── 'system' (ID: 9125, Hits: 6)
                ...
                └── ' helpful' (ID: 11190, Hits: 6)
                    └── ' assistant' (ID: 18328, Hits: 6)
                        └── '.' (ID: 13, Hits: 6)
                            └── '<|eot_id|>' (ID: 128009, Hits: 6)
                                ...
                                └── 'Question' (ID: 14924, Hits: 5)
                                    └── ' ' (ID: 220, Hits: 5)
                                        ├── '0' (ID: 15, Hits: 1)
                                        ├── '1' (ID: 16, Hits: 1)
                                        ├── '2' (ID: 17, Hits: 1)
                                        ├── '3' (ID: 18, Hits: 1)
                                        └── '4' (ID: 19, Hits: 1)
```

The trie correctly encoded the shared/divergent boundary without being explicitly told where it was. The deep spine (count=6) is the hot system prompt prefix. The 5 leaf branches (count=1 each) are unique question tails. Structurally correct.

---

### 5. Eviction — Validated (with a discovered bug)

Inserted 5 variations (`Question 0` through `Question 4`), then evicted down to 45 nodes:

```
Nodes before eviction: 56
Evicted Token ID 128009 with 1 hits.   # <eot_id> after Q0
Evicted Token ID 15     with 1 hits.   # '0'
Evicted Token ID 128009 with 1 hits.   # <eot_id> after Q1
Evicted Token ID 16     with 1 hits.   # '1'
... (Q2, Q3, Q4 similarly)
Evicted Token ID 220    with 5 hits.   # ' ' — space before question number
Nodes after eviction: 45
```

The first 10 evictions are correct — low-count leaf nodes. But the final eviction (token `' '`, ID 220, count=5) reveals the flaw in naive leaf-LRU: **it's blind to depth**.

That space token sits at depth ~47 in the trie. Evicting it means any future request matching that path would need to recompute 47 tokens worth of KV entries. A node at depth 2 with count=3 would be a far cheaper eviction by recompute cost. Hit count alone is the wrong signal.

This empirically confirms the need for the cost-aware eviction policy from DESIGN.md §4.5:

```
eviction_score = recompute_cost / (count * recency_weight)
# where recompute_cost = token_depth * COST_PER_TOKEN
```

The `token_depth` field on `TrieNode` exists precisely to make this calculation possible.

---

### 6. Key Finding — Runtime Template Drift (new open question)

Llama 3.2's chat template injects the current date into every system prefix:

```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

Cutting Knowledge Date: December 2023
Today Date: 12 Apr 2026

You are a helpful assistant.
```

This means **the system prefix token sequence changes every day at midnight**. Any trie nodes built on yesterday's prefix are stale — the token IDs for the date segment differ. This is worse than tokenizer version drift (DESIGN.md Q2) because it's runtime-deterministic and silent: no error, just a cold cache every 24 hours.

**Mitigation options:**
- Strip or normalize the date segment before trie insertion (requires template-aware parsing)
- Accept daily cache cold-start as a known cost
- Pin the date in the template for caching purposes (hacky, breaks model behavior)

Added as **Q7** to open questions.

---

### What This Validates from DESIGN.md

| Design Component | Status |
|---|---|
| Tokenizer pipeline (§4.2) | ✅ Validated — chat template + encode works correctly |
| Prefix trie insert + lookup (§4.3) | ✅ Validated — correct prefix matching across turns |
| Trie segmentation per model | ⬜ Not tested — single model only |
| Multi-turn context growth | ✅ Validated — trie correctly extends path per turn |
| Eviction — LRU by count | ✅ Implemented, flaw identified |
| Eviction — cost-aware | ⬜ Not yet implemented — need `token_depth` on nodes |
| Analytics store (§4.4) | ⬜ Not yet — no SQLite |
| Proxy layer (§4.1) | ⬜ Not yet — no FastAPI |
| Dashboard (§4.6) | ⬜ Not yet |

---

### Gap to Phase 1 Complete

The notebook validated everything structural. What remains for a shippable Phase 1:

1. **Add `token_depth` to `MiniNode`** → enables cost-aware eviction (straightforward)
2. **Implement cost-aware eviction policy** → replace leaf-count sort with `depth / count` score
3. **Wrap in async FastAPI proxy** → transparent forwarding + async trie ops off critical path
4. **SQLite analytics store** → persist events, compute hit rate / token reuse ratio
5. **Per-model trie roots** → `dict[str, TrieNode]` with `asyncio.Lock` per model
6. **Streamlit dashboard** → read from SQLite, display key metrics

The core data structure is done. The rest is plumbing.

---

### Updated Open Questions

From DESIGN.md §9, plus new:

- **Q1:** Right `min_prefix_tokens` default? 32 is still a guess — need real traffic.
- **Q2:** Tokenizer version pinning — same model, different tokenizer version = different IDs.
- **Q3:** Streaming buffer strategy for completion token capture.
- **Q4:** Trie persistence across restarts.
- **Q5:** Max-depth cap for long multi-turn sessions.
- **Q6:** When does path compression become necessary?
- **Q7 (new):** Runtime template drift — Llama 3.2 injects today's date into the system prefix, invalidating the trie daily. Need a normalization strategy before trie insertion.
