"""
Test fixtures for KVern components.

Provides reusable test data and mock objects for unit tests.
"""

import pytest
import asyncio
import tempfile
import os
from typing import List, Dict, Any
import time

from src.trie.node import TrieNode
from src.trie.prefix_trie import PrefixTrie
from src.analytics.store import AnalyticsStore


@pytest.fixture
def sample_conversations():
    """Sample conversation data for testing."""
    return [
        {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ],
            "expected_tokens": 12  # Approximate
        },
        {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is Python?"}
            ],
            "expected_tokens": 15  # Approximate
        },
        {
            "messages": [
                {"role": "system", "content": "You are a coding expert."},
                {"role": "user", "content": "Explain tries in Python"}
            ],
            "expected_tokens": 16  # Approximate
        }
    ]


@pytest.fixture
def sample_token_sequences():
    """Sample token ID sequences for trie testing."""
    return {
        "short_sequence": [1, 2, 3],
        "medium_sequence": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "long_sequence": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] + list(range(11, 51)),
        "shared_prefix": [1, 2, 3, 4, 5, 100, 101, 102],
        "different_suffix": [1, 2, 3, 4, 5, 200, 201, 202]
    }


@pytest.fixture
def empty_trie():
    """Empty trie for testing."""
    return PrefixTrie(min_prefix_tokens=5)


@pytest.fixture
def populated_trie(sample_token_sequences):
    """Trie populated with test data."""
    trie = PrefixTrie(min_prefix_tokens=5)
    
    # Insert test sequences multiple times to create different access patterns
    trie.insert(sample_token_sequences["long_sequence"])
    trie.insert(sample_token_sequences["long_sequence"])  # High frequency
    
    trie.insert(sample_token_sequences["shared_prefix"])
    trie.insert(sample_token_sequences["different_suffix"])
    
    trie.insert(sample_token_sequences["medium_sequence"])
    
    return trie


@pytest.fixture
def test_nodes():
    """Sample TrieNode objects for eviction testing."""
    current_time = time.time()
    
    return [
        TrieNode(
            token_id=100,
            count=10,
            token_depth=5,
            first_seen=current_time - 3600,  # 1 hour ago
            last_seen=current_time - 300     # 5 minutes ago
        ),
        TrieNode(
            token_id=200,
            count=2,
            token_depth=50,
            first_seen=current_time - 7200,  # 2 hours ago
            last_seen=current_time - 1800    # 30 minutes ago
        ),
        TrieNode(
            token_id=300,
            count=20,
            token_depth=10,
            first_seen=current_time - 1800,  # 30 minutes ago
            last_seen=current_time - 60      # 1 minute ago
        ),
        TrieNode(
            token_id=400,
            count=1,
            token_depth=5,
            first_seen=current_time - 900,   # 15 minutes ago
            last_seen=current_time - 900     # 15 minutes ago (only accessed once)
        )
    ]


@pytest.fixture
def temp_db():
    """Temporary SQLite database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    yield path
    
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
async def analytics_store(temp_db):
    """Analytics store with temporary database."""
    store = AnalyticsStore(temp_db)
    await store.initialize()
    
    yield store
    
    await store.close()


@pytest.fixture
def mock_requests():
    """Mock request data for analytics testing."""
    return [
        {
            "request_id": "req-001",
            "model": "test-llama",
            "prompt_tokens": 50,
            "shared_prefix_tokens": 30,
            "is_hit": True,
            "backend_latency_ms": 120.5
        },
        {
            "request_id": "req-002", 
            "model": "test-llama",
            "prompt_tokens": 45,
            "shared_prefix_tokens": None,
            "is_hit": False,
            "backend_latency_ms": 89.2
        },
        {
            "request_id": "req-003",
            "model": "test-mistral",
            "prompt_tokens": 60,
            "shared_prefix_tokens": 40,
            "is_hit": True,
            "backend_latency_ms": 156.8
        }
    ]


@pytest.fixture
def event_loop():
    """Event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mock tokenizer responses
@pytest.fixture
def mock_tokenizer_responses():
    """Mock tokenizer responses for testing."""
    return {
        "simple_prompt": {
            "input": [{"role": "user", "content": "Hello"}],
            "token_ids": [128000, 128006, 882, 128007, 271, 9906, 128009]
        },
        "system_prompt": {
            "input": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"}
            ],
            "token_ids": [128000, 128006, 9125, 128007, 271, 2675, 527, 11190, 13, 128009, 128006, 882, 128007, 271, 13347, 128009]
        },
        "long_conversation": {
            "input": [
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": "Explain how tries work in computer science."},
                {"role": "assistant", "content": "A trie is a tree data structure..."},
                {"role": "user", "content": "Can you show me Python code?"}
            ],
            "token_ids": list(range(1, 101))  # 100 tokens for testing
        }
    }


# Performance benchmarking helpers
class TimingContext:
    """Context manager for timing operations in tests."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time


@pytest.fixture
def timing_context():
    """Timing context for performance tests."""
    return TimingContext


# Configuration fixtures
@pytest.fixture
def test_config():
    """Test configuration values."""
    return {
        "min_prefix_tokens": 5,
        "max_nodes_per_model": 1000,
        "cost_per_token": 1.0,
        "decay_rate": 0.01,
        "backend_timeout": 30.0
    }