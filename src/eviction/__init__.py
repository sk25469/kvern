"""
Eviction policy engine for KVern trie cache management.

This package provides pluggable eviction policies for memory management:
- LRU (Least Recently Used)
- LFU with decay 
- Cost-aware (considers recompute cost vs access frequency)
"""

from .base import EvictionPolicy
from .lru import LRUEvictionPolicy
from .lfu_decay import LFUDecayEvictionPolicy  
from .cost_aware import CostAwareEvictionPolicy

# Registry of available policies
POLICY_REGISTRY = {
    "lru": LRUEvictionPolicy,
    "lfu_decay": LFUDecayEvictionPolicy,
    "cost_aware": CostAwareEvictionPolicy,
}

def get_eviction_policy(policy_name: str, **kwargs) -> EvictionPolicy:
    """
    Factory function to create eviction policy instances.
    
    Args:
        policy_name: Name of the eviction policy ('lru', 'lfu_decay', 'cost_aware')
        **kwargs: Additional parameters for the policy
        
    Returns:
        EvictionPolicy instance
        
    Raises:
        ValueError: If policy_name is not recognized
    """
    if policy_name not in POLICY_REGISTRY:
        available = list(POLICY_REGISTRY.keys())
        raise ValueError(f"Unknown policy '{policy_name}'. Available: {available}")
    
    policy_class = POLICY_REGISTRY[policy_name]
    return policy_class(**kwargs)

__all__ = [
    "EvictionPolicy",
    "LRUEvictionPolicy", 
    "LFUDecayEvictionPolicy",
    "CostAwareEvictionPolicy",
    "get_eviction_policy",
    "POLICY_REGISTRY",
]