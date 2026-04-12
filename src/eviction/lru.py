"""
LRU (Least Recently Used) eviction policy for KVern.

Evicts nodes that haven't been accessed recently, regardless of frequency.
Simple baseline policy with predictable behavior.
"""

from typing import List
from .base import EvictionPolicy
from ..trie.node import TrieNode


class LRUEvictionPolicy(EvictionPolicy):
    """
    Least Recently Used eviction policy.
    
    Ranks nodes by last_seen timestamp, evicting the oldest accessed nodes first.
    This is a simple baseline policy that provides predictable behavior but may
    evict frequently accessed nodes that happened to be accessed long ago.
    """
    
    def rank(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Rank nodes by last access time (oldest first).
        
        Args:
            nodes: List of TrieNode objects to rank
            
        Returns:
            List of TrieNode objects ordered from oldest to newest access
        """
        # Filter for safety
        evictable_nodes = self.filter_evictable_nodes(nodes)
        
        # Sort by last_seen (ascending - oldest first = most evictable)
        sorted_nodes = sorted(evictable_nodes, key=lambda node: node.last_seen)
        
        return sorted_nodes
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return "LRU"


class StrictLRUEvictionPolicy(LRUEvictionPolicy):
    """
    Strict LRU policy that only considers recency.
    
    Unlike the base LRU policy, this variant doesn't consider any frequency
    information and purely ranks by temporal access patterns.
    """
    
    def rank(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Rank nodes strictly by last access time.
        
        Args:
            nodes: List of TrieNode objects to rank
            
        Returns:
            List of TrieNode objects ordered by last_seen (oldest first)
        """
        evictable_nodes = self.filter_evictable_nodes(nodes)
        
        # Strict temporal ordering
        return sorted(evictable_nodes, key=lambda node: (node.last_seen, node.token_id))
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return "StrictLRU"


class LRUWithMinimumFrequencyPolicy(LRUEvictionPolicy):
    """
    LRU policy with minimum frequency protection.
    
    Protects frequently accessed nodes from eviction even if they're old,
    only evicting nodes below a frequency threshold.
    """
    
    def __init__(self, min_frequency_threshold: int = 5):
        """
        Initialize LRU with frequency protection.
        
        Args:
            min_frequency_threshold: Minimum access count to protect from eviction
        """
        super().__init__()
        self.min_frequency_threshold = min_frequency_threshold
    
    def filter_evictable_nodes(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Filter nodes, excluding high-frequency nodes.
        
        Args:
            nodes: List of TrieNode objects to filter
            
        Returns:
            Filtered list excluding high-frequency nodes
        """
        # Apply base filtering first
        base_evictable = super().filter_evictable_nodes(nodes)
        
        # Additional filter: exclude high-frequency nodes
        low_frequency_nodes = [
            node for node in base_evictable
            if node.count < self.min_frequency_threshold
        ]
        
        return low_frequency_nodes
    
    def rank(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Rank low-frequency nodes by last access time.
        
        Args:
            nodes: List of TrieNode objects to rank
            
        Returns:
            List of low-frequency TrieNode objects ordered by access time
        """
        evictable_nodes = self.filter_evictable_nodes(nodes)
        
        # Sort by last_seen among low-frequency nodes
        return sorted(evictable_nodes, key=lambda node: node.last_seen)
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return f"LRU_MinFreq({self.min_frequency_threshold})"