"""
Cost-aware eviction policy for KVern.

Considers both recompute cost (token depth) and access frequency.
Prioritizes evicting nodes where recompute cost is low relative to reuse frequency.
This addresses the depth-blind LRU flaw discovered in the POC.
"""

from typing import List
from .base import EvictionPolicy
from ..trie.node import TrieNode


class CostAwareEvictionPolicy(EvictionPolicy):
    """
    Cost-aware eviction policy that balances recompute cost vs access frequency.
    
    This policy addresses the critical flaw discovered in the POC where naive LRU
    evicted a high-traffic node at depth 47, requiring recomputation of 47 tokens.
    
    Eviction score = recompute_cost / (count * recency_weight)
    
    Lower score = more evictable:
    - Shallow nodes (low recompute cost) are preferred for eviction
    - Frequently accessed nodes are protected
    - Recently accessed nodes get additional protection
    """
    
    def __init__(
        self, 
        cost_per_token: float = 1.0,
        recency_weight: float = 1.0,
        min_depth_protection: int = 10
    ):
        """
        Initialize cost-aware eviction policy.
        
        Args:
            cost_per_token: Relative cost per token of depth (tunable)
            recency_weight: Weight for recency in the eviction score
            min_depth_protection: Minimum depth threshold for additional protection
        """
        super().__init__()
        self.cost_per_token = cost_per_token
        self.recency_weight = recency_weight
        self.min_depth_protection = min_depth_protection
    
    def calculate_eviction_score(self, node: TrieNode) -> float:
        """
        Calculate eviction score for a node.
        
        Lower score = more evictable.
        
        Args:
            node: TrieNode to score
            
        Returns:
            Eviction score (lower = more evictable)
        """
        # Recompute cost: deeper nodes are more expensive to evict
        recompute_cost = self.calculate_recompute_cost(node, self.cost_per_token)
        
        # Frequency weight: frequently accessed nodes are less evictable
        frequency_weight = max(node.count, 1)  # Avoid division by zero
        
        # Recency weight: recently accessed nodes are less evictable
        recency_score = self.calculate_recency_score(node)
        combined_weight = frequency_weight * (1.0 + self.recency_weight * recency_score)
        
        # Lower score = more evictable
        eviction_score = recompute_cost / combined_weight
        
        return eviction_score
    
    def rank(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Rank nodes by eviction score (lowest first).
        
        Args:
            nodes: List of TrieNode objects to rank
            
        Returns:
            List of TrieNode objects ordered from most to least evictable
        """
        evictable_nodes = self.filter_evictable_nodes(nodes)
        
        # Calculate eviction score for each node
        node_scores = []
        for node in evictable_nodes:
            score = self.calculate_eviction_score(node)
            node_scores.append((score, node))
        
        # Sort by eviction score (ascending - lowest first = most evictable)
        node_scores.sort(key=lambda x: x[0])
        
        return [node for _, node in node_scores]
    
    def filter_evictable_nodes(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """
        Apply cost-aware safety filtering.
        
        Args:
            nodes: List of TrieNode objects to filter
            
        Returns:
            Filtered list of evictable nodes
        """
        # Apply base filtering
        base_evictable = super().filter_evictable_nodes(nodes)
        
        # Additional protection for very deep, frequently accessed nodes
        protected_nodes = []
        evictable_nodes = []
        
        for node in base_evictable:
            # Protect very deep + very frequent nodes
            if (node.token_depth >= self.min_depth_protection and 
                node.count >= 10):  # Configurable threshold
                protected_nodes.append(node)
            else:
                evictable_nodes.append(node)
        
        # If we need to evict and only have protected nodes, allow some eviction
        if not evictable_nodes and protected_nodes:
            # Sort protected nodes by eviction score and allow eviction of highest scores
            protected_scores = [
                (self.calculate_eviction_score(node), node) 
                for node in protected_nodes
            ]
            protected_scores.sort(key=lambda x: x[0], reverse=True)
            
            # Allow eviction of up to 25% of protected nodes with highest scores
            max_protected_evictable = max(1, len(protected_nodes) // 4)
            evictable_nodes = [
                node for _, node in protected_scores[:max_protected_evictable]
            ]
        
        return evictable_nodes
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return f"CostAware(token_cost={self.cost_per_token},recency={self.recency_weight})"
    
    def get_node_debug_info(self, node: TrieNode) -> dict:
        """
        Get debug information for a node under this policy.
        
        Args:
            node: TrieNode to analyze
            
        Returns:
            Dictionary with debug information
        """
        recompute_cost = self.calculate_recompute_cost(node, self.cost_per_token)
        frequency_weight = max(node.count, 1)
        recency_score = self.calculate_recency_score(node)
        eviction_score = self.calculate_eviction_score(node)
        
        return {
            "token_depth": node.token_depth,
            "access_count": node.count,
            "recompute_cost": recompute_cost,
            "frequency_weight": frequency_weight,
            "recency_score": recency_score,
            "eviction_score": eviction_score,
            "protected": (node.token_depth >= self.min_depth_protection and 
                         node.count >= 10)
        }


class AggressiveCostAwarePolicy(CostAwareEvictionPolicy):
    """
    Aggressive variant that more heavily penalizes depth.
    
    Useful when compute cost is very high relative to memory cost.
    """
    
    def __init__(self, **kwargs):
        """Initialize with more aggressive cost weighting."""
        kwargs.setdefault('cost_per_token', 2.0)  # Higher cost penalty
        kwargs.setdefault('min_depth_protection', 20)  # Higher protection threshold
        super().__init__(**kwargs)
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return f"AggressiveCostAware(token_cost={self.cost_per_token})"


class ConservativeCostAwarePolicy(CostAwareEvictionPolicy):
    """
    Conservative variant that protects deep nodes more strongly.
    
    Useful when memory is plentiful but compute cost is moderate.
    """
    
    def __init__(self, **kwargs):
        """Initialize with conservative settings."""
        kwargs.setdefault('cost_per_token', 0.5)   # Lower cost penalty
        kwargs.setdefault('recency_weight', 2.0)   # Higher recency protection
        kwargs.setdefault('min_depth_protection', 5)  # Lower protection threshold
        super().__init__(**kwargs)
    
    def filter_evictable_nodes(self, nodes: List[TrieNode]) -> List[TrieNode]:
        """More conservative filtering."""
        base_evictable = super().filter_evictable_nodes(nodes)
        
        # Even more protection for deep nodes
        conservative_evictable = []
        for node in base_evictable:
            # Only evict shallow nodes or very old deep nodes
            if (node.token_depth < self.min_depth_protection or 
                (node.token_depth >= self.min_depth_protection and 
                 self.get_current_time() - node.last_seen > 3600)):  # 1 hour old
                conservative_evictable.append(node)
        
        return conservative_evictable if conservative_evictable else base_evictable[:1]
    
    def get_policy_name(self) -> str:
        """Get policy name."""
        return f"ConservativeCostAware(token_cost={self.cost_per_token})"