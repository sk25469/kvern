#!/usr/bin/env python3
"""
Test script to validate KVern's cache hit predictions against actual latencies.
Tests the hypothesis: Do KVern's cache hits correlate with faster response times?
"""

import time
import json
import requests
from typing import List, Dict, Any

PROXY_URL = "http://localhost:8080"
MODEL = "llama3.2:1b"

def time_request(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Send request and measure latency."""
    start_time = time.time()
    
    response = requests.post(
        f"{PROXY_URL}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False
        }
    )
    
    end_time = time.time()
    latency_ms = (end_time - start_time) * 1000
    
    return {
        "latency_ms": latency_ms,
        "response": response.json() if response.status_code == 200 else None,
        "status": response.status_code
    }

def get_metrics() -> Dict[str, Any]:
    """Get KVern metrics."""
    response = requests.get(f"{PROXY_URL}/metrics")
    return response.json() if response.status_code == 200 else {}

def test_prefix_caching_hypothesis():
    """Test if KVern's cache hits correlate with faster responses."""
    
    print("🧪 Testing KVern Cache Hit vs Actual Latency Correlation\n")
    
    # Clear initial metrics
    initial_metrics = get_metrics()
    print(f"Initial state: {initial_metrics['analytics']['total_requests']} total requests")
    
    # Test 1: Send identical requests (should hit ollama's internal cache if it exists)
    print("\n📊 Test 1: Identical Request Latency Test")
    identical_prompt = [{"role": "user", "content": "What is the capital of France?"}]
    
    latencies = []
    for i in range(3):
        print(f"  Request {i+1}/3...", end="")
        result = time_request(identical_prompt)
        latencies.append(result["latency_ms"])
        print(f" {result['latency_ms']:.1f}ms")
        time.sleep(1)  # Brief pause between requests
    
    print(f"  📈 Latencies: {[f'{l:.1f}ms' for l in latencies]}")
    print(f"  📊 Trend: {'Decreasing (possible internal caching)' if latencies[-1] < latencies[0] * 0.8 else 'Stable (no obvious internal caching)'}")
    
    # Test 2: Prefix overlap test
    print("\n📊 Test 2: Prefix Overlap vs Latency Test")
    
    system_prompt = "You are a helpful AI assistant specialized in explaining technical concepts clearly and concisely."
    
    test_cases = [
        {
            "name": "Unique prompt (no overlap)",
            "messages": [{"role": "user", "content": "Tell me about quantum computing basics."}]
        },
        {
            "name": "With system prompt (first time)",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is machine learning?"}
            ]
        },
        {
            "name": "Same system prompt (second time)",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is deep learning?"}
            ]
        },
        {
            "name": "Same system prompt (third time)",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is neural network?"}
            ]
        }
    ]
    
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"  Test {i+1}: {test_case['name']}...", end="")
        
        # Get metrics before
        metrics_before = get_metrics()
        requests_before = metrics_before['analytics']['total_requests']
        hits_before = metrics_before['analytics']['hits']
        
        # Send request
        result = time_request(test_case["messages"])
        
        # Get metrics after
        time.sleep(2)  # Allow analytics to flush
        metrics_after = get_metrics()
        requests_after = metrics_after['analytics']['total_requests']
        hits_after = metrics_after['analytics']['hits']
        
        # Calculate if this request was a cache hit
        was_cache_hit = (hits_after - hits_before) > 0
        cache_hit_str = "✅ CACHE HIT" if was_cache_hit else "❌ CACHE MISS"
        
        print(f" {result['latency_ms']:.1f}ms {cache_hit_str}")
        
        results.append({
            "test": test_case['name'],
            "latency_ms": result['latency_ms'],
            "cache_hit": was_cache_hit
        })
    
    # Analysis
    print(f"\n📈 Analysis:")
    cache_hits = [r for r in results if r['cache_hit']]
    cache_misses = [r for r in results if not r['cache_hit']]
    
    if cache_hits and cache_misses:
        avg_hit_latency = sum(r['latency_ms'] for r in cache_hits) / len(cache_hits)
        avg_miss_latency = sum(r['latency_ms'] for r in cache_misses) / len(cache_misses)
        
        print(f"  📊 Average cache hit latency:  {avg_hit_latency:.1f}ms")
        print(f"  📊 Average cache miss latency: {avg_miss_latency:.1f}ms")
        print(f"  📊 Difference: {avg_miss_latency - avg_hit_latency:.1f}ms")
        
        if avg_hit_latency < avg_miss_latency * 0.9:
            print(f"  ✅ KVern cache hits correlate with faster responses!")
            print(f"  💡 This suggests KVern is detecting real computational reuse.")
        else:
            print(f"  ⚠️  No clear latency difference between hits/misses.")
            print(f"  💡 This suggests either:")
            print(f"      - Ollama already has internal caching")
            print(f"      - Network/other factors dominate latency")
    
    # Final metrics
    final_metrics = get_metrics()
    print(f"\n📋 Final KVern State:")
    analytics = final_metrics['analytics']
    print(f"  📊 Total requests: {analytics['total_requests']}")
    print(f"  🎯 Hit rate: {analytics['hit_rate']:.1%}")
    print(f"  💾 Token reuse ratio: {analytics['token_reuse_ratio']:.1%}")
    print(f"  ⚡ Theoretical savings: {analytics['theoretical_compute_savings_pct']:.1f}%")
    
    if analytics['hit_rate'] > 0:
        print(f"\n💡 Interpretation:")
        print(f"  KVern detected {analytics['hit_rate']:.1%} prefix overlap")
        print(f"  This represents {analytics['theoretical_compute_savings_pct']:.1f}% theoretical compute savings")
        print(f"  Whether this is 'real' depends on if your latency tests showed correlation!")

if __name__ == "__main__":
    try:
        test_prefix_caching_hypothesis()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure KVern proxy is running on localhost:8080")