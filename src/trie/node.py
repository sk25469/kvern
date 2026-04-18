from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TrieNode:
    """
    A single node in the token-level prefix trie.

    `token_depth` is the depth of this node from the model root (= prefix length in tokens).
    `count` is incremented at every node along the insert path — not just at the terminal node.
    This means count = "how many requests shared *at least* this prefix", which is the correct
    signal for eviction scoring (depth / count).

    `block_ids` is a Phase 2 bridge — maps this node to actual vLLM KV block IDs once
    the control plane is wired to GPU memory.
    """
    children:    dict[int, TrieNode] = field(default_factory=dict)
    count:       int   = 0
    last_seen:   float = 0.0   # unix timestamp of last access
    first_seen:  float = 0.0   # unix timestamp of node creation
    token_depth: int   = 0     # depth from model root = prefix length in tokens

    # Phase 2: bridge to vLLM KV block IDs
    block_ids: list[str] = field(default_factory=list)