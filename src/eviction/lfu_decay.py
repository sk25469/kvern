"""
LFU with decay eviction policy for KVern.

Evicts nodes with low frequency, but applies time decay so old popular
nodes become evictable over time. Balances frequency and recency.
"""

import time
import math
from typing import List
from .base import StatefulEvictionPolicy
from ..trie.node import TrieNode


class LFUDecayEvictionPolicy(StatefulEvictionPolicy):
    """
    Least Frequently Used with time decay eviction policy.
    
    Similar to LFU but applies exponential decay to frequency counts over time.
    This prevents old popular prefixes from staying in cache indefinitely
    if they're no longer being accessed.
    
    Score formula: effective_frequency = count / (1 + decay_rate * age)
    Lower score = more evictable.
    """
    
    def __init__(self, decay_rate: float = 0.01, min_age_hours: float = 1.0):
        """
        Initialize LFU with decay policy.
        
        Args:
            decay_rate: Rate of frequency decay over time (higher = faster decay)
            min_age_hours: Minimum age before decay starts (protects new entries)
        """
        super().__init__()
        self.decay_rate = decay_rate
        self.min_age_seconds = min_age_hours * 3600
    
    def calculate_effective_frequency(self, node: TrieNode) -> float:
        """
        Calculate effective frequency with time decay applied.
        
        Args:
            node: TrieNode to calculate frequency for
            
        Returns:
            Effective frequency (higher = less evictable)
        """
        current_time = self.get_current_time()
        age_seconds = current_time - node.first_seen
        
        # Don't apply decay to very new entries
        if age_seconds < self.min_age_seconds:
            return float(node.count)
        
        # Apply exponential decay
        decay_factor = 1.0 + (self.decay_rate * age_seconds / 3600)  # Hourly decay
        effective_frequency = node.count / decay_factor
        
        return max(effective_frequency, 0.001)  # Avoid zero division issues
    
    def rank(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Rank nodes by effective frequency (lowest first).
        
        Args:
            nodes: List of TrieNode objects to rank
            
        Returns:
            List of TrieNode objects ordered from lowest to highest effective frequency
        """
        evictable_nodes = self.filter_evictable_nodes(nodes)
        
        # Calculate effective frequency for each node
        node_scores = []
        for node in evictable_nodes:
            effective_freq = self.calculate_effective_frequency(node)
            node_scores.append((effective_freq, node))
        
        # Sort by effective frequency (ascending - lowest first = most evictable)
        node_scores.sort(key=lambda x: x[0])
        
        return [node for _, node in node_scores]
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return f"LFU_Decay(rate={self.decay_rate})"
    
    def get_node_debug_info(self, node: TrieNode) -> dict:
        """
        Get debug information for a node under this policy.
        
        Args:
            node: TrieNode to analyze
            
        Returns:
            Dictionary with debug information
        """
        current_time = self.get_current_time()
        age_hours = (current_time - node.first_seen) / 3600
        time_since_access_hours = (current_time - node.last_seen) / 3600
        effective_freq = self.calculate_effective_frequency(node)
        
        return {
            "raw_count": node.count,
            "effective_frequency": effective_freq,
            "age_hours": age_hours,
            "time_since_access_hours": time_since_access_hours,
            "decay_applied": age_hours > (self.min_age_seconds / 3600)
        }


class AdaptiveLFUDecayPolicy(LFUDecayEvictionPolicy):
    """
    Adaptive LFU decay policy that adjusts decay rate based on cache pressure.
    
    When cache pressure is high (frequent evictions), increases decay rate
    to make more nodes evictable. When pressure is low, reduces decay rate
    to retain more cache entries.
    """
    
    def __init__(
        self, 
        base_decay_rate: float = 0.01,
        min_decay_rate: float = 0.005,
        max_decay_rate: float = 0.05,
        adaptation_window: int = 100
    ):
        """
        Initialize adaptive LFU decay policy.
        
        Args:
            base_decay_rate: Starting decay rate
            min_decay_rate: Minimum decay rate (low pressure)
            max_decay_rate: Maximum decay rate (high pressure)
            adaptation_window: Number of eviction events to consider for adaptation
        """
        super().__init__(decay_rate=base_decay_rate)
        self.base_decay_rate = base_decay_rate
        self.min_decay_rate = min_decay_rate
        self.max_decay_rate = max_decay_rate
        self.adaptation_window = adaptation_window
        
        # Track eviction frequency for adaptation
        self.recent_eviction_times = []
    
    def on_eviction(self, evicted_nodes: List[TrieNode]) -> None:
        """
        Update state after eviction event.
        
        Args:
            evicted_nodes: List of nodes that were evicted
        """
        super().on_eviction(evicted_nodes)
        
        # Record eviction time
        current_time = self.get_current_time()
        self.recent_eviction_times.append(current_time)
        
        # Keep only recent evictions
        cutoff_time = current_time - 3600  # Last hour
        self.recent_eviction_times = [
            t for t in self.recent_eviction_times if t > cutoff_time
        ]
        
        # Adapt decay rate based on eviction frequency
        self._adapt_decay_rate()
    
    def _adapt_decay_rate(self) -> None:
        """Adapt decay rate based on recent eviction frequency."""
        if len(self.recent_eviction_times) < 2:
            return
        
        # Calculate evictions per hour
        time_span = self.recent_eviction_times[-1] - self.recent_eviction_times[0]
        if time_span > 0:
            evictions_per_hour = len(self.recent_eviction_times) / (time_span / 3600)
        else:
            evictions_per_hour = 0
        
        # Adapt decay rate based on eviction frequency
        # High frequency = high cache pressure = increase decay rate
        if evictions_per_hour > 10:  # High pressure
            self.decay_rate = min(self.max_decay_rate, self.decay_rate * 1.1)
        elif evictions_per_hour < 2:  # Low pressure  
            self.decay_rate = max(self.min_decay_rate, self.decay_rate * 0.95)
        
    def get_policy_name(self) -> str:
        """Get policy name."""
        return f"AdaptiveLFU_Decay(current_rate={self.decay_rate:.4f})"
    
    def get_eviction_stats(self) -> dict:
        """Get enhanced eviction statistics."""
        base_stats = super().get_eviction_stats()
        
        # Calculate recent eviction frequency
        if len(self.recent_eviction_times) >= 2:
            time_span = self.recent_eviction_times[-1] - self.recent_eviction_times[0]
            evictions_per_hour = len(self.recent_eviction_times) / max(time_span / 3600, 0.001)
        else:
            evictions_per_hour = 0
        
        base_stats.update({
            "current_decay_rate": self.decay_rate,
            "base_decay_rate": self.base_decay_rate,
            "recent_evictions_per_hour": evictions_per_hour,
            "recent_eviction_count": len(self.recent_eviction_times)
        })
        
        return base_stats