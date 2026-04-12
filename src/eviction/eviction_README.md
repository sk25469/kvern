# eviction

Pure logic layer. Takes a snapshot of trie node metadata and returns an ordered list of eviction candidates. **No GPU, no tensors, no I/O.** The eviction engine reasons about *which* nodes to evict — the actual eviction of GPU KV blocks is the trie manager's job in Phase 2.

This separation is deliberate: the policy can be tested, benchmarked, and swapped without any model infrastructure.

---

## Responsibilities

- Implement pluggable eviction policies via a common interface
- Score trie nodes based on frequency, recency, and recomputation cost
- Return nodes ordered from most to least evictable
- Never touch GPU memory, the trie directly, or any I/O

---

## The interface

```python
from abc import ABC, abstractmethod

class EvictionPolicy(ABC):
    @abstractmethod
    def rank(self, nodes: list[TrieNode]) -> list[TrieNode]:
        """
        Return nodes ordered from most evictable (index 0)
        to least evictable (index -1).
        """
        ...
```

The trie manager calls `policy.rank(candidates)` and evicts from the front of the returned list until it's under the memory cap.

---

## Implemented policies

### LRU — Least Recently Used (baseline)

```
eviction_score = current_time - node.last_seen
```

Higher score → evict first. Simple, well-understood, wrong for LLM workloads.

**Why it's wrong:** A 2000-token system prompt used by 10,000 users/day but not accessed in the last 60 seconds scores higher than a 50-token throwaway prefix accessed 5 seconds ago. LRU is blind to recomputation cost and access frequency.

Use this as a baseline to measure improvement from smarter policies.

---

### LFU with decay — Least Frequently Used, time-decayed

```
eviction_score = count / (1 + decay_rate * (current_time - first_seen))
```

Lower score → evict first. Frequency is the primary signal, but it decays over time — a prefix that was hot last week and cold today is worth less than one that's hot right now.

`decay_rate` is configurable (default: `0.01`). Higher values make old frequency data stale faster.

**Better than LRU** for workloads with stable hot prefixes (e.g. a fixed system prompt). Still blind to recomputation cost.

---

### Cost-aware (default)

```
recompute_cost  = node.token_depth * COST_PER_TOKEN
recency_weight  = 1 / (1 + (current_time - node.last_seen))
eviction_score  = recompute_cost / (node.count * recency_weight)
```

Higher score → keep. Lower score → evict first.

The intuition: **evict nodes where the cost of recomputing them is low and nobody's been using them.** A 2000-token system prompt used 500 times today has a massive `recompute_cost * count * recency_weight` — it is never evicted. A 40-token prefix seen twice last week has a tiny score — first to go.

`COST_PER_TOKEN` is a relative unit (default: `1.0`). It doesn't need to map to real dollars — it's a scaling factor that weights depth in the score. Increase it to make the policy more reluctant to evict deep nodes.

**This is the default policy.** It's the only one that correctly handles the asymmetry between a system prompt (deep, frequently reused) and a long conversation tail (deep, seen once).

---

## Why LRU is the wrong default for LLMs

Standard caching systems use LRU because access cost is roughly uniform — a cache miss for a 10-byte string costs about the same as a cache miss for a 100-byte string. In LLM inference, this assumption breaks completely.

A cache miss for a 2000-token prefix means **2000 tokens of attention computation across every transformer layer** — quadratic in sequence length. A cache miss for a 50-token prefix is trivial. LRU treats both evictions as equivalent. Cost-aware does not.

This is the fundamental insight that makes KVern's eviction engine more than a reimplementation of existing tools.

---

## Files

| File | Purpose |
|---|---|
| `base.py` | `EvictionPolicy` ABC |
| `lru.py` | LRU implementation |
| `lfu_decay.py` | LFU-with-decay implementation |
| `cost_aware.py` | Cost-aware implementation (default) |

---

## Configuration (from `config.yaml`)

```yaml
eviction:
  policy: cost_aware          # lru | lfu_decay | cost_aware
  cost_per_token: 1.0         # relative weight for token depth in cost-aware
  decay_rate: 0.01            # for lfu_decay: how fast old frequency data ages out
```

---

## Testing

All three policies are pure functions of node metadata — no side effects, no I/O. Tests generate synthetic `TrieNode` lists with controlled `count`, `last_seen`, `first_seen`, and `token_depth` values and assert correct ordering.

Key test cases:
- LRU: node with older `last_seen` ranks before node with recent `last_seen`
- LFU-decay: high-count node survives over low-count node of same age
- LFU-decay: old high-count node eventually loses to recent low-count node as decay accumulates
- Cost-aware: deep node with high count is never evicted over shallow node with low count
- Cost-aware: shallow, stale, rarely-used node is always first candidate
- Policy swapping: same node list, different policy, different ordering

See `tests/test_eviction.py`.

---

## Phase roadmap

- **Phase 1:** All three policies implemented as pure logic, exercised on synthetic trie snapshots
- **Phase 2:** Eviction policy output is wired to the vLLM block manager — `rank()` output drives actual GPU block eviction; cost model can be calibrated against real measured latency per token
- **Phase 3:** Policy becomes aware of cross-replica block placement — eviction considers whether another replica holds a copy before freeing a block
