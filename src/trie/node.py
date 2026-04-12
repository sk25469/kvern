import time
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class TrieNode:
    token_id: int
    children: Dict[int, 'TrieNode'] = field(default_factory=dict)
    
    # Metadata for the "Eviction Bitch"
    count: int = 1
    last_accessed: float = field(default_factory=time.time)

    def touch(self):
        """Update metadata when this node is part of a cache hit."""
        self.count += 1
        self.last_accessed = time.time()

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0