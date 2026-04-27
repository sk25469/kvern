#!/usr/bin/env python3
"""
Better test to understand KVern's cache hit logic by examining token patterns.
"""

import requests
import json
import time

PROXY_URL = "http://localhost:8080"
MODEL = "llama3.2:1b"

def detailed_cache_test():
    """Test with detailed token analysis."""
    
    print("🔬 Detailed Cache Hit Analysis\n")
    
    system_prompt = "You are a helpful AI assistant specialized in explaining technical concepts clearly and concisely."
    
    test_cases = [
        {"name": "Baseline", "messages": [{"role": "user", "content": "What is Python?"}]},
        {"name": "System+Q1", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": "What is machine learning?"}]},
        {"name": "System+Q2", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": "What is deep learning?"}]},
        {"name": "System+Q3", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": "What is neural network?"}]},
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"🧪 Test {i+1}: {test_case['name']}")
        
        # Get detailed metrics before
        before = requests.get(f"{PROXY_URL}/metrics").json()
        before_trie = before['trie']['models'].get(MODEL, {'node_count': 0})
        before_analytics = before['analytics']
        
        print(f"  📊 Before: Nodes={before_trie['node_count']}, Requests={before_analytics['total_requests']}, Hits={before_analytics['hits']}")
        
        # Send request
        start = time.time()
        response = requests.post(f"{PROXY_URL}/v1/chat/completions", 
            headers={"Content-Type": "application/json"},
            json={"model": MODEL, "messages": test_case["messages"], "stream": False})
        latency = (time.time() - start) * 1000
        
        # Wait and get metrics after
        time.sleep(3)  # Give analytics time to flush
        after = requests.get(f"{PROXY_URL}/metrics").json()
        after_trie = after['trie']['models'].get(MODEL, {'node_count': 0})
        after_analytics = after['analytics']
        
        print(f"  📊 After:  Nodes={after_trie['node_count']}, Requests={after_analytics['total_requests']}, Hits={after_analytics['hits']}")
        print(f"  📈 Delta:  Nodes=+{after_trie['node_count'] - before_trie['node_count']}, Requests=+{after_analytics['total_requests'] - before_analytics['total_requests']}, Hits=+{after_analytics['hits'] - before_analytics['hits']}")
        print(f"  ⏱️  Latency: {latency:.1f}ms")
        
        # Determine cache hit based on multiple signals
        hit_by_analytics = (after_analytics['hits'] - before_analytics['hits']) > 0
        requests_processed = (after_analytics['total_requests'] - before_analytics['total_requests']) > 0
        
        print(f"  🎯 Analytics says cache hit: {hit_by_analytics}")
        print(f"  📝 Request was processed: {requests_processed}")
        print()

if __name__ == "__main__":
    detailed_cache_test()