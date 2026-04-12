"""
Analytics query engine for KVern performance insights.

Provides higher-level querying and analysis capabilities on top of
the raw analytics store data.
"""

import sqlite3
import aiosqlite
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import time


class AnalyticsQueryEngine:
    """
    Query engine for KVern analytics insights.
    
    Provides time-windowed queries, trend analysis, and performance insights
    beyond basic summary statistics.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize query engine.
        
        Args:
            db_path: Path to SQLite analytics database
        """
        self.db_path = db_path
    
    async def get_hit_rate_timeline(
        self, 
        hours: int = 24, 
        bucket_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get hit rate over time in buckets.
        
        Args:
            hours: Time window in hours
            bucket_minutes: Bucket size in minutes
            
        Returns:
            List of time buckets with hit rates
        """
        cutoff_time = time.time() - (hours * 3600)
        bucket_seconds = bucket_minutes * 60
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    (CAST(ts / ? AS INTEGER) * ?) as bucket_start,
                    COUNT(*) as total_requests,
                    SUM(is_hit) as hits
                FROM prefix_events 
                WHERE ts > ?
                GROUP BY bucket_start
                ORDER BY bucket_start
            """, (bucket_seconds, bucket_seconds, cutoff_time))
            
            rows = await cursor.fetchall()
        
        timeline = []
        for bucket_start, total_requests, hits in rows:
            hit_rate = (hits / total_requests) if total_requests > 0 else 0
            timeline.append({
                "timestamp": bucket_start,
                "datetime": datetime.fromtimestamp(bucket_start).isoformat(),
                "total_requests": total_requests,
                "hits": hits,
                "hit_rate": hit_rate
            })
        
        return timeline
    
    async def get_model_comparison(self, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """
        Compare cache performance across models.
        
        Args:
            hours: Time window in hours
            
        Returns:
            Dictionary of model performance metrics
        """
        cutoff_time = time.time() - (hours * 3600)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    model,
                    COUNT(*) as total_requests,
                    SUM(is_hit) as hits,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(COALESCE(shared_prefix_tokens, 0)) as total_shared_tokens,
                    AVG(backend_latency_ms) as avg_latency_ms,
                    MIN(ts) as first_request,
                    MAX(ts) as last_request
                FROM prefix_events 
                WHERE ts > ?
                GROUP BY model
            """, (cutoff_time,))
            
            rows = await cursor.fetchall()
        
        model_stats = {}
        for row in rows:
            (model, total_requests, hits, total_prompt_tokens, 
             total_shared_tokens, avg_latency, first_request, last_request) = row
            
            hit_rate = (hits / total_requests) if total_requests > 0 else 0
            token_reuse_ratio = (
                (total_shared_tokens / total_prompt_tokens) 
                if total_prompt_tokens > 0 else 0
            )
            
            model_stats[model] = {
                "total_requests": total_requests,
                "hits": hits,
                "hit_rate": hit_rate,
                "total_prompt_tokens": total_prompt_tokens,
                "total_shared_tokens": total_shared_tokens,
                "token_reuse_ratio": token_reuse_ratio,
                "avg_latency_ms": avg_latency,
                "compute_savings_pct": token_reuse_ratio * 100,
                "first_request": datetime.fromtimestamp(first_request).isoformat(),
                "last_request": datetime.fromtimestamp(last_request).isoformat()
            }
        
        return model_stats
    
    async def get_prefix_depth_distribution(
        self, 
        model: str, 
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get distribution of shared prefix depths for cache hits.
        
        Args:
            model: Model to analyze
            hours: Time window in hours
            
        Returns:
            List of depth buckets with counts
        """
        cutoff_time = time.time() - (hours * 3600)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    CASE 
                        WHEN shared_prefix_tokens < 10 THEN '0-9'
                        WHEN shared_prefix_tokens < 50 THEN '10-49'
                        WHEN shared_prefix_tokens < 100 THEN '50-99'
                        WHEN shared_prefix_tokens < 200 THEN '100-199'
                        WHEN shared_prefix_tokens < 500 THEN '200-499'
                        ELSE '500+'
                    END as depth_bucket,
                    COUNT(*) as count,
                    AVG(shared_prefix_tokens) as avg_depth
                FROM prefix_events 
                WHERE model = ? AND ts > ? AND is_hit = 1 AND shared_prefix_tokens IS NOT NULL
                GROUP BY depth_bucket
                ORDER BY avg_depth
            """, (model, cutoff_time))
            
            rows = await cursor.fetchall()
        
        return [
            {
                "depth_bucket": bucket,
                "count": count,
                "avg_depth": round(avg_depth, 1) if avg_depth else 0
            }
            for bucket, count, avg_depth in rows
        ]
    
    async def get_latency_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze backend latency patterns.
        
        Args:
            hours: Time window in hours
            
        Returns:
            Latency analysis metrics
        """
        cutoff_time = time.time() - (hours * 3600)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Overall latency stats
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    AVG(backend_latency_ms) as avg_latency,
                    MIN(backend_latency_ms) as min_latency,
                    MAX(backend_latency_ms) as max_latency
                FROM prefix_events 
                WHERE ts > ? AND backend_latency_ms IS NOT NULL
            """, (cutoff_time,))
            overall_stats = await cursor.fetchone()
            
            # Hit vs Miss latency comparison
            cursor = await db.execute("""
                SELECT 
                    is_hit,
                    COUNT(*) as count,
                    AVG(backend_latency_ms) as avg_latency,
                    AVG(prompt_tokens) as avg_prompt_tokens
                FROM prefix_events 
                WHERE ts > ? AND backend_latency_ms IS NOT NULL
                GROUP BY is_hit
            """, (cutoff_time,))
            hit_miss_stats = {
                ("hit" if is_hit else "miss"): {
                    "count": count,
                    "avg_latency_ms": avg_latency,
                    "avg_prompt_tokens": avg_prompt_tokens
                }
                for is_hit, count, avg_latency, avg_prompt_tokens in await cursor.fetchall()
            }
        
        return {
            "total_requests_with_latency": overall_stats[0] or 0,
            "overall_avg_latency_ms": overall_stats[1],
            "overall_min_latency_ms": overall_stats[2],
            "overall_max_latency_ms": overall_stats[3],
            "hit_miss_comparison": hit_miss_stats
        }
    
    async def get_cache_pressure_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze cache pressure and optimization opportunities.
        
        Args:
            hours: Time window in hours
            
        Returns:
            Cache pressure analysis
        """
        cutoff_time = time.time() - (hours * 3600)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Request rate analysis
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) / (? / 3600.0) as requests_per_hour,
                    COUNT(DISTINCT model) as unique_models,
                    AVG(prompt_tokens) as avg_prompt_length
                FROM prefix_events 
                WHERE ts > ?
            """, (hours * 3600, cutoff_time))
            rate_stats = await cursor.fetchone()
            
            # Miss pattern analysis
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total_misses,
                    AVG(prompt_tokens) as avg_miss_prompt_tokens,
                    model
                FROM prefix_events 
                WHERE ts > ? AND is_hit = 0
                GROUP BY model
            """, (cutoff_time,))
            miss_patterns = {
                model: {
                    "total_misses": total_misses,
                    "avg_miss_prompt_tokens": avg_miss_prompt_tokens
                }
                for total_misses, avg_miss_prompt_tokens, model in await cursor.fetchall()
            }
            
            # Hot prefix concentration
            cursor = await db.execute("""
                SELECT 
                    model,
                    COUNT(*) as unique_prefixes,
                    MAX(count) as max_prefix_count,
                    AVG(count) as avg_prefix_count
                FROM hot_prefixes
                GROUP BY model
            """, ())
            hot_prefix_stats = {
                model: {
                    "unique_prefixes": unique_prefixes,
                    "max_prefix_count": max_prefix_count,
                    "avg_prefix_count": avg_prefix_count
                }
                for model, unique_prefixes, max_prefix_count, avg_prefix_count in await cursor.fetchall()
            }
        
        return {
            "requests_per_hour": rate_stats[0] or 0,
            "unique_models": rate_stats[1] or 0,
            "avg_prompt_length": rate_stats[2] or 0,
            "miss_patterns_by_model": miss_patterns,
            "hot_prefix_distribution": hot_prefix_stats
        }
    
    async def identify_optimization_opportunities(
        self, 
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Identify potential cache optimization opportunities.
        
        Args:
            hours: Time window in hours
            
        Returns:
            List of optimization suggestions
        """
        opportunities = []
        
        # Check hit rate by model
        model_stats = await self.get_model_comparison(hours)
        for model, stats in model_stats.items():
            if stats["hit_rate"] < 0.3 and stats["total_requests"] > 10:
                opportunities.append({
                    "type": "low_hit_rate",
                    "model": model,
                    "hit_rate": stats["hit_rate"],
                    "suggestion": f"Model {model} has low hit rate ({stats['hit_rate']:.1%}). Consider increasing min_prefix_tokens or investigating prefix diversity."
                })
        
        # Check for high-frequency misses with similar tokens
        cutoff_time = time.time() - (hours * 3600)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    model,
                    prompt_tokens,
                    COUNT(*) as miss_count
                FROM prefix_events 
                WHERE ts > ? AND is_hit = 0
                GROUP BY model, prompt_tokens
                HAVING miss_count > 3
                ORDER BY miss_count DESC
                LIMIT 5
            """, (cutoff_time,))
            
            for model, prompt_tokens, miss_count in await cursor.fetchall():
                opportunities.append({
                    "type": "repeated_miss_pattern",
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "miss_count": miss_count,
                    "suggestion": f"Frequent misses for {prompt_tokens}-token prompts in {model}. May indicate template drift or tokenizer issues."
                })
        
        return opportunities