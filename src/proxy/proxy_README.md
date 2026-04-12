# proxy

The entry point for all client traffic. KVern's proxy is a **transparent HTTP layer** — clients talk to it exactly as they would to any OpenAI-compatible endpoint. It does not modify requests or responses. Its job is to intercept, observe, and forward.

---

## Responsibilities

- Accept `POST /v1/chat/completions` requests (streaming and non-streaming)
- Assign a `request_id` (UUID) to every incoming request
- Extract `model` and `messages[]` from the request body
- Dispatch to the tokenizer pipeline (async, off critical path)
- Forward the original request unchanged to the configured backend
- Stream or return the backend response to the client unmodified
- Record backend latency post-response to the analytics store

## What it does NOT do

- Modify request payloads
- Block or gate requests based on cache state
- Wait for trie or analytics operations before forwarding
- Handle authentication (out of scope for v1)

---

## Critical design constraint

**Trie and analytics operations must never block the forward path.**

The sequence is:

```
1. Receive request
2. [async, fire-and-forget] → tokenize → trie lookup/insert → analytics write
3. [immediately] → forward to backend
4. Stream response to client
5. [post-response] → record latency
```

Steps 2 and 3 happen concurrently. If the trie or SQLite write takes 20ms, the client sees zero impact. Violating this turns an observability layer into a latency tax.

---

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app, route definitions, lifespan events |
| `middleware.py` | Request interception, `request_id` injection, timing |
| `backend.py` | `httpx` async client, backend forwarding, streaming passthrough |

---

## Key decisions

**Why FastAPI?** Async by default, minimal overhead, native streaming support via `StreamingResponse`. The proxy spends most of its time waiting on network I/O — async is the right model.

**Why `httpx` for backend calls?** `httpx.AsyncClient` supports streaming responses natively, which is required for SSE passthrough. `requests` is synchronous and would block the event loop.

**Streaming handling:** When `stream: true` in the request, the proxy opens a streaming connection to the backend and forwards SSE chunks to the client in real-time. It simultaneously buffers chunk content to extract the completion token count for analytics — this buffering happens in a background task, not in the stream path.

**Fail-open:** If KVern's proxy process crashes or becomes unavailable, the client should be pointed directly at the backend. KVern is never the only path to the model.

---

## Configuration (from `config.yaml`)

```yaml
proxy:
  host: 0.0.0.0
  port: 8080

backend:
  url: http://localhost:11434   # Ollama default; swap for vLLM
  timeout_seconds: 120
```

---

## Running locally

```bash
uvicorn proxy.main:app --host 0.0.0.0 --port 8080 --reload
```

Point any OpenAI-compatible client at `http://localhost:8080` instead of the model backend directly.

---

## Phase roadmap

- **Phase 1:** Transparent proxy with async trie dispatch and analytics recording
- **Phase 2:** Add cache-hit header injection (`X-KVern-Cache-Hit`, `X-KVern-Prefix-Depth`) for observability
- **Phase 3:** Route requests with known-hot prefixes to the replica holding those KV blocks
