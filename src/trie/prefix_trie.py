"""
prefix_trie.py — Core trie operations.

All functions are stateless and take an explicit root node. They know nothing about
models, locks, or memory caps — that's trie_manager.py's job. This makes every
operation independently testable with synthetic token ID sequences, no proxy needed.

Eviction note:
    Only leaf nodes are evicted in Phase 1 (nodes with empty `children`). This avoids
    the cascade problem of orphaning subtrees. We collect (parent, token_id, node)
    triples so deletion is O(1) — just `del parent.children[token_id]`.
"""

from __future__ import annotations
import time
from typing import Iterator

from .node import TrieNode


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def insert(root: TrieNode, token_ids: list[int], now: float | None = None) -> None:
    """
    Walk the trie from root, creating nodes as needed.

    Increments `count` and updates `last_seen` at *every* node along the path —
    not just the terminal node. This means node.count = number of requests that
    shared at least this prefix, which is what eviction scoring needs.

    `token_depth` is set once at node creation and never changes.
    """
    if now is None:
        now = time.time()

    node = root
    for depth, token_id in enumerate(token_ids, start=1):
        if token_id not in node.children:
            node.children[token_id] = TrieNode(
                count=1,
                first_seen=now,
                last_seen=now,
                token_depth=depth,
            )
        else:
            child = node.children[token_id]
            child.count += 1
            child.last_seen = now
        node = node.children[token_id]


def lookup(
    root: TrieNode,
    token_ids: list[int],
    min_prefix_tokens: int = 32,
) -> tuple[int, bool]:
    """
    Walk the trie and return the length of the longest matching prefix.

    Returns:
        (matched_depth, is_hit)
        matched_depth — number of tokens matched (0 if nothing matched)
        is_hit        — True if matched_depth >= min_prefix_tokens

    Read-only: does not mutate the trie. No lock needed in single-process context.
    """
    node = root
    depth = 0
    for token_id in token_ids:
        if token_id not in node.children:
            break
        node = node.children[token_id]
        depth += 1
    return depth, depth >= min_prefix_tokens


# ---------------------------------------------------------------------------
# Query operations
# ---------------------------------------------------------------------------

def hot_prefixes(
    root: TrieNode,
    n: int,
    min_prefix_tokens: int = 32,
) -> list[TrieNode]:
    """
    Return the top-N nodes by count with token_depth >= min_prefix_tokens.

    These are the "hot spine" nodes — the deepest points on frequently-traversed
    paths before the trie forks into unique suffixes. In a real workload, the
    system prompt shows up here as a single node with count=N_requests.

    Uses iterative DFS to avoid recursion depth issues on deep tries.
    """
    candidates: list[TrieNode] = []
    stack: list[TrieNode] = list(root.children.values())

    while stack:
        node = stack.pop()
        if node.token_depth >= min_prefix_tokens:
            candidates.append(node)
        stack.extend(node.children.values())

    candidates.sort(key=lambda n: n.count, reverse=True)
    return candidates[:n]


def eviction_candidates(root: TrieNode) -> list[tuple[TrieNode, int, TrieNode]]:
    """
    Collect all leaf nodes as (parent, token_id, node) triples.

    Only leaf nodes are eligible for eviction in Phase 1. This avoids the cascade
    problem: evicting a non-leaf would orphan its entire subtree, wiping out deep
    hot paths silently. Leaf-only eviction is conservative but safe.

    The (parent, token_id) pair enables O(1) deletion:
        del parent.children[token_id]

    The eviction engine (eviction/) ranks these by policy score and calls
    evict_nodes() with the subset it wants removed.
    """
    results: list[tuple[TrieNode, int, TrieNode]] = []
    # stack entries: (node, parent, token_id_in_parent)
    stack: list[tuple[TrieNode, TrieNode | None, int | None]] = [
        (root, None, None)
    ]

    while stack:
        node, parent, token_id = stack.pop()
        is_leaf = len(node.children) == 0
        if is_leaf and parent is not None:
            results.append((parent, token_id, node))  # type: ignore[arg-type]
        else:
            for tid, child in node.children.items():
                stack.append((child, node, tid))

    return results


def evict_nodes(
    candidates: list[tuple[TrieNode, int, TrieNode]],
    target_count: int,
) -> int:
    """
    Evict up to `target_count` nodes from the trie.

    `candidates` should already be ranked most-to-least evictable by the eviction
    engine. We just execute deletions here — policy logic lives in eviction/.

    Returns the number of nodes actually evicted.
    """
    evicted = 0
    for parent, token_id, _node in candidates:
        if evicted >= target_count:
            break
        # Guard: another eviction in the same pass may have already removed this
        if token_id in parent.children:
            del parent.children[token_id]
            evicted += 1
    return evicted


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def node_count(root: TrieNode) -> int:
    """Count all nodes in the trie (excluding root). Iterative DFS."""
    count = 0
    stack: list[TrieNode] = list(root.children.values())
    while stack:
        node = stack.pop()
        count += 1
        stack.extend(node.children.values())
    return count


def iter_nodes(root: TrieNode) -> Iterator[TrieNode]:
    """Yield every node in the trie (excluding root). Iterative DFS."""
    stack: list[TrieNode] = list(root.children.values())
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children.values())


def is_leaf(node: TrieNode) -> bool:
    """Return True if this node has no children (is a leaf node)."""
    return len(node.children) == 0


def evict_node(parent: TrieNode, token_id: int) -> bool:
    """
    Remove a direct child node from parent.
    
    Args:
        parent: The parent node
        token_id: The token ID of the child to remove
        
    Returns:
        True if the node was found and removed, False otherwise
    """
    if token_id in parent.children:
        del parent.children[token_id]
        return True
    return False