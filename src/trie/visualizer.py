"""
Trie visualization utilities for KVern.
Phase 1: Hot prefix text visualization.
"""

from typing import List, Tuple, Optional
from collections import deque

from .prefix_trie import hot_prefixes
from .node import TrieNode


def reconstruct_token_path(root: TrieNode, target_node: TrieNode) -> Optional[List[int]]:
    """
    Reconstruct the token sequence from root to target_node.
    Returns the list of token IDs forming the path, or None if not found.
    """
    # BFS to find the path to target_node
    queue = deque([(root, [])])  # (node, path_so_far)
    
    while queue:
        current_node, path = queue.popleft()
        
        # If we found the target, return the path
        if current_node is target_node:
            return path
            
        # Explore children
        for token_id, child_node in current_node.children.items():
            queue.append((child_node, path + [token_id]))
    
    return None


def get_hot_prefixes_with_text(root: TrieNode, tokenizer, n: int = 10, min_prefix_tokens: int = 20) -> List[dict]:
    """
    Get hot prefixes decoded as readable text.
    
    Returns diverse and interesting cached content, focusing on complete conversations.
    """
    # Get many candidates to filter from
    hot_nodes = hot_prefixes(root, n * 5, min_prefix_tokens)
    
    results = []
    seen_patterns = set()  
    
    for node in hot_nodes:
        token_path = reconstruct_token_path(root, node)
        if token_path is None:
            continue
            
        try:
            decoded_text = tokenizer.decode(token_path)
            cleaned_text = ' '.join(decoded_text.split())
            
            # Extract meaningful content
            meaningful_part = extract_meaningful_content(cleaned_text)
            if not meaningful_part or len(meaningful_part) < 25:
                continue
            
            # Skip if this looks like incomplete incremental content
            if not is_complete_meaningful_content(meaningful_part):
                continue
                
            # Create a similarity key for deduplication 
            similarity_key = create_similarity_key(meaningful_part)
            if similarity_key in seen_patterns:
                continue
            seen_patterns.add(similarity_key)
            
            # Format for display
            if len(meaningful_part) > 100:
                display_text = meaningful_part[:50] + " ... " + meaningful_part[-50:]
            else:
                display_text = meaningful_part
            
            results.append({
                'text': display_text,
                'depth': node.token_depth,
                'count': node.count,
                'truncated': len(meaningful_part) > 100,
                'full_text': cleaned_text,
                'meaningful_content': meaningful_part
            })
            
        except Exception as e:
            continue  # Skip decode errors for cleaner output
    
    # Sort by hit count and limit results
    results.sort(key=lambda x: x['count'], reverse=True)
    return results[:n]


def is_complete_meaningful_content(text: str) -> bool:
    """Check if content represents a complete, meaningful cached unit."""
    text = text.strip()
    
    # Skip very short content
    if len(text) < 15:
        return False
    
    # Skip obvious incomplete incremental content
    if text.endswith(' user') or text.endswith('.user'):
        return False
        
    # Include properly formatted system/user content
    if text.startswith("System:") or text.startswith("User:"):
        content_part = text.split(":", 1)[1].strip() if ":" in text else text
        # Must have reasonable content after the label
        if len(content_part) > 10:
            return True
    
    # Include complete sentences 
    if text.endswith('.') or text.endswith('?') or text.endswith('!'):
        return True
    
    # Include meaningful questions and prompts
    meaningful_patterns = [
        'what is', 'how to', 'how do', 'why', 'explain', 'you are',
        'write a', 'make', 'help with', 'show me', 'tell me'
    ]
    if any(pattern in text.lower() for pattern in meaningful_patterns):
        return True
        
    # Include anything substantial (but not ending with common incomplete words)
    incomplete_endings = ['user', 'system', 'how', 'what', 'the', 'a', 'and']
    last_word = text.split()[-1].lower() if text.split() else ''
    
    if len(text) > 25 and last_word not in incomplete_endings:
        return True
        
    return False


def create_similarity_key(text: str) -> str:
    """Create a key for detecting similar content patterns."""
    # For formatted content, use the actual content part
    if "System:" in text or "User:" in text:
        # Extract the main content after the label
        if " | " in text:
            parts = text.split(" | ")
            return parts[-1][:30].lower()  # Use user part
        elif "User:" in text:
            return text.split("User:", 1)[1][:30].lower()
        elif "System:" in text:
            return text.split("System:", 1)[1][:30].lower()
    
    # For other content, use first few words
    words = text.split()
    if len(words) >= 4:
        return ' '.join(words[:4]).lower()
    return text[:25].lower()


def extract_meaningful_content(text: str) -> str:
    """Extract human-readable content from chat template text."""
    
    # Remove common chat template markers
    text = text.replace('<|begin_of_text|>', '')
    text = text.replace('<|start_header_id|>', '')
    text = text.replace('<|end_header_id|>', '')
    text = text.replace('<|eot_id|>', '')
    
    # Remove knowledge cutoff boilerplate
    if "Cutting Knowledge Date:" in text:
        parts = text.split("Cutting Knowledge Date:")
        if len(parts) > 1:
            text = parts[1]
    
    # Remove date stamps  
    import re
    text = re.sub(r'December \d{4}', '', text)
    text = re.sub(r'Today Date: \d+ \w+ \d+', '', text)
    
    # Clean up whitespace
    text = ' '.join(text.split())
    
    # Parse out system and user content properly
    if "system" in text.lower() and "user" in text.lower():
        # Split on role transitions
        if " user " in text:
            parts = text.split(" user ", 1)
            system_part = parts[0].strip()
            user_part = parts[1].strip() if len(parts) > 1 else ""
            
            # Format nicely
            result = ""
            if "You are" in system_part:
                result += f"System: {system_part}"
            if user_part and len(user_part) > 3:
                if result:
                    result += " | "
                result += f"User: {user_part}"
            return result
    
    # Single role content
    if "You are" in text and len(text) > 10:
        return f"System: {text.strip()}"
    elif any(word in text.lower() for word in ['what', 'how', 'why', 'explain', 'help', 'python', 'code', 'tell', 'show']):
        return f"User: {text.strip()}"
    elif len(text.strip()) > 15:
        return text.strip()
    
    return ""


def format_hot_prefixes_display(hot_prefixes_data: List[dict]) -> str:
    """Format hot prefixes for console/text display."""
    if not hot_prefixes_data:
        return "🔥 No hot prefixes found\n"
    
    output = ["🔥 Hot Prefixes (Most Frequently Cached):\n"]
    
    for i, prefix in enumerate(hot_prefixes_data, 1):
        count = prefix['count']
        depth = prefix['depth'] 
        text = prefix['text']
        truncated = prefix.get('truncated', False)
        
        line = f"{i:2d}. \"{text}\""
        if truncated:
            line += " ..."
        line += f" (depth: {depth}, hits: {count})"
        
        output.append(line)
    
    return "\n".join(output) + "\n"