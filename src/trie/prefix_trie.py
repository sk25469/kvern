"""
Prefix trie operations for token sequence caching.

This module implements the core trie operations: insert, lookup, and hot prefix queries.
Based on the validated POC from notebooks/KVern_POC.ipynb.
"""

import time
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass

from .node import TrieNode


@dataclass 
class LookupResult:
    """Result of a trie prefix lookup operation."""
    match_depth: int        # Number of tokens matched from the start
    is_hit: bool           # True if prefix depth >= min_threshold
    matched_node: Optional[TrieNode] = None  # Final matched node
    

@dataclass
class HotPrefix:
    """Information about a frequently accessed prefix."""
    token_ids: List[int]    # Token sequence for this prefix
    depth: int             # Prefix length in tokens
    count: int             # Number of times accessed
    last_seen: float       # Unix timestamp of last access
    first_seen: float      # Unix timestamp of first access
    

class PrefixTrie:
    """
    Token-level trie for tracking shared prefixes in LLM requests.
    
    Features:
    - Insert token sequences and track access counts
    - Lookup longest matching prefix for incoming sequences
    - Query for hot prefixes above minimum depth threshold
    - Eviction candidate ranking
    """
    
    def __init__(self, min_prefix_tokens: int = 32):
        """
        Initialize prefix trie.
        
        Args:
            min_prefix_tokens: Minimum prefix length to consider a "hit"
        """
        self.root = TrieNode(token_id=-1)  # Root is dummy node
        self.min_prefix_tokens = min_prefix_tokens
        self.total_nodes = 1  # Count the root
        
    def insert(self, token_ids: List[int]) -> None:
        """
        Insert a token sequence into the trie.
        
        Walks the trie from root, creating nodes as needed. Updates counts
        and timestamps for all nodes along the path.
        
        Args:
            token_ids: Sequence of token IDs to insert
        """
        if not token_ids:
            return
            
        current = self.root
        current_time = time.time()
        
        for depth, token_id in enumerate(token_ids):
            # Update timestamp for current node
            current.last_seen = current_time
            if current.first_seen == 0.0:
                current.first_seen = current_time
                
            # Navigate to child node
            if token_id not in current.children:
                # Create new child node
                child = TrieNode(
                    token_id=token_id,
                    token_depth=depth + 1,  # Depth from root (excluding root itself)
                    first_seen=current_time,
                    last_seen=current_time
                )
                current.children[token_id] = child
                self.total_nodes += 1
                
            current = current.children[token_id]
            current.count += 1
        
        # Update final node timestamp
        current.last_seen = current_time
        if current.first_seen == 0.0:
            current.first_seen = current_time
    
    def lookup(self, token_ids: List[int]) -> LookupResult:
        """
        Find the longest matching prefix for a token sequence.
        
        Args:
            token_ids: Sequence of token IDs to match
            
        Returns:
            LookupResult with match depth, hit status, and final node
        """
        if not token_ids:
            return LookupResult(match_depth=0, is_hit=False)
            
        current = self.root
        match_depth = 0
        
        for token_id in token_ids:
            if token_id in current.children:
                current = current.children[token_id]
                match_depth += 1
            else:
                break
        
        is_hit = match_depth >= self.min_prefix_tokens
        
        return LookupResult(
            match_depth=match_depth,
            is_hit=is_hit,
            matched_node=current if match_depth > 0 else None
        )
    
    def find_prefix(self, token_ids: List[int]) -> int:
        """
        Legacy method for compatibility with notebook POC.
        
        Args:
            token_ids: Sequence of token IDs to match
            
        Returns:
            Length of matching prefix
        """
        return self.lookup(token_ids).match_depth
    
    def get_hot_prefixes(self, n: int = 10, min_count: int = 2) -> List[HotPrefix]:
        """
        Get the top N most frequently accessed prefixes.
        
        Args:
            n: Number of hot prefixes to return
            min_count: Minimum access count to be considered "hot"
            
        Returns:
            List of HotPrefix objects ordered by access count (descending)
        """
        hot_prefixes = []
        
        def collect_prefixes(node: TrieNode, path: List[int]):
            """Recursively collect prefix information."""
            if (node.count >= min_count and 
                node.token_depth >= self.min_prefix_tokens and
                node.token_id != -1):  # Exclude root
                
                hot_prefixes.append(HotPrefix(
                    token_ids=path.copy(),
                    depth=node.token_depth,
                    count=node.count,
                    last_seen=node.last_seen,
                    first_seen=node.first_seen
                ))
            
            # Recurse to children
            for token_id, child in node.children.items():
                collect_prefixes(child, path + [token_id])
        
        # Start collection from root
        collect_prefixes(self.root, [])
        
        # Sort by count (descending) and return top N
        hot_prefixes.sort(key=lambda x: x.count, reverse=True)
        return hot_prefixes[:n]
    
    def get_eviction_candidates(self, policy: str = "lru") -> List[TrieNode]:
        """
        Get nodes ranked for eviction according to the specified policy.
        
        Args:
            policy: Eviction policy ("lru", "lfu", "cost_aware")
            
        Returns:
            List of TrieNode objects ordered from most to least evictable
        """
        all_nodes = []
        
        def collect_nodes(node: TrieNode):
            """Recursively collect all non-root nodes."""
            if node.token_id != -1:  # Exclude root
                all_nodes.append(node)
            
            for child in node.children.values():
                collect_nodes(child)
        
        collect_nodes(self.root)
        
        current_time = time.time()
        
        if policy == "lru":
            # Sort by last_seen (ascending - oldest first)
            all_nodes.sort(key=lambda x: x.last_seen)
            
        elif policy == "lfu":
            # Sort by count (ascending - least frequent first)
            all_nodes.sort(key=lambda x: x.count)
            
        elif policy == "cost_aware":
            # Sort by eviction score: recompute_cost / count
            # Lower score = easier to evict
            def eviction_score(node: TrieNode) -> float:
                recompute_cost = node.token_depth
                frequency_weight = max(node.count, 1)  # Avoid division by zero
                return recompute_cost / frequency_weight
            
            all_nodes.sort(key=eviction_score)
            
        else:
            raise ValueError(f"Unknown eviction policy: {policy}")
        
        return all_nodes
    
    def evict_nodes(self, target_count: int) -> List[TrieNode]:
        """
        Evict nodes to reach target node count.
        
        This is a simplified version focusing on leaf nodes for safety.
        In production, this would need more sophisticated tree restructuring.
        
        Args:
            target_count: Target number of nodes after eviction
            
        Returns:
            List of evicted TrieNode objects
        """
        if self.total_nodes <= target_count:
            return []
        
        nodes_to_remove = self.total_nodes - target_count
        evicted_nodes = []
        
        # Get leaf nodes (nodes with no children) ordered by LRU
        leaf_nodes = []
        
        def find_leaf_nodes(node: TrieNode, parent: TrieNode = None):
            if not node.children and node.token_id != -1:  # Leaf, not root
                leaf_nodes.append((node, parent))
            
            for child in node.children.values():
                find_leaf_nodes(child, node)
        
        find_leaf_nodes(self.root)
        
        # Sort leaves by last_seen (oldest first)
        leaf_nodes.sort(key=lambda x: x[0].last_seen)
        
        # Remove oldest leaf nodes
        for node, parent in leaf_nodes[:nodes_to_remove]:
            if parent:
                # Remove from parent's children
                for token_id, child in list(parent.children.items()):
                    if child is node:
                        del parent.children[token_id]
                        break
                        
                evicted_nodes.append(node)
                self.total_nodes -= 1
                
                if self.total_nodes <= target_count:
                    break
        
        return evicted_nodes
    
    def get_total_nodes(self) -> int:
        """Get total number of nodes in the trie."""
        return self.total_nodes
    
    def get_stats(self) -> Dict[str, Union[int, float]]:
        """
        Get trie statistics.
        
        Returns:
            Dictionary with node counts, depths, and other metrics
        """
        max_depth = 0
        leaf_count = 0
        
        def analyze_tree(node: TrieNode):
            nonlocal max_depth, leaf_count
            
            if node.token_depth > max_depth:
                max_depth = node.token_depth
                
            if not node.children and node.token_id != -1:
                leaf_count += 1
                
            for child in node.children.values():
                analyze_tree(child)
        
        analyze_tree(self.root)
        
        return {
            "total_nodes": self.total_nodes,
            "max_depth": max_depth,
            "leaf_nodes": leaf_count,
            "min_prefix_threshold": self.min_prefix_tokens,
            "branching_factor": len(self.root.children)
        }