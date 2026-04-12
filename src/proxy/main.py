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

from ..tokenizer.pipeline import TokenizerPipeline
from ..trie.manager import TrieManager
from ..analytics.store import AnalyticsStore

app = FastAPI(
    title="KVern - LLM KV Cache Manager",
    description="Transparent proxy for LLM inference with prefix caching optimization",
    version="0.1.0"
)

# Global components (initialized on startup)
tokenizer_pipeline: TokenizerPipeline = None
trie_manager: TrieManager = None
analytics_store: AnalyticsStore = None
backend_client: httpx.AsyncClient = None
config: Dict[str, Any] = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global tokenizer_pipeline, trie_manager, analytics_store, backend_client, config
    
    # Load config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Initialize components
    tokenizer_pipeline = TokenizerPipeline(config["tokenizer"]["model_map"])
    trie_manager = TrieManager(config["trie"])
    analytics_store = AnalyticsStore(config["analytics"]["db_path"])
    
    # Backend HTTP client
    backend_client = httpx.AsyncClient(
        base_url=config["backend"]["url"],
        timeout=config["backend"]["timeout_seconds"]
    )
    
    print(f"KVern proxy started on {config['proxy']['host']}:{config['proxy']['port']}")
    print(f"Backend: {config['backend']['url']}")


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
            # Tokenize prompt
            token_ids = await tokenizer_pipeline.tokenize(model, messages)
            
            # Trie lookup and insert
            hit_info = await trie_manager.lookup(model, token_ids)
            await trie_manager.insert(model, token_ids)
            
            # Record event
            await analytics_store.record_event(
                request_id=request_id,
                model=model, 
                prompt_tokens=len(token_ids),
                shared_prefix_tokens=hit_info.get("match_depth", 0),
                is_hit=hit_info.get("is_hit", False)
            )
        except Exception as e:
            print(f"Trie analytics error (non-blocking): {e}")
    
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
        trie_stats = await trie_manager.get_stats()
        analytics_stats = await analytics_store.get_summary_stats()
        
        return {
            "trie": trie_stats,
            "analytics": analytics_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    # Load config for host/port
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    uvicorn.run(
        "main:app",
        host=config["proxy"]["host"],
        port=config["proxy"]["port"],
        reload=True
    )