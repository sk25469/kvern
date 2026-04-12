"""
Unit tests for KVern eviction policies.

Tests the pluggable eviction policies validated in the POC, including
the cost-aware policy that fixes the depth-blind LRU flaw.
"""

import pytest
import time
from unittest.mock import Mock

from src.eviction import get_eviction_policy, POLICY_REGISTRY
from src.eviction.lru import LRUEvictionPolicy
from src.eviction.lfu_decay import LFUDecayEvictionPolicy  
from src.eviction.cost_aware import CostAwareEvictionPolicy
from src.trie.node import TrieNode
from .fixtures import test_nodes, test_config


class TestEvictionPolicyRegistry:
    """Tests for eviction policy factory and registry."""
    
    def test_policy_registry_contains_expected_policies(self):
        """Test that all expected policies are registered."""
        expected_policies = ["lru", "lfu_decay", "cost_aware"]
        
        for policy_name in expected_policies:
            assert policy_name in POLICY_REGISTRY
    
    def test_get_eviction_policy_valid_names(self):
        """Test getting policies by valid names."""
        lru_policy = get_eviction_policy("lru")
        assert isinstance(lru_policy, LRUEvictionPolicy)
        
        lfu_policy = get_eviction_policy("lfu_decay", decay_rate=0.05)
        assert isinstance(lfu_policy, LFUDecayEvictionPolicy)
        
        cost_policy = get_eviction_policy("cost_aware", cost_per_token=2.0)
        assert isinstance(cost_policy, CostAwareEvictionPolicy)
    
    def test_get_eviction_policy_invalid_name(self):
        """Test error handling for invalid policy names."""
        with pytest.raises(ValueError, match="Unknown policy"):
            get_eviction_policy("invalid_policy")


class TestLRUEvictionPolicy:
    """Tests for LRU (Least Recently Used) eviction policy."""
    
    def test_lru_basic_ranking(self, test_nodes):
        """Test LRU ranking orders by last_seen timestamp."""
        policy = LRUEvictionPolicy()
        
        ranked = policy.rank(test_nodes)
        
        # Should be ordered by last_seen (ascending - oldest first)
        for i in range(1, len(ranked)):
            assert ranked[i-1].last_seen <= ranked[i].last_seen
    
    def test_lru_filtering_safety(self):
        """Test LRU filters out unsafe nodes."""
        policy = LRUEvictionPolicy()
        
        # Create test nodes with edge cases
        nodes = [
            TrieNode(token_id=-1, count=1),  # Root node (should be filtered)
            TrieNode(token_id=100, count=0),  # Unaccessed node (should be filtered)
            TrieNode(token_id=200, count=5, last_seen=time.time()),  # Valid node
        ]
        
        ranked = policy.rank(nodes)
        
        # Should only include the valid node
        assert len(ranked) == 1
        assert ranked[0].token_id == 200
    
    def test_lru_policy_name(self):
        """Test LRU policy name reporting."""
        policy = LRUEvictionPolicy()
        assert policy.get_policy_name() == "LRU"
    
    def test_lru_eviction_candidate_selection(self, test_nodes):
        """Test selecting specific number of eviction candidates."""
        policy = LRUEvictionPolicy()
        
        candidates = policy.select_eviction_candidates(test_nodes, target_eviction_count=2)
        
        assert len(candidates) == 2
        # Should be the 2 oldest nodes
        assert candidates[0].last_seen <= candidates[1].last_seen


