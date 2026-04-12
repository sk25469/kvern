"""
Test package for KVern components.

Contains unit tests for trie operations, eviction policies, tokenizer pipeline,
and analytics functionality.
"""

# Test configuration
TEST_CONFIG = {
    "test_db_path": ":memory:",  # In-memory SQLite for tests
    "test_models": {
        "test-llama": "meta-llama/Llama-3.2-1B-Instruct",
        "test-mistral": "mistralai/Mistral-7B-Instruct-v0.2"
    },
    "min_prefix_tokens": 5,  # Lower threshold for testing
    "eviction_policies": ["lru", "lfu_decay", "cost_aware"]
}

__all__ = ["TEST_CONFIG"]