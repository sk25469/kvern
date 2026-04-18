"""
trie_manager.py — Orchestration layer for the prefix trie.

This is the only layer the proxy talks to. It owns:
  - Per-model TrieNode roots
  - Per-model asyncio.Lock for insert/eviction concurrency
  - Memory cap enforcement (triggers eviction when nodes > max_nodes_per_model)
  - Config wiring (min_prefix_tokens, max_nodes_per_model)

prefix_trie.py has zero knowledge of models, locks, or caps. All of that lives here.

Concurrency model:
    lookup  — lock-free. Read-only; CPython GIL covers concurrent dict reads.
    insert  — acquires model lock. Concurrent inserts race on node.children mutations.
    evict   — acquires model lock. Mutates the tree.

    lookup and insert are intentionally separated so the proxy can do:
        depth, is_hit = manager.lookup(model, token_ids)   # no lock, fast
        asyncio.create_task(manager.insert(model, token_ids))  # async, off critical path
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .node import TrieNode
from .prefix_trie import (
    insert,
    lookup,
    hot_prefixes,
    eviction_candidates,
    evict_nodes,
    node_count,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class KVPrefixManager:
    def __init__(
        self,
        min_prefix_tokens: int = 32,
        max_nodes_per_model: int = 50_000,
        eviction_policy=None,  # EvictionPolicy instance; injected to avoid circular import
    ):
        self.min_prefix_tokens = min_prefix_tokens
        self.max_nodes_per_model = max_nodes_per_model
        self.eviction_policy = eviction_policy  # set after construction if needed

        self._roots: dict[str, TrieNode] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API — called by the proxy
    # ------------------------------------------------------------------

    def lookup(self, model: str, token_ids: list[int]) -> tuple[int, bool]:
        """
        Return (matched_depth, is_hit) for the given token sequence.

        Lock-free. Safe to call from async context without awaiting.
        """
        root = self._get_root(model)
        return lookup(root, token_ids, self.min_prefix_tokens)

    async def insert(self, model: str, token_ids: list[int]) -> None:
        """
        Insert token_ids into the model's trie.

        Acquires the model lock. Should be dispatched as asyncio.create_task()
        from the proxy so it doesn't add latency to the critical path.
        """
        root = self._get_root(model)
        lock = self._get_lock(model)
        now = time.time()

        async with lock:
            insert(root, token_ids, now)

        # Check memory cap outside the lock — node_count is read-only
        count = node_count(root)
        if count > self.max_nodes_per_model:
            logger.info(
                "model=%s node_count=%d exceeds cap=%d, triggering eviction",
                model, count, self.max_nodes_per_model,
            )
            asyncio.create_task(self._evict(model))

    async def record(
        self,
        model: str,
        token_ids: list[int],
    ) -> tuple[int, bool]:
        """
        Convenience method: lookup + async insert in one call.

        Returns (matched_depth, is_hit) from lookup (before insert, so the current
        request doesn't count as its own hit — consistent with "prior requests" semantics).

        Dispatches insert as a background task — does not await it.
        """
        depth, is_hit = self.lookup(model, token_ids)
        task = asyncio.create_task(self.insert(model, token_ids))
        # Store task reference to prevent it from being garbage collected
        if not hasattr(self, '_background_tasks'):
            self._background_tasks = set()
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return depth, is_hit

    async def wait_for_pending_inserts(self) -> None:
        """
        Wait for all background insert tasks to complete.
        Useful for testing scenarios where you need deterministic timing.
        """
        if hasattr(self, '_background_tasks'):
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks)

    async def record_sync(
        self,
        model: str,
        token_ids: list[int],
    ) -> tuple[int, bool]:
        """
        Synchronous version of record() for testing.
        Waits for the insert to complete before returning.
        """
        depth, is_hit = self.lookup(model, token_ids)
        await self.insert(model, token_ids)
        return depth, is_hit

    def hot_prefixes(self, model: str, n: int = 20) -> list[TrieNode]:
        """Top-N most reused nodes above min_prefix_tokens, by count."""
        root = self._get_root(model)
        return hot_prefixes(root, n, self.min_prefix_tokens)

    def node_count(self, model: str) -> int:
        """Current node count for a model's trie."""
        root = self._get_root(model)
        return node_count(root)

    def models(self) -> list[str]:
        """Models with active trie roots."""
        return list(self._roots.keys())

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    async def _evict(self, model: str) -> None:
        """
        Evict nodes from the model's trie until we're back under the memory cap.

        Uses the injected eviction_policy to rank candidates. Falls back to
        count-ascending (evict lowest-count leaves first) if no policy is set.

        Acquires the model lock for the full eviction pass.
        """
        root = self._get_root(model)
        lock = self._get_lock(model)

        async with lock:
            candidates = eviction_candidates(root)

            if not candidates:
                return

            if self.eviction_policy is not None:
                # Policy receives raw TrieNode objects and returns them ranked
                nodes_ranked = self.eviction_policy.rank([node for _, _, node in candidates])
                # Re-map back to (parent, token_id, node) triples in ranked order
                node_to_triple = {id(node): triple for triple in candidates for node in [triple[2]]}
                ranked_triples = [node_to_triple[id(n)] for n in nodes_ranked if id(n) in node_to_triple]
            else:
                # Default: evict lowest-count leaves first
                ranked_triples = sorted(candidates, key=lambda t: t[2].count)

            current_count = node_count(root)
            target_evictions = current_count - self.max_nodes_per_model

            if target_evictions <= 0:
                return  # another task already evicted enough

            evicted = evict_nodes(ranked_triples, target_evictions)
            logger.info("model=%s evicted=%d nodes", model, evicted)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_root(self, model: str) -> TrieNode:
        if model not in self._roots:
            self._roots[model] = TrieNode()
        return self._roots[model]

    def _get_lock(self, model: str) -> asyncio.Lock:
        if model not in self._locks:
            self._locks[model] = asyncio.Lock()
        return self._locks[model]