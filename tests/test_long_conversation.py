#!/usr/bin/env python3
"""
Test KVern with realistic long conversation scenario.
This tests prefix caching with substantial system prompts and multi-turn conversations.
"""

import requests
import json
import time
from typing import List, Dict

PROXY_URL = "http://localhost:8080"
MODEL = "llama3.2:1b"

def test_long_conversation():
    """Test KVern with realistic long conversation patterns."""
    
    print("🗣️  Testing Realistic Long Conversation Caching\n")
    
    # Realistic detailed system prompt (common in production)
    system_prompt = """You are Claude, an AI assistant created by Anthropic. You are a highly capable AI assistant with expertise across many domains including science, mathematics, history, literature, programming, and analytical reasoning. 

Key principles for your responses:
- Be helpful, harmless, and honest in all interactions
- Provide accurate, well-reasoned answers based on your training
- When uncertain, clearly express your uncertainty rather than guessing
- Break down complex topics into understandable explanations
- Use examples and analogies when helpful for comprehension
- Be concise but thorough - include important details while avoiding unnecessary verbosity
- Maintain a professional but friendly tone
- If asked about controversial topics, present multiple perspectives fairly
- Always prioritize user safety and well-being in your recommendations
- Be transparent about your capabilities and limitations as an AI

For technical questions, provide step-by-step explanations. For creative tasks, offer multiple approaches. For problem-solving, work through the logic systematically."""

    # Simulate a realistic multi-turn conversation
    conversation_turns = [
        "Hello! I'm working on a Python project and need help with data structures.",
        "Can you explain the difference between lists and dictionaries in Python?", 
        "That's helpful! Now, which one should I use for storing user profiles with names and ages?",
        "Perfect! Can you show me how to create a dictionary for this use case?",
        "Great! How would I add a new user to this dictionary?",
        "What if I want to find all users who are over 25 years old?",
        "Excellent! One more question - how do I sort the users by age?",
        "This is very helpful. Can you also show me how to save this data to a file?",
        "Thank you! What's the best way to handle errors when reading the file back?",
        "Perfect! I think I understand now. What are some other data structures I should learn about?"
    ]
    
    print(f"📊 System prompt: {len(system_prompt)} characters")
    print(f"🔄 Conversation turns: {len(conversation_turns)}")
    print()
    
    # Track conversation state
    conversation_history = []
    results = []
    
    # Get initial state
    initial_metrics = requests.get(f"{PROXY_URL}/metrics").json()
    initial_nodes = initial_metrics['trie']['models'].get(MODEL, {'node_count': 0})['node_count']
    initial_requests = initial_metrics['analytics']['total_requests']
    
    print(f"🎯 Starting with {initial_nodes} nodes, {initial_requests} total requests\n")
    
    for turn_num, user_message in enumerate(conversation_turns, 1):
        print(f"💬 Turn {turn_num}: {user_message[:50]}{'...' if len(user_message) > 50 else ''}")
        
        # Build full conversation context (system + all previous turns + current)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        for prev_user, prev_assistant in conversation_history:
            messages.append({"role": "user", "content": prev_user})
            messages.append({"role": "assistant", "content": prev_assistant})
        
        # Add current turn
        messages.append({"role": "user", "content": user_message})
        
        # Get metrics before
        before = requests.get(f"{PROXY_URL}/metrics").json()
        before_nodes = before['trie']['models'].get(MODEL, {'node_count': 0})['node_count']
        before_analytics = before['analytics']
        
        # Send request
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
        latency = (time.time() - start_time) * 1000
        
        # Parse response
        if response.status_code == 200:
            resp_data = response.json()
            assistant_response = resp_data['choices'][0]['message']['content']
            conversation_history.append((user_message, assistant_response))
        else:
            print(f"   ❌ Request failed: {response.status_code}")
            continue
        
        # Wait for analytics to process
        time.sleep(3)
        
        # Get metrics after  
        after = requests.get(f"{PROXY_URL}/metrics").json()
        after_nodes = after['trie']['models'].get(MODEL, {'node_count': 0})['node_count']
        after_analytics = after['analytics']
        
        # Calculate metrics
        new_nodes = after_nodes - before_nodes
        total_tokens_in_conversation = len(' '.join([m['content'] for m in messages])) // 4  # Rough estimate
        
        # Estimate prefix reuse
        if turn_num == 1:
            prefix_reuse_pct = 0  # First turn has no prefix to reuse
        else:
            # Rough estimate: new nodes vs expected tokens
            expected_new_tokens = len(user_message) // 4  # Just the new user message
            prefix_reuse_pct = max(0, (expected_new_tokens - new_nodes) / expected_new_tokens * 100) if expected_new_tokens > 0 else 0
        
        print(f"   📊 New nodes: {new_nodes} (≈{new_nodes*4} tokens)")
        print(f"   📈 Est. prefix reuse: {prefix_reuse_pct:.1f}%")  
        print(f"   ⏱️  Latency: {latency:.0f}ms")
        print(f"   💬 Conv length: ≈{total_tokens_in_conversation} tokens")
        
        results.append({
            'turn': turn_num,
            'new_nodes': new_nodes,
            'latency': latency,
            'conversation_length': total_tokens_in_conversation,
            'prefix_reuse_pct': prefix_reuse_pct
        })
        
        print()
    
    # Final analysis
    print("📈 Conversation Analysis:")
    final_metrics = requests.get(f"{PROXY_URL}/metrics").json()
    final_nodes = final_metrics['trie']['models'].get(MODEL, {'node_count': 0})['node_count']
    final_analytics = final_metrics['analytics']
    
    total_new_nodes = final_nodes - initial_nodes
    total_new_requests = final_analytics['total_requests'] - initial_requests
    
    print(f"   🎯 Total new nodes: {total_new_nodes}")
    print(f"   📊 Total requests: {total_new_requests}")
    print(f"   📈 Current hit rate: {final_analytics['hit_rate']:.1%}")
    print(f"   💾 Token reuse ratio: {final_analytics['token_reuse_ratio']:.1%}")
    print(f"   ⚡ Theoretical savings: {final_analytics['theoretical_compute_savings_pct']:.1f}%")
    
    # Trend analysis
    early_turns = results[:3]
    late_turns = results[-3:]
    
    avg_early_nodes = sum(r['new_nodes'] for r in early_turns) / len(early_turns)
    avg_late_nodes = sum(r['new_nodes'] for r in late_turns) / len(late_turns)
    
    print(f"\n🚀 Caching Efficiency Trend:")
    print(f"   Early conversation (turns 1-3): {avg_early_nodes:.1f} avg new nodes")
    print(f"   Late conversation (turns 8-10): {avg_late_nodes:.1f} avg new nodes")
    print(f"   Improvement: {((avg_early_nodes - avg_late_nodes) / avg_early_nodes * 100):.1f}% fewer new nodes")
    
    if avg_late_nodes < avg_early_nodes * 0.7:
        print(f"   ✅ Strong caching benefits in long conversations!")
    else:
        print(f"   📊 Moderate caching benefits detected.")

if __name__ == "__main__":
    test_long_conversation()