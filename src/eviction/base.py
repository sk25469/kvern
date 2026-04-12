"""
Base eviction policy interface for KVern cache management.

This module defines the abstract base class for all eviction policies.
"""

from abc import ABC, abstractmethod
from typing import List
import time

from ..trie.node import TrieNode


class EvictionPolicy(ABC):
    """
    Abstract base class for trie node eviction policies.
    
    All eviction policies must implement the rank() method to provide
    an ordered list of nodes from most to least evictable.
    """
    
    def __init__(self):
        """Initialize the eviction policy."""
        pass
    
    @abstractmethod
    def rank(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Rank nodes from most to least evictable.
        
        Args:
            nodes: List of TrieNode objects to rank
            
        Returns:
            List of TrieNode objects ordered from most to least evictable
        """
        pass
    
    def select_eviction_candidates(
        self, 
        nodes: List[TrieNode], 
        target_eviction_count: int
    ) -> List[TrieNode]:
        """
        Select nodes for eviction up to the target count.
        
        Args:
            nodes: List of TrieNode objects to consider
            target_eviction_count: Maximum number of nodes to evict
            
        Returns:
            List of TrieNode objects to evict (up to target_eviction_count)
        """
        ranked_nodes = self.rank(nodes)
        return ranked_nodes[:target_eviction_count]
    
    def get_current_time(self) -> float:
        """
        Get current timestamp for eviction calculations.
        
        Returns:
            Unix timestamp as float
        """
        return time.time()
    
    def calculate_recency_score(self, node: TrieNode) -> float:
        """
        Calculate recency score for a node.
        
        Args:
            node: TrieNode to score
            
        Returns:
            Recency score (higher = more recent)
        """
        current_time = self.get_current_time()
        time_since_access = current_time - node.last_seen
        
        # Avoid division by zero and negative scores
        return 1.0 / max(time_since_access, 0.001)
    
    def calculate_frequency_score(self, node: TrieNode) -> int:
        """
        Calculate frequency score for a node.
        
        Args:
            node: TrieNode to score
            
        Returns:
            Frequency score (access count)
        """
        return node.count
    
    def calculate_recompute_cost(self, node: TrieNode, cost_per_token: float = 1.0) -> float:
        """
        Calculate the cost of recomputing this prefix.
        
        Args:
            node: TrieNode to evaluate
            cost_per_token: Relative cost per token depth
            
        Returns:
            Recompute cost (higher = more expensive to evict)
        """
        return node.token_depth * cost_per_token
    
    def filter_evictable_nodes(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Filter nodes to only include those that are safe to evict.
        
        Basic safety checks:
        - Node is not the root (token_id != -1)
        - Node has been accessed (count > 0)
        
        Subclasses can override to add additional safety checks.
        
        Args:
            nodes: List of TrieNode objects to filter
            
        Returns:
            Filtered list of evictable nodes
        """
        evictable = []
        
        for node in nodes:
            # Skip root node
            if node.token_id == -1:
                continue
                
            # Skip unaccessed nodes (shouldn't happen, but safety check)
            if node.count <= 0:
                continue
                
            evictable.append(node)
        
        return evictable
    
    def get_policy_name(self) -> str:
        """
        Get human-readable name of this eviction policy.
        
        Returns:
            Policy name string
        """
        return self.__class__.__name__


class StatefulEvictionPolicy(EvictionPolicy):
    """
    Base class for eviction policies that maintain internal state.
    
    Some policies may need to track historical information or maintain
    running averages. This class provides a foundation for such policies.
    """
    
    def __init__(self):
        """Initialize stateful policy."""
        super().__init__()
        self.last_eviction_time = 0.0
        self.total_evictions = 0
    
    def on_eviction(self, evicted_nodes: List[TrieNode]) -> None:
        """
        Callback when nodes are evicted.
        
        Subclasses can override to update internal state.
        
        Args:
            evicted_nodes: List of nodes that were evicted
        """
        self.last_eviction_time = self.get_current_time()
        self.total_evictions += len(evicted_nodes)
    
    def get_eviction_stats(self) -> dict:
        """
        Get statistics about eviction behavior.
        
        Returns:
            Dictionary with eviction statistics
        """
        return {
            "total_evictions": self.total_evictions,
            "last_eviction_time": self.last_eviction_time,
            "policy_name": self.get_policy_name()
        }