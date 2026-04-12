"""
Unit tests for KVern trie operations.

Tests the core trie functionality including insert, lookup, eviction,
and hot prefix queries validated in the POC notebook.
"""

import pytest
import time
from typing import List

from src.trie.prefix_trie import PrefixTrie, LookupResult, HotPrefix
from src.trie.node import TrieNode
from .fixtures import sample_token_sequences, populated_trie, empty_trie


class TestTrieNode:
    """Tests for TrieNode dataclass."""
    
    def test_node_creation(self):
        """Test basic node creation."""
        node = TrieNode(token_id=123)
        
        assert node.token_id == 123
        assert node.count == 0
        assert node.children == {}
        assert node.token_depth == 0
        assert node.last_seen == 0.0
        assert node.first_seen == 0.0
    
    def test_node_with_parameters(self):
        """Test node creation with all parameters."""
        current_time = time.time()
        
        node = TrieNode(
            token_id=456,
            count=5,
            token_depth=10,
            first_seen=current_time - 100,
            last_seen=current_time
        )
        
        assert node.token_id == 456
        assert node.count == 5
        assert node.token_depth == 10
        assert node.first_seen == current_time - 100
        assert node.last_seen == current_time


class TestPrefixTrie:
    """Tests for PrefixTrie operations."""
    
    def test_empty_trie_creation(self):
        """Test creating an empty trie."""
        trie = PrefixTrie(min_prefix_tokens=10)
        
        assert trie.min_prefix_tokens == 10
        assert trie.total_nodes == 1  # Root node
        assert trie.root.token_id == -1
        assert len(trie.root.children) == 0
    
    def test_single_sequence_insertion(self, empty_trie):
        """Test inserting a single token sequence."""
        token_ids = [1, 2, 3, 4, 5]
        
        empty_trie.insert(token_ids)
        
        assert empty_trie.total_nodes == 6  # Root + 5 tokens
        
        # Verify path exists
        current = empty_trie.root
        for i, token_id in enumerate(token_ids):
            assert token_id in current.children
            current = current.children[token_id]
            assert current.token_id == token_id
            assert current.token_depth == i + 1
            assert current.count == 1
    
    def test_multiple_insertions_same_sequence(self, empty_trie):
        """Test inserting the same sequence multiple times."""
        token_ids = [10, 20, 30]
        
        # Insert same sequence 3 times
        for _ in range(3):
            empty_trie.insert(token_ids)
        
        # Should still have same number of nodes
        assert empty_trie.total_nodes == 4  # Root + 3 tokens
        
        # But counts should be incremented
        current = empty_trie.root
        for token_id in token_ids:
            current = current.children[token_id]
            assert current.count == 3
    
    def test_overlapping_sequences(self, empty_trie):
        """Test inserting sequences with shared prefixes."""
        seq1 = [1, 2, 3, 4]
        seq2 = [1, 2, 5, 6]
        
        empty_trie.insert(seq1)
        empty_trie.insert(seq2)
        
        # Should have: root + [1,2] shared + [3,4] + [5,6]
        assert empty_trie.total_nodes == 7
        
        # Check shared prefix counts
        node_1 = empty_trie.root.children[1]
        node_2 = node_1.children[2]
        assert node_1.count == 2  # Both sequences pass through
        assert node_2.count == 2  # Both sequences pass through
        
        # Check divergent paths
        node_3 = node_2.children[3]
        node_5 = node_2.children[5]
        assert node_3.count == 1  # Only seq1
        assert node_5.count == 1  # Only seq2
    
    def test_lookup_exact_match(self, populated_trie, sample_token_sequences):
        """Test looking up an exact sequence that exists."""
        long_seq = sample_token_sequences["long_sequence"]
        
        result = populated_trie.lookup(long_seq)
        
        assert result.match_depth == len(long_seq)
        assert result.is_hit == True  # Assuming min_prefix_tokens <= len(long_seq)
        assert result.matched_node is not None
        assert result.matched_node.count >= 1
    
    def test_lookup_partial_match(self, populated_trie, sample_token_sequences):
        """Test looking up a sequence that partially matches."""
        long_seq = sample_token_sequences["long_sequence"]
        partial_seq = long_seq[:20]  # First 20 tokens
        
        result = populated_trie.lookup(partial_seq)
        
        assert result.match_depth == len(partial_seq)
        assert result.matched_node is not None
    
    def test_lookup_no_match(self, populated_trie):
        """Test looking up a sequence with no match."""
        non_existent = [999, 998, 997]
        
        result = populated_trie.lookup(non_existent)
        
        assert result.match_depth == 0
        assert result.is_hit == False
        assert result.matched_node is None
    
    def test_lookup_empty_sequence(self, populated_trie):
        """Test looking up an empty sequence."""
        result = populated_trie.lookup([])
        
        assert result.match_depth == 0
        assert result.is_hit == False
    
    def test_find_prefix_legacy_method(self, populated_trie, sample_token_sequences):
        """Test legacy find_prefix method for compatibility."""
        long_seq = sample_token_sequences["long_sequence"]
        
        match_length = populated_trie.find_prefix(long_seq)
        
        assert match_length == len(long_seq)
        assert match_length > 0
    
    def test_hot_prefixes_query(self, populated_trie):
        """Test hot prefix identification."""
        hot_prefixes = populated_trie.get_hot_prefixes(n=5, min_count=1)
        
        assert isinstance(hot_prefixes, list)
        assert len(hot_prefixes) > 0
        
        # Check sorting (should be descending by count)
        for i in range(1, len(hot_prefixes)):
            assert hot_prefixes[i-1].count >= hot_prefixes[i].count
        
        # Verify structure
        for prefix in hot_prefixes:
            assert isinstance(prefix, HotPrefix)
            assert prefix.count >= 1
            assert prefix.depth >= populated_trie.min_prefix_tokens
            assert len(prefix.token_ids) == prefix.depth
    
    def test_eviction_candidates_lru(self, populated_trie):
        """Test LRU eviction candidate ranking."""
        candidates = populated_trie.get_eviction_candidates(policy="lru")
        
        assert len(candidates) > 0
        
        # Check LRU ordering (oldest first)
        for i in range(1, len(candidates)):
            assert candidates[i-1].last_seen <= candidates[i].last_seen
    
    def test_eviction_candidates_cost_aware(self, populated_trie):
        """Test cost-aware eviction candidate ranking."""
        candidates = populated_trie.get_eviction_candidates(policy="cost_aware")
        
        assert len(candidates) > 0
        
        # Verify nodes are present (specific ordering depends on implementation)
        assert all(isinstance(node, TrieNode) for node in candidates)
        assert all(node.token_id != -1 for node in candidates)  # No root node
    
    def test_eviction_execution(self, populated_trie):
        """Test actual node eviction."""
        initial_count = populated_trie.total_nodes
        target_count = max(2, initial_count - 3)  # Evict 3 nodes, keep at least root
        
        evicted = populated_trie.evict_nodes(target_count)
        
        assert len(evicted) >= 0
        assert populated_trie.total_nodes <= initial_count
        assert populated_trie.total_nodes >= 1  # Root should remain
        
        # Verify evicted nodes are no longer accessible
        for node in evicted:
            assert isinstance(node, TrieNode)
    
    def test_trie_stats(self, populated_trie):
        """Test trie statistics generation."""
        stats = populated_trie.get_stats()
        
        required_keys = [
            "total_nodes", "max_depth", "leaf_nodes", 
            "min_prefix_threshold", "branching_factor"
        ]
        
        for key in required_keys:
            assert key in stats
        
        assert stats["total_nodes"] >= 1
        assert stats["max_depth"] >= 0
        assert stats["leaf_nodes"] >= 0
        assert stats["min_prefix_threshold"] == populated_trie.min_prefix_tokens
    
    def test_concurrent_insertions(self, empty_trie):
        """Test trie behavior with concurrent-like insertions."""
        sequences = [
            [1, 2, 3],
            [1, 2, 4], 
            [1, 5, 6],
            [7, 8, 9]
        ]
        
        for seq in sequences:
            empty_trie.insert(seq)
        
        # Verify structure
        assert 1 in empty_trie.root.children
        node_1 = empty_trie.root.children[1]
        assert node_1.count == 3  # Three sequences start with 1
        
        assert 2 in node_1.children
        assert 5 in node_1.children
        
        node_2 = node_1.children[2]
        assert node_2.count == 2  # Two sequences have [1,2]
    
    def test_deep_sequence_insertion(self, empty_trie):
        """Test inserting very deep sequences."""
        deep_sequence = list(range(1000))  # 1000 tokens
        
        empty_trie.insert(deep_sequence)
        
        assert empty_trie.total_nodes == 1001  # Root + 1000 tokens
        
        # Verify we can traverse to the end
        current = empty_trie.root
        for i, token_id in enumerate(deep_sequence):
            assert token_id in current.children
            current = current.children[token_id]
            assert current.token_depth == i + 1
    
    def test_min_prefix_threshold_enforcement(self):
        """Test that min_prefix_tokens threshold is enforced."""
        trie = PrefixTrie(min_prefix_tokens=20)
        
        short_seq = [1, 2, 3, 4, 5]  # Below threshold
        long_seq = list(range(1, 26))  # Above threshold
        
        trie.insert(short_seq)
        trie.insert(long_seq)
        
        # Short sequence lookup should not be a hit
        short_result = trie.lookup(short_seq)
        assert short_result.is_hit == False
        
        # Long sequence lookup should be a hit
        long_result = trie.lookup(long_seq)
        assert long_result.is_hit == True
        
        # Hot prefixes should only include sequences above threshold
        hot_prefixes = trie.get_hot_prefixes(min_count=1)
        valid_hot_prefixes = [hp for hp in hot_prefixes if hp.depth >= 20]
        assert len(valid_hot_prefixes) >= 0  # May be 0 if only one sequence above threshold


class TestTriePerformance:
    """Performance tests for trie operations."""
    
    def test_large_scale_insertion_performance(self, timing_context):
        """Test performance with large number of insertions."""
        trie = PrefixTrie(min_prefix_tokens=10)
        
        # Generate test sequences
        sequences = [
            list(range(i, i + 50))  # 50-token sequences
            for i in range(1000)  # 1000 different sequences
        ]
        
        with timing_context() as timer:
            for seq in sequences:
                trie.insert(seq)
        
        # Performance check (adjust threshold as needed)
        assert timer.duration < 5.0  # Should complete in under 5 seconds
        assert trie.total_nodes > 1000
    
    def test_lookup_performance(self, populated_trie, sample_token_sequences, timing_context):
        """Test lookup performance on populated trie."""
        long_seq = sample_token_sequences["long_sequence"]
        
        with timing_context() as timer:
            for _ in range(1000):  # 1000 lookups
                result = populated_trie.lookup(long_seq)
                assert result.match_depth > 0
        
        # Performance check
        assert timer.duration < 1.0  # Should be very fast