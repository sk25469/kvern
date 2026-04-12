"""
KVern - LLM KV Cache Manager using token-level Trie optimization.

A transparent proxy that optimizes LLM inference by tracking and managing
Key-Value cache reuse across requests using token-level trie data structures.
"""

__version__ = "0.1.0"
__author__ = "Sahil"
__description__ = "LLM KV Cache Manager using token-level Trie optimization"

# Package-level imports for convenience
from .trie.prefix_trie import PrefixTrie
from .eviction import get_eviction_policy
from .analytics.store import AnalyticsStore

__all__ = [
    "PrefixTrie",
    "get_eviction_policy", 
    "AnalyticsStore",
]