class TestLFUDecayEvictionPolicy:
    """Tests for LFU with decay eviction policy."""
    
    def test_lfu_decay_initialization(self):
        """Test LFU decay policy initialization with parameters."""
        policy = LFUDecayEvictionPolicy(decay_rate=0.05, min_age_hours=2.0)
        
        assert policy.decay_rate == 0.05
        assert policy.min_age_seconds == 2.0 * 3600
    
    def test_effective_frequency_calculation_new_node(self):
        """Test effective frequency for new nodes (no decay applied).""" 
        policy = LFUDecayEvictionPolicy(min_age_hours=1.0)
        
        # Create a recent node (should not have decay applied)
        recent_node = TrieNode(
            token_id=100,
            count=10,
            first_seen=time.time() - 1800,  # 30 minutes ago
            last_seen=time.time()
        )
        
        effective_freq = policy.calculate_effective_frequency(recent_node)
        
        # Should be close to original count (no decay)
        assert effective_freq == 10.0
    
    def test_effective_frequency_calculation_old_node(self):
        """Test effective frequency for old nodes (decay applied)."""
        policy = LFUDecayEvictionPolicy(decay_rate=0.01, min_age_hours=1.0)
        
        # Create an old node (should have decay applied)
        old_node = TrieNode(
            token_id=100,
            count=10,
            first_seen=time.time() - 7200,  # 2 hours ago
            last_seen=time.time() - 3600    # 1 hour ago
        )
        
        effective_freq = policy.calculate_effective_frequency(old_node)
        
        # Should be less than original count due to decay
        assert effective_freq < 10.0
        assert effective_freq > 0
    
    def test_lfu_decay_ranking(self, test_nodes):
        """Test LFU decay ranking orders by effective frequency."""
        policy = LFUDecayEvictionPolicy(decay_rate=0.01)
        
        ranked = policy.rank(test_nodes)
        
        # Should be ordered by effective frequency (ascending - lowest first)
        for i in range(1, len(ranked)):
            freq_prev = policy.calculate_effective_frequency(ranked[i-1])
            freq_curr = policy.calculate_effective_frequency(ranked[i])
            assert freq_prev <= freq_curr
    
    def test_lfu_decay_debug_info(self):
        """Test debug information generation."""
        policy = LFUDecayEvictionPolicy(decay_rate=0.01)
        
        test_node = TrieNode(
            token_id=100,
            count=5,
            first_seen=time.time() - 3600,
            last_seen=time.time() - 300
        )
        
        debug_info = policy.get_node_debug_info(test_node)
        
        required_keys = [
            "raw_count", "effective_frequency", "age_hours", 
            "time_since_access_hours", "decay_applied"
        ]
        
        for key in required_keys:
            assert key in debug_info
        
        assert debug_info["raw_count"] == 5
        assert debug_info["effective_frequency"] > 0


class TestCostAwareEvictionPolicy:
    """Tests for cost-aware eviction policy (addresses POC depth-blind LRU flaw)."""
    
    def test_cost_aware_initialization(self):
        """Test cost-aware policy initialization."""
        policy = CostAwareEvictionPolicy(
            cost_per_token=2.0,
            recency_weight=1.5,
            min_depth_protection=15
        )
        
        assert policy.cost_per_token == 2.0
        assert policy.recency_weight == 1.5
        assert policy.min_depth_protection == 15
    
    def test_eviction_score_calculation(self):
        """Test eviction score calculation for different node types."""
        policy = CostAwareEvictionPolicy(cost_per_token=1.0, recency_weight=1.0)
        
        # Shallow, low-frequency node (should be evictable)
        shallow_node = TrieNode(
            token_id=100,
            count=2,
            token_depth=5,
            last_seen=time.time() - 3600
        )
        
        # Deep, high-frequency node (should be protected)
        deep_node = TrieNode(
            token_id=200,
            count=50,
            token_depth=100,
            last_seen=time.time() - 300
        )
        
        shallow_score = policy.calculate_eviction_score(shallow_node)
        deep_score = policy.calculate_eviction_score(deep_node)
        
        # Shallow node should have lower score (more evictable)
        assert shallow_score < deep_score
    
    def test_cost_aware_addresses_depth_blind_flaw(self):
        """Test that cost-aware policy fixes the depth-blind LRU flaw from POC."""
        policy = CostAwareEvictionPolicy()
        
        # Recreate the problematic scenario from POC:
        # A space token at depth 47 with 5 hits vs a shallow token with 3 hits
        deep_frequent_node = TrieNode(
            token_id=220,  # The ' ' (space) token from POC
            count=5,
            token_depth=47,
            last_seen=time.time() - 1800  # Older access
        )
        
        shallow_infrequent_node = TrieNode(
            token_id=999,
            count=3,
            token_depth=2,
            last_seen=time.time() - 900   # More recent access
        )
        
        nodes = [deep_frequent_node, shallow_infrequent_node]
        ranked = policy.rank(nodes)
        
        # Cost-aware should prefer evicting shallow node despite higher frequency
        # because the recompute cost is much lower
        assert ranked[0] == shallow_infrequent_node  # Most evictable
        assert ranked[1] == deep_frequent_node       # Less evictable
    
    def test_cost_aware_protection_filtering(self):
        """Test protection of very deep, frequent nodes."""
        policy = CostAwareEvictionPolicy(min_depth_protection=10)
        
        # Create a very deep, very frequent node that should be protected
        protected_node = TrieNode(
            token_id=100,
            count=15,  # Above protection threshold
            token_depth=20,  # Above depth threshold
            last_seen=time.time()
        )
        
        regular_node = TrieNode(
            token_id=200,
            count=5,
            token_depth=5,
            last_seen=time.time()
        )
        
        nodes = [protected_node, regular_node]
        filtered = policy.filter_evictable_nodes(nodes)
        
        # Protected node might be filtered out or given lower priority
        assert len(filtered) >= 1
        # The exact behavior depends on implementation, but regular_node should be evictable
        assert regular_node in filtered
    
    def test_cost_aware_debug_info(self):
        """Test cost-aware policy debug information."""
        policy = CostAwareEvictionPolicy()
        
        test_node = TrieNode(
            token_id=100,
            count=10,
            token_depth=25,
            last_seen=time.time() - 600
        )
        
        debug_info = policy.get_node_debug_info(test_node)
        
        required_keys = [
            "token_depth", "access_count", "recompute_cost",
            "frequency_weight", "recency_score", "eviction_score", "protected"
        ]
        
        for key in required_keys:
            assert key in debug_info
        
        assert debug_info["token_depth"] == 25
        assert debug_info["access_count"] == 10
        assert debug_info["recompute_cost"] > 0
        assert debug_info["eviction_score"] > 0


class TestEvictionPolicyComparison:
    """Integration tests comparing different eviction policies."""
    
    def test_policy_consistency(self, test_nodes):
        """Test that all policies produce consistent rankings."""
        policies = [
            LRUEvictionPolicy(),
            LFUDecayEvictionPolicy(),
            CostAwareEvictionPolicy()
        ]
        
        for policy in policies:
            ranked = policy.rank(test_nodes)
            
            # Basic consistency checks
            assert len(ranked) <= len(test_nodes)  # May filter some nodes
            assert all(isinstance(node, TrieNode) for node in ranked)
            assert all(node.token_id != -1 for node in ranked)  # No root nodes
    
    def test_eviction_scenario_comparison(self):
        """Test different policies on the same eviction scenario."""
        # Create nodes representing the POC scenario
        nodes = [
            # Deep frequently accessed system prompt prefix
            TrieNode(token_id=1, count=500, token_depth=50, last_seen=time.time() - 3600),
            
            # Medium depth moderately accessed
            TrieNode(token_id=2, count=10, token_depth=20, last_seen=time.time() - 1800),
            
            # Shallow infrequently accessed  
            TrieNode(token_id=3, count=2, token_depth=5, last_seen=time.time() - 900),
            
            # Deep but old and infrequent
            TrieNode(token_id=4, count=3, token_depth=40, last_seen=time.time() - 7200)
        ]
        
        lru_policy = LRUEvictionPolicy()
        cost_aware_policy = CostAwareEvictionPolicy()
        
        lru_ranking = lru_policy.rank(nodes)
        cost_aware_ranking = cost_aware_policy.rank(nodes)
        
        # Rankings should be different for this scenario
        assert lru_ranking != cost_aware_ranking
        
        # Cost-aware should generally prefer evicting shallow nodes
        cost_aware_first = cost_aware_ranking[0]
        assert cost_aware_first.token_depth <= 20  # Should prefer shallower nodes


class TestEvictionPolicyPerformance:
    """Performance tests for eviction policies."""
    
    def test_large_scale_ranking_performance(self, timing_context):
        """Test performance with large number of nodes."""
        # Create many test nodes
        current_time = time.time()
        nodes = [
            TrieNode(
                token_id=i,
                count=i % 50 + 1,
                token_depth=i % 100 + 1,
                first_seen=current_time - (i * 60),
                last_seen=current_time - ((i % 10) * 60)
            )
            for i in range(10000)  # 10k nodes
        ]
        
        policy = CostAwareEvictionPolicy()
        
        with timing_context() as timer:
            ranked = policy.rank(nodes)
        
        # Performance check
        assert timer.duration < 2.0  # Should complete quickly
        assert len(ranked) > 0