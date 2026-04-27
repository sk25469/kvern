"""
KVern FastAPI application entry point.

This module sets up the main FastAPI app that serves as a transparent proxy
for LLM inference requests, tracking prefix reuse via token-level trie.
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import asyncio
import uuid
from typing import Dict, Any
import yaml
import time
import logging

from ..tokenizer.pipeline import TokenizerPipeline
from ..tokenizer.normalizer import Normalizer
from ..trie.manager import KVPrefixManager
from ..trie.prefix_trie import node_count, hot_prefixes
from ..analytics.store import AnalyticsStore
from ..eviction.lru import LRUEvictionPolicy
from ..eviction.cost_aware import CostAwareEvictionPolicy
from ..eviction.lfu_decay import LFUDecayEvictionPolicy
from .middleware import RequestTrackingMiddleware, CORSMiddleware
from ..trie.visualizer import get_hot_prefixes_with_text, format_hot_prefixes_display



app = FastAPI(
    title="KVern - LLM KV Cache Manager",
    description="Transparent proxy for LLM inference with prefix caching optimization",
    version="0.1.0"
)

# Add middleware
app.add_middleware(RequestTrackingMiddleware)
app.add_middleware(CORSMiddleware)

# Global components (initialized on startup)
tokenizer_pipeline: TokenizerPipeline = None
trie_manager: KVPrefixManager = None
analytics_store: AnalyticsStore = None
backend_client: httpx.AsyncClient = None
config: Dict[str, Any] = None
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global tokenizer_pipeline, trie_manager, analytics_store, backend_client, config
    
    # Load config
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")
        raise
    
    # Validate required config sections
    required_sections = ["tokenizer", "trie", "analytics", "backend", "proxy", "eviction"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required config section: {section}")
    
    # Initialize eviction policy
    eviction_policy = None
    policy_name = config["eviction"]["policy"]
    if policy_name == "lru":
        eviction_policy = LRUEvictionPolicy()
    elif policy_name == "cost_aware":
        eviction_policy = CostAwareEvictionPolicy(
            cost_per_token=config["eviction"]["cost_per_token"]
        )
    elif policy_name == "lfu_decay":
        eviction_policy = LFUDecayEvictionPolicy(
            decay_rate=config["eviction"]["decay_rate"]
        )
    else:
        logger.warning(f"Unknown eviction policy '{policy_name}', using LRU")
        eviction_policy = LRUEvictionPolicy()
    
    # Initialize components
    normalizer = Normalizer()
    tokenizer_pipeline = TokenizerPipeline(
        model_map=config["tokenizer"]["model_map"],
        normalizer=normalizer
    )
    trie_manager = KVPrefixManager(
        max_nodes_per_model=config["trie"]["max_nodes_per_model"],
        eviction_policy=eviction_policy
    )
    analytics_store = AnalyticsStore(config["analytics"]["db_path"])
    await analytics_store.initialize()
    
    # Backend HTTP client
    backend_client = httpx.AsyncClient(
        base_url=config["backend"]["url"],
        timeout=config["backend"]["timeout_seconds"]
    )
    
    logger.info(f"KVern proxy started on {config['proxy']['host']}:{config['proxy']['port']}")
    logger.info(f"Backend: {config['backend']['url']}")
    logger.info(f"Eviction policy: {policy_name}")
    logger.info(f"Loaded models: {list(config['tokenizer']['model_map'].keys())}")


@app.on_event("shutdown") 
async def shutdown_event():
    """Cleanup on shutdown."""
    if backend_client:
        await backend_client.aclose()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Transparent proxy for OpenAI-compatible chat completions.
    
    1. Extract model and messages from request
    2. Tokenize and record prefix hits/misses in trie (async)
    3. Forward request to backend unchanged
    4. Return response to client (streaming or complete)
    5. Record analytics post-response
    """
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Parse request body
    body = await request.json()
    model = body.get("model", "unknown")
    messages = body.get("messages", [])
    is_streaming = body.get("stream", False)
    
    # Async trie operations (don't block critical path)
    async def record_trie_analytics():
        try:
            # Tokenize using real TokenizerPipeline
            token_ids = tokenizer_pipeline.tokenize(model, messages)
            
            if token_ids is None:
                # Tokenization failed (unknown model, etc.) - skip trie recording
                logger.warning(f"Skipping trie recording for unknown model: {model}")
                return
            
            # Only process if we meet minimum prefix length requirement
            min_prefix_tokens = config["trie"].get("min_prefix_tokens", 32)
            if len(token_ids) < min_prefix_tokens:
                logger.debug(f"Skipping trie recording - prompt too short: {len(token_ids)} < {min_prefix_tokens}")
                return
            
            # Trie lookup and insert
            match_depth, is_hit = trie_manager.lookup(model, token_ids)
            await trie_manager.insert(model, token_ids)
            
            # Record event in analytics
            await analytics_store.record_event(
                request_id=request_id,
                model=model,
                prompt_tokens=len(token_ids),
                shared_prefix_tokens=match_depth if is_hit else None,
                is_hit=is_hit
            )
            
            logger.debug(
                f"Recorded trie event: model={model}, tokens={len(token_ids)}, "
                f"match_depth={match_depth}, is_hit={is_hit}"
            )
            
        except Exception as e:
            logger.error(f"Trie analytics error (non-blocking): {e}")
    
    # Start analytics task (non-blocking)
    asyncio.create_task(record_trie_analytics())
    
    # Forward request to backend
    try:
        if is_streaming:
            response = await backend_client.post(
                "/v1/chat/completions",
                json=body,
                headers={"Content-Type": "application/json"}
            )
            return StreamingResponse(
                response.iter_bytes(),
                media_type="text/event-stream",
                headers=dict(response.headers)
            )
        else:
            response = await backend_client.post(
                "/v1/chat/completions", 
                json=body,
                headers={"Content-Type": "application/json"}
            )
            
            # Record backend latency
            backend_latency = (time.time() - start_time) * 1000
            asyncio.create_task(
                analytics_store.update_latency(request_id, backend_latency)
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Backend error: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/metrics")  
async def metrics():
    """Expose basic trie metrics."""
    try:
        # Get trie statistics per model
        trie_stats = {
            "total_models": len(trie_manager._roots),
            "models": {}
        }
        
        for model_name, root_node in trie_manager._roots.items():
            trie_stats["models"][model_name] = {
                "node_count": node_count(root_node),
                "hot_prefixes": len(hot_prefixes(root_node, n=10, min_prefix_tokens=32))
            }
        
        # Get analytics statistics
        analytics_stats = await analytics_store.get_summary_stats()
        
        # Get loaded tokenizer models
        loaded_models = tokenizer_pipeline.loaded_models() if tokenizer_pipeline else []
        
        return {
            "trie": trie_stats,
            "analytics": analytics_stats,
            "tokenizer": {
                "loaded_models": loaded_models,
                "configured_models": list(config["tokenizer"]["model_map"].keys())
            },
            "version": "0.1.0"
        }
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")

@app.get("/trie/visualize")
async def visualize_trie():
    """Show hot prefixes as readable text."""
    try:
        result = {}
        
        for model_name, root_node in trie_manager._roots.items():
            # Get tokenizer for this model
            tokenizer = tokenizer_pipeline._registry.get(model_name)
            if tokenizer is None:
                result[model_name] = {"error": "Tokenizer not loaded"}
                continue
            
            # Get hot prefixes with text
            hot_prefixes_data = get_hot_prefixes_with_text(
                root_node, tokenizer, n=10, min_prefix_tokens=32
            )
            
            result[model_name] = {
                "hot_prefixes": hot_prefixes_data,
                "display": format_hot_prefixes_display(hot_prefixes_data)
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visualization error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load config for host/port
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        uvicorn.run(
            "main:app",
            host=config["proxy"]["host"],
            port=config["proxy"]["port"],
            reload=True
        )
    except Exception as e:
        print(f"Failed to start server: {e}")
        exit(1)