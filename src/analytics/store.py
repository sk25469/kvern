"""
SQLite analytics store for KVern cache events.

Persists trie traversal events, response latencies, and metadata for
computing cache performance metrics.
"""

import sqlite3
import aiosqlite
import asyncio
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import hashlib
import json


@dataclass
class PrefixEvent:
    """Represents a prefix cache event."""
    request_id: str
    model: str
    prompt_tokens: int
    shared_prefix_tokens: Optional[int]
    is_hit: bool
    timestamp: float
    backend_latency_ms: Optional[float] = None


@dataclass 
class HotPrefixRecord:
    """Represents a hot prefix for analytics storage."""
    model: str
    prefix_hash: str
    token_depth: int
    count: int
    last_seen: float
    first_seen: float


class AnalyticsStore:
    """
    SQLite-based analytics store for KVern cache performance.
    
    Features:
    - Async SQLite operations
    - Event recording with batching
    - Hot prefix tracking
    - Configurable retention
    """
    
    def __init__(self, db_path: str = "./data/cache_analytics.db"):
        """
        Initialize analytics store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._db_lock = asyncio.Lock()
        self._batch_events = []
        self._batch_size = 100
        self._last_flush = time.time()
        
    async def initialize(self) -> None:
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS prefix_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    model TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    shared_prefix_tokens INTEGER,
                    is_hit INTEGER NOT NULL,
                    backend_latency_ms REAL
                );
                
                CREATE INDEX IF NOT EXISTS idx_prefix_events_ts ON prefix_events(ts);
                CREATE INDEX IF NOT EXISTS idx_prefix_events_model ON prefix_events(model);
                CREATE INDEX IF NOT EXISTS idx_prefix_events_hit ON prefix_events(is_hit);
                
                CREATE TABLE IF NOT EXISTS hot_prefixes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT NOT NULL,
                    prefix_hash TEXT NOT NULL,
                    token_depth INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    last_seen REAL NOT NULL,
                    first_seen REAL NOT NULL,
                    UNIQUE(model, prefix_hash)
                );
                
                CREATE INDEX IF NOT EXISTS idx_hot_prefixes_model ON hot_prefixes(model);
                CREATE INDEX IF NOT EXISTS idx_hot_prefixes_count ON hot_prefixes(count);
            """)
            await db.commit()
    
    async def record_event(
        self,
        request_id: str,
        model: str,
        prompt_tokens: int,
        shared_prefix_tokens: Optional[int],
        is_hit: bool,
        timestamp: Optional[float] = None
    ) -> None:
        """
        Record a prefix cache event.
        
        Args:
            request_id: Unique request identifier
            model: Model name
            prompt_tokens: Total prompt token count
            shared_prefix_tokens: Tokens shared with cache (None for miss)
            is_hit: Whether this was a cache hit
            timestamp: Event timestamp (current time if None)
        """
        if timestamp is None:
            timestamp = time.time()
            
        event = PrefixEvent(
            request_id=request_id,
            model=model,
            prompt_tokens=prompt_tokens,
            shared_prefix_tokens=shared_prefix_tokens,
            is_hit=is_hit,
            timestamp=timestamp
        )
        
        async with self._db_lock:
            self._batch_events.append(event)
            
            # Flush if batch is full or enough time has passed
            if (len(self._batch_events) >= self._batch_size or 
                time.time() - self._last_flush > 10):  # Reduce to 10 seconds for better responsiveness
                await self._flush_events()
    
    async def update_latency(self, request_id: str, backend_latency_ms: float) -> None:
        """
        Update backend latency for a recorded event.
        
        Args:
            request_id: Request identifier to update
            backend_latency_ms: Backend latency in milliseconds
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE prefix_events SET backend_latency_ms = ? WHERE request_id = ?",
                (backend_latency_ms, request_id)
            )
            await db.commit()
    
    async def record_hot_prefix(
        self,
        model: str,
        token_ids: List[int],
        token_depth: int,
        count: int,
        last_seen: float,
        first_seen: float
    ) -> None:
        """
        Record or update a hot prefix.
        
        Args:
            model: Model name
            token_ids: Token sequence for this prefix
            token_depth: Prefix depth
            count: Access count
            last_seen: Last access timestamp
            first_seen: First access timestamp
        """
        # Hash token sequence for storage
        prefix_hash = hashlib.sha256(
            json.dumps(token_ids, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO hot_prefixes 
                (model, prefix_hash, token_depth, count, last_seen, first_seen)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (model, prefix_hash, token_depth, count, last_seen, first_seen))
            await db.commit()
    
    async def _flush_events(self) -> None:
        """Flush batched events to database."""
        if not self._batch_events:
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            event_data = [
                (
                    event.timestamp,
                    event.model,
                    event.request_id,
                    event.prompt_tokens,
                    event.shared_prefix_tokens,
                    1 if event.is_hit else 0,
                    event.backend_latency_ms
                )
                for event in self._batch_events
            ]
            
            await db.executemany("""
                INSERT INTO prefix_events 
                (ts, model, request_id, prompt_tokens, shared_prefix_tokens, is_hit, backend_latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, event_data)
            await db.commit()
        
        self._batch_events.clear()
        self._last_flush = time.time()
    
    async def get_summary_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary cache statistics.
        
        Args:
            hours: Time window in hours
            
        Returns:
            Dictionary with cache performance metrics
        """
        cutoff_time = time.time() - (hours * 3600)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Basic hit rate
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(is_hit) as hits,
                    AVG(backend_latency_ms) as avg_latency_ms
                FROM prefix_events 
                WHERE ts > ?
            """, (cutoff_time,))
            row = await cursor.fetchone()
            
            # Handle case where query returns no rows
            if row is None:
                total_requests, hits, avg_latency = 0, 0, None
            else:
                total_requests, hits, avg_latency = row
            
            # Handle None values from SQL aggregations
            total_requests = total_requests or 0
            hits = hits or 0
            avg_latency = avg_latency  # Keep None for avg_latency as it's meaningful
            
            hit_rate = (hits / total_requests) if total_requests > 0 else 0
            
            # Token reuse ratio
            cursor = await db.execute("""
                SELECT 
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(COALESCE(shared_prefix_tokens, 0)) as total_shared_tokens
                FROM prefix_events 
                WHERE ts > ?
            """, (cutoff_time,))
            row = await cursor.fetchone()
            
            # Handle case where query returns no rows
            if row is None:
                total_prompt_tokens, total_shared_tokens = 0, 0
            else:
                total_prompt_tokens, total_shared_tokens = row
            
            # Handle None values from SQL aggregations  
            total_prompt_tokens = total_prompt_tokens or 0
            total_shared_tokens = total_shared_tokens or 0
            
            token_reuse_ratio = (
                (total_shared_tokens / total_prompt_tokens) 
                if total_prompt_tokens > 0 else 0
            )
            
            # Model breakdown
            cursor = await db.execute("""
                SELECT 
                    model,
                    COUNT(*) as requests,
                    SUM(is_hit) as hits
                FROM prefix_events 
                WHERE ts > ?
                GROUP BY model
            """, (cutoff_time,))
            model_stats = {
                row[0]: {"requests": row[1], "hits": row[2] or 0} 
                for row in await cursor.fetchall()
            }
        
        return {
            "time_window_hours": hours,
            "total_requests": total_requests or 0,
            "hits": hits or 0,
            "hit_rate": hit_rate,
            "token_reuse_ratio": token_reuse_ratio,
            "avg_backend_latency_ms": avg_latency,
            "theoretical_compute_savings_pct": token_reuse_ratio * 100,
            "model_breakdown": model_stats
        }
    
    async def get_hot_prefixes(self, model: str, limit: int = 10) -> List[HotPrefixRecord]:
        """
        Get hot prefixes for a model.
        
        Args:
            model: Model name to query
            limit: Maximum number of results
            
        Returns:
            List of HotPrefixRecord objects
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT model, prefix_hash, token_depth, count, last_seen, first_seen
                FROM hot_prefixes 
                WHERE model = ?
                ORDER BY count DESC
                LIMIT ?
            """, (model, limit))
            
            rows = await cursor.fetchall()
            
        return [
            HotPrefixRecord(
                model=row[0],
                prefix_hash=row[1],
                token_depth=row[2],
                count=row[3],
                last_seen=row[4],
                first_seen=row[5]
            )
            for row in rows
        ]
    
    async def cleanup_old_data(self, retention_days: int = 30) -> None:
        """
        Remove old data beyond retention period.
        
        Args:
            retention_days: Data retention in days
        """
        cutoff_time = time.time() - (retention_days * 24 * 3600)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Clean old events
            await db.execute("DELETE FROM prefix_events WHERE ts < ?", (cutoff_time,))
            
            # Clean old hot prefixes that haven't been seen recently
            await db.execute("DELETE FROM hot_prefixes WHERE last_seen < ?", (cutoff_time,))
            
            await db.commit()
    
    async def close(self) -> None:
        """Close store and flush any pending events."""
        async with self._db_lock:
            await self._flush_events()