from .node import TrieNode
from typing import List, Tuple

class KVPrefixManager:
    def __init__(self, max_nodes: int = 10000):
        self.root = TrieNode(token_id=-1)  # Dummy root
        self.max_nodes = max_nodes
        self.current_node_count = 0

    def insert(self, token_ids: List[int]):
        current = self.root
        for tid in token_ids:
            if tid in current.children:
                current.children[tid].touch()
            else:
                current.children[tid] = TrieNode(token_id=tid)
                self.current_node_count += 1
            current = current.children[tid]

    def find_longest_common_prefix(self, token_ids: List[int]) -> int:
        """
        Returns the number of tokens that can be served from KV Cache.
        """
        current = self.root
        match_count = 0
        
        for tid in token_ids:
            if tid in current.children:
                match_count += 1
                current = current.children[tid]
                current.touch() # Important: we 'touch' it because we're using it!
            else:
                break
        return match_count