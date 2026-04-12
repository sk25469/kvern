"""
Analytics package for KVern cache performance tracking.

This package provides SQLite-based storage and querying for:
- Prefix event tracking (hits, misses, latencies)
- Aggregate metrics computation
- Time-windowed analytics
- Hot prefix identification
"""

from .store import AnalyticsStore
from .queries import AnalyticsQueryEngine

__all__ = [
    "AnalyticsStore",
    "AnalyticsQueryEngine",
]