"""
tests/test_trie.py

Tests for the trie layer. No tokenizer, no proxy, no GPU.
All tests operate on synthetic integer token ID sequences.

Run with: pytest tests/test_trie.py -v
"""

import asyncio
import time

import pytest

from src.trie.node import TrieNode
from src.trie.prefix_trie import (
    evict_node,
    eviction_candidates,
    hot_prefixes,
    insert,
    is_leaf,
    lookup,
    node_count,
)
from src.trie.manager import KVPrefixManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_root() -> TrieNode:
    return TrieNode()


# Synthetic sequences that share a prefix
SYSTEM_PROMPT = list(range(100))          # tokens 0..99 — simulates a system prompt
Q1 = SYSTEM_PROMPT + [200, 201, 202]      # system + question 1
Q2 = SYSTEM_PROMPT + [300, 301]           # system + question 2
Q3 = SYSTEM_PROMPT + [400]               # system + question 3
UNRELATED = list(range(500, 540))         # completely different


# ---------------------------------------------------------------------------
# insert + lookup — core correctness
# ---------------------------------------------------------------------------

class TestInsertLookup:

    def test_lookup_on_empty_trie_returns_zero_depth(self):
        root = make_root()
        depth, is_hit = lookup(root, Q1, min_prefix_tokens=32)
        assert depth == 0
        assert is_hit is False

    def test_exact_prefix_match(self):
        root = make_root()
        insert(root, Q1)
        # Q2 shares SYSTEM_PROMPT (100 tokens) with Q1
        depth, is_hit = lookup(root, Q2, min_prefix_tokens=32)
        assert depth == len(SYSTEM_PROMPT)
        assert is_hit is True

    def test_full_sequence_match(self):
        root = make_root()
        insert(root, Q1)
        depth, is_hit = lookup(root, Q1, min_prefix_tokens=32)
        assert depth == len(Q1)
        assert is_hit is True

    def test_no_match_unrelated_sequence(self):
        root = make_root()
        insert(root, Q1)
        depth, is_hit = lookup(root, UNRELATED, min_prefix_tokens=32)
        assert depth == 0
        assert is_hit is False

    def test_is_hit_false_below_min_prefix_tokens(self):
        root = make_root()
        short_seq = [1, 2, 3, 4, 5]  # only 5 tokens shared
        insert(root, short_seq + [99])
        depth, is_hit = lookup(root, short_seq + [100], min_prefix_tokens=32)
        assert depth == 5
        assert is_hit is False  # matched 5 < 32

    def test_is_hit_true_at_exactly_min_prefix_tokens(self):
        root = make_root()
        shared = list(range(32))
        insert(root, shared + [999])
        depth, is_hit = lookup(root, shared + [888], min_prefix_tokens=32)
        assert depth == 32
        assert is_hit is True

    def test_lookup_is_read_only(self):
        """lookup() must not create nodes."""
        root = make_root()
        lookup(root, Q1, min_prefix_tokens=32)
        assert node_count(root) == 0


# ---------------------------------------------------------------------------
# Count semantics — path-level counting
# ---------------------------------------------------------------------------

class TestCountSemantics:

    def test_count_increments_on_every_node_along_path(self):
        """
        The key invariant: count at depth D = number of requests that shared
        at least D tokens. Not just requests that terminated at depth D.
        """
        root = make_root()
        insert(root, Q1)
        insert(root, Q2)
        insert(root, Q3)

        # Walk down to depth 50 (middle of shared system prompt)
        node = root
        for token_id in SYSTEM_PROMPT[:50]:
            node = node.children[token_id]

        # All 3 requests passed through this node
        assert node.count == 3

    def test_count_at_divergence_point(self):
        """After the shared prefix, counts drop to 1 at divergent branches."""
        root = make_root()
        insert(root, Q1)
        insert(root, Q2)

        # The last shared node (end of SYSTEM_PROMPT) should have count=2
        node = root
        for token_id in SYSTEM_PROMPT:
            node = node.children[token_id]
        assert node.count == 2

        # Q1's first unique token — only Q1 goes here
        q1_branch = node.children[Q1[len(SYSTEM_PROMPT)]]
        assert q1_branch.count == 1

    def test_repeated_inserts_accumulate_count(self):
        root = make_root()
        for _ in range(10):
            insert(root, Q1)

        node = root
        for token_id in Q1:
            node = node.children[token_id]
        assert node.count == 10


# ---------------------------------------------------------------------------
# token_depth metadata
# ---------------------------------------------------------------------------

class TestTokenDepth:

    def test_token_depth_set_correctly_on_creation(self):
        root = make_root()
        insert(root, [10, 20, 30])

        node = root
        for expected_depth, token_id in enumerate([10, 20, 30], start=1):
            node = node.children[token_id]
            assert node.token_depth == expected_depth

    def test_token_depth_does_not_change_on_subsequent_inserts(self):
        root = make_root()
        insert(root, [10, 20, 30])
        insert(root, [10, 20, 30])

        node = root.children[10].children[20].children[30]
        assert node.token_depth == 3


# ---------------------------------------------------------------------------
# node_count
# ---------------------------------------------------------------------------

class TestNodeCount:

    def test_empty_trie_has_zero_nodes(self):
        root = make_root()
        assert node_count(root) == 0

    def test_non_overlapping_sequences(self):
        root = make_root()
        insert(root, [1, 2, 3])
        insert(root, [4, 5, 6])
        assert node_count(root) == 6

    def test_fully_overlapping_sequences(self):
        root = make_root()
        insert(root, [1, 2, 3])
        insert(root, [1, 2, 3, 4])
        assert node_count(root) == 4  # shared 1,2,3 + unique 4

    def test_partial_overlap(self):
        root = make_root()
        insert(root, [1, 2, 3])    # 3 nodes
        insert(root, [1, 2, 9])    # shares 1,2 + adds 9 → 4 nodes total
        assert node_count(root) == 4


# ---------------------------------------------------------------------------
# hot_prefixes
# ---------------------------------------------------------------------------

class TestHotPrefixes:

    def test_returns_most_frequent_nodes(self):
        root = make_root()
        # system prompt used 10 times, unique tails each time
        for i in range(10):
            insert(root, SYSTEM_PROMPT + [1000 + i])

        # One unrelated request
        insert(root, UNRELATED)

        top = hot_prefixes(root, n=1, min_prefix_tokens=32)
        assert len(top) == 1
        # The hot node should be deep in the system prompt path
        assert top[0].count == 10
        assert top[0].token_depth >= 32

    def test_filters_below_min_depth(self):
        root = make_root()
        insert(root, [1, 2, 3])  # depth 3, below any reasonable min
        results = hot_prefixes(root, n=10, min_prefix_tokens=32)
        assert results == []

    def test_respects_n_limit(self):
        root = make_root()
        for i in range(5):
            insert(root, SYSTEM_PROMPT + [2000 + i])
        results = hot_prefixes(root, n=2, min_prefix_tokens=32)
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------

class TestEviction:

    def test_evict_leaf_node(self):
        root = make_root()
        insert(root, [1, 2, 3])
        assert node_count(root) == 3

        # [3] is a leaf — evict it
        parent = root.children[1].children[2]
        evict_node(parent, 3)
        assert node_count(root) == 2

    def test_evict_nonexistent_token_is_noop(self):
        root = make_root()
        insert(root, [1, 2, 3])
        evict_node(root, 999)  # 999 doesn't exist under root
        assert node_count(root) == 3

    def test_eviction_candidates_excludes_root(self):
        root = make_root()
        insert(root, [1, 2, 3])
        candidates = eviction_candidates(root)
        nodes = [node for _, _, node in candidates]
        assert root not in nodes

    def test_is_leaf(self):
        root = make_root()
        insert(root, [1, 2])
        node_1 = root.children[1]
        node_2 = node_1.children[2]
        assert not is_leaf(node_1)
        assert is_leaf(node_2)


# ---------------------------------------------------------------------------
# Model isolation
# ---------------------------------------------------------------------------

class TestModelIsolation:

    def test_same_tokens_different_models_separate_tries(self):
        """
        Identical token sequences under different model names must not
        produce cross-model prefix hits. Token ID spaces are model-specific.
        """
        manager = KVPrefixManager(min_prefix_tokens=1)

        async def run():
            await manager.record("llama3", [1, 2, 3, 4, 5])
            await manager.wait_for_pending_inserts()  # Wait for first insert
            depth_llama, hit_llama = await manager.record("llama3", [1, 2, 3, 4, 5, 6])
            depth_mistral, hit_mistral = await manager.record("mistral", [1, 2, 3, 4, 5, 6])
            return depth_llama, hit_llama, depth_mistral, hit_mistral

        dl, hl, dm, hm = asyncio.run(run())
        assert hl is True   # llama3 has seen [1,2,3,4,5] before
        assert hm is False  # mistral has NOT seen [1,2,3,4,5] before

    def test_model_counts_are_independent(self):
        manager = KVPrefixManager(min_prefix_tokens=1)

        async def run():
            await manager.record("llama3", [10, 20, 30])
            await manager.record("llama3", [10, 20, 30])
            await manager.record("mistral", [10, 20, 30])
            
            # Wait for all background insert tasks to complete
            await manager.wait_for_pending_inserts()
            
            return (
                manager.node_count("llama3"),
                manager.node_count("mistral"),
            )

        llama_count, mistral_count = asyncio.run(run())
        assert llama_count == 3
        assert mistral_count == 3


# ---------------------------------------------------------------------------
# KVPrefixManager — async behavior
# ---------------------------------------------------------------------------

class TestKVPrefixManager:

    def test_record_returns_correct_depth_and_hit(self):
        manager = KVPrefixManager(min_prefix_tokens=32)

        async def run():
            await manager.record("llama3", Q1)
            # Wait for the first insert to complete before second record call
            await manager.wait_for_pending_inserts()
            return await manager.record("llama3", Q2)

        depth, is_hit = asyncio.run(run())
        assert depth == len(SYSTEM_PROMPT)
        assert is_hit is True

    def test_first_request_is_always_miss(self):
        manager = KVPrefixManager(min_prefix_tokens=32)

        async def run():
            return await manager.record("llama3", Q1)

        depth, is_hit = asyncio.run(run())
        assert depth == 0
        assert is_hit is False

    def test_get_models_reflects_seen_models(self):
        manager = KVPrefixManager(min_prefix_tokens=1)

        async def run():
            await manager.record("llama3", [1, 2])
            await manager.record("mistral", [3, 4])
            await manager.wait_for_pending_inserts()

        asyncio.run(run())
        assert set(manager.models()) == {"llama3", "mistral"}

    def test_concurrent_inserts_no_corruption(self):
        """
        Fire N concurrent inserts for the same model.
        Node count should be deterministic regardless of interleaving.
        """
        manager = KVPrefixManager(min_prefix_tokens=1)
        sequences = [SYSTEM_PROMPT + [i] for i in range(20)]

        async def run():
            tasks = [manager.record("llama3", seq) for seq in sequences]
            await asyncio.gather(*tasks)
            await manager.wait_for_pending_inserts()

        asyncio.run(run())
        # 100 shared nodes + 20 unique leaf nodes = 120
        assert manager.node_count("llama3") == 120

    def test_memory_cap_triggers_eviction(self):
        """With a tiny cap, eviction should fire and keep node count bounded."""
        manager = KVPrefixManager(min_prefix_tokens=1, max_nodes_per_model=10)
        sequences = [list(range(i, i + 8)) for i in range(0, 80, 8)]

        async def run():
            for seq in sequences:
                await manager.record("llama3", seq)
            # Wait for all inserts and eviction tasks to complete
            await manager.wait_for_pending_inserts()
            # Small additional sleep for eviction tasks
            await asyncio.sleep(0.05)

        asyncio.run(run())
        count = manager.node_count("llama3")
        # Should have been evicted at some point — not all 80 nodes remain
        # (10 sequences × 8 nodes = 80 without eviction)
        assert count <= manager.max_nodes_per_model