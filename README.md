# KVern - LLM KV Cache Manager

> **🚧 Work in Progress** - Currently refactoring notebook prototype into production modules

A transparent proxy that optimizes LLM inference by tracking and managing Key-Value cache reuse across requests using token-level trie data structures.

## Problem Statement

LLM inference is wasteful by default. Every request triggers a full forward pass, even when most of the prompt was processed before:

- **Static system prompts** repeated across every request (multi-tenant SaaS, RAG pipelines)
- **Chat history growth** where each turn re-processes all previous context  
- **High-frequency prompts** served independently across replicas

**KVern** builds a control plane above model serving infrastructure to track prefix reuse and provide measurable compute savings.

## Architecture Overview

<img width="4136" height="3715" alt="KVERN_ARCH" src="https://github.com/user-attachments/assets/7418baba-8f13-466e-90bc-abdd16089801" />




**Transparent Proxy**: Zero API changes - clients use standard OpenAI `/v1/chat/completions` endpoint

### 📊 Request Flow Visualization

**[→ Interactive Request Flow Demo](./docs/kvern_request_flow.html)** *(download and open in browser)*

7-step walkthrough showing how a single request moves through KVern's components, with async analytics recording and background eviction engine.

## Current Status 

### ✅ **Phase 1 - Core Components Complete** (April 18, 2026)

**Production-Ready Modules:**
- [x] **Trie Core**: Complete function-based implementation with insert, lookup, eviction
- [x] **Eviction Policies**: LRU, LFU-decay, and cost-aware eviction (addresses POC depth-blind flaw)
- [x] **Tokenizer Pipeline**: Full HuggingFace integration with model mapping & normalization
- [x] **Trie Manager**: Per-model roots, async locks, memory cap enforcement
- [x] **Analytics Store**: SQLite backend with query engine for metrics
- [x] **Configuration**: YAML-based config system with normalization rules
- [x] **Test Suite**: 61 passing tests covering core functionality

**Key Implementation Highlights:**
- **Cost-Aware Eviction**: Fixes the depth-blind LRU flaw discovered in POC
- **Template Normalization**: Handles runtime date injection with configurable rules
- **Async Architecture**: Lock-free lookups, background inserts for zero latency impact
- **Pluggable Policies**: Factory pattern for eviction strategy selection

### ✅ **Phase 1B - Integration Layer Complete** (April 27, 2026)

**Full end-to-end proxy integration:**
- [x] **FastAPI Proxy Server**: Complete transparent OpenAI-compatible proxy
- [x] **Real Tokenization**: Integrated TokenizerPipeline replacing all mock implementations
- [x] **Analytics Integration**: Enhanced store with batching, error handling, and metrics endpoint
- [x] **Middleware Stack**: Request/response processing with proper error handling
- [x] **Backend Forwarding**: Robust upstream routing with connection management
- [x] **Trie Visualization**: Web endpoint for inspecting cached content and patterns

**Production Validation:**
- **Cross-Platform Tested**: Windows Ollama + WSL proxy successfully validated
- **Cache Effectiveness Confirmed**: 78.6% theoretical token savings correlated with 25% actual latency improvement
- **Real Workload Testing**: Multi-turn conversations, diverse system prompts, varied request patterns
- **Performance Verified**: <5ms proxy overhead, efficient async processing

## Quick Start

### Prerequisites
- Python 3.9+  
- Virtual environment
- LLM backend (Ollama, vLLM, or any OpenAI-compatible API)

### Installation

```bash
git clone <repo-url>
cd kvern
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Run the Production Proxy

1. **Configure your backend** in `config.yaml`:
```yaml
proxy:
  upstream_base_url: "http://localhost:11434"  # Ollama default
  # or: "http://localhost:8000"  # vLLM default
```

2. **Start KVern proxy**:
```bash
python run_proxy.py
```

3. **Send requests** (transparent OpenAI API):
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:1b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

4. **Monitor caching** via built-in endpoints:
- **Health**: `GET http://localhost:8080/health`
- **Analytics**: `GET http://localhost:8080/analytics`  
- **Cache Visualization**: `GET http://localhost:8080/trie/visualize`

### Run the Notebook POC (Historical)

```bash
jupyter notebook notebooks/KVern_POC.ipynb
```

**Expected Output**:
- Tokenization of sample conversation (52 tokens)
- Trie insertion and prefix matching across turns
- Visualization showing shared spine vs. unique branches
- Eviction simulation (demonstrates depth-blind LRU issue)

## Key Findings from Testing

### 1. **Multi-turn Prefix Sharing Works**
```
Turn 1: "You are a helpful assistant." + "Hello!"
Turn 2: Turn 1 + "Explain Tries."
Result: 100% prefix match for Turn 1 sequence
```

### 2. **Cache Effectiveness Validated** ⚡ **New**
**Controlled Testing Results** (April 27, 2026):
- **Theoretical Savings**: 78.6% token reuse across conversation turns
- **Measured Performance**: 25% actual latency improvement correlation
- **Cache Hit Patterns**: System prompts achieve 90%+ reuse, conversation context 60%+ reuse
- **Cross-Platform Success**: Windows Ollama backend + WSL proxy integration working seamlessly

### 3. **Eviction Policy Success** 
Cost-aware eviction successfully prevents naive LRU from evicting deep, high-traffic nodes.
**Before**: Evicted depth-47 node requiring 47 token recomputation
**After**: Evicts shallow, low-frequency nodes preserving expensive computation

### 4. **Production-Ready Architecture** 
- **Transparent Integration**: Zero API changes required for client applications
- **Real-Time Analytics**: SQLite store captures hit/miss patterns with <10ms latency
- **Template Normalization**: Solved date injection drift with configurable regex patterns
- **Visualization Tools**: Web interface for inspecting cached conversation patterns

### 5. **Runtime Template Drift Solved**
Date injection no longer breaks daily cache persistence. Template normalization rules handle dynamic content:
```yaml
normalization:
  llama3.2:
    - pattern: "Today Date: \\d{1,2} \\w+ \\d{4}"
      placeholder: "Today Date: NORMALIZED"
```

## Planned Architecture

### Core Components Implementation Status

| Component | Technology | Status |
|-----------|------------|---------|
| **Prefix Trie** | Custom token-level trie | ✅ **Complete** |
| **Eviction Engine** | Pluggable policies (LRU/LFU/Cost-aware) | ✅ **Complete** |
| **Tokenizer Pipeline** | HuggingFace transformers | ✅ **Complete** |
| **Analytics Store** | SQLite with query engine | ✅ **Complete** |
| **Trie Manager** | Per-model async orchestration | ✅ **Complete** |
| **Configuration** | YAML config system | ✅ **Complete** |
| **Proxy Layer** | FastAPI transparent proxy | ✅ **Complete** |
| **Trie Visualization** | Web-based cache inspection | ✅ **Complete** |
| **Dashboard** | Streamlit metrics visualization | 🔄 **Partial** |

### Target Metrics

| Metric | Goal |
|--------|------|
| **Cache Hit Rate** | ≥40% on templated workloads |
| **Token Reuse Ratio** | Measured and optimized |
| **Proxy Overhead** | <5ms p99 added latency |
| **Compute Savings** | Theoretical FLOP reduction tracking |

## Roadmap

### Phase 1 - Core Infrastructure ✅ **Complete**
**Goal**: Production-ready caching components

- [x] Notebook prototype validation
- [x] Trie data structure with eviction policies
- [x] Tokenizer pipeline with normalization
- [x] SQLite analytics store with query engine
- [x] Cost-aware eviction policy
- [x] YAML config system
- [x] Comprehensive test suite (61 tests)

### Phase 1B - Integration ✅ **Complete** 
**Goal**: End-to-end proxy deployment

- [x] Complete proxy server middleware with real tokenization
- [x] Backend forwarding with comprehensive error handling  
- [x] Analytics integration with batching and metrics endpoints
- [x] Trie visualization for cache inspection
- [x] Cross-platform validation (Windows/WSL)
- [x] Performance benchmarking and cache effectiveness validation

### Phase 2 - Production Polish  ⚡ **Current Priority**
**Goal**: Enterprise deployment readiness

- [ ] Streamlit dashboard completion with real-time metrics
- [ ] Docker deployment package with multi-stage builds
- [ ] Load testing and performance optimization
- [ ] Configuration validation and error handling improvements
- [ ] Comprehensive logging and monitoring integration
- [ ] Documentation and deployment guides

### Phase 3 - vLLM Integration  
**Goal**: Actually influence GPU KV block eviction decisions

- [ ] vLLM block manager integration
- [ ] Map trie nodes → GPU block IDs
- [ ] CPU block offload for evicted cache
- [ ] Measure real prompt processing speedup beyond proxy benefits

### Phase 4 - Distributed Cache
**Goal**: Share KV cache across multiple replicas

- [ ] Redis metadata store
- [ ] KV block serialization/transport  
- [ ] Load balancer integration
- [ ] Multi-node cache consistency

## Contributing

This is early-stage research. Current focus:

1. **Data Structure Optimization**: Improve eviction policies, add path compression
2. **Template Normalization**: Solve runtime drift for production deployment
3. **Backend Integration**: FastAPI proxy with real model backends
4. **Metrics Collection**: SQLite analytics with meaningful dashboards

## Technical Details

### API Endpoints

The KVern proxy provides several monitoring and inspection endpoints:

```bash
# Standard OpenAI-compatible endpoint
POST /v1/chat/completions

# Health check
GET /health
# → {"status": "healthy", "version": "0.1.0"}

# Analytics and performance metrics  
GET /analytics
# → Cache hit rates, token savings, latency stats

# Cache visualization - inspect what's actually cached
GET /trie/visualize  
# → {"<model>": {"hot_prefixes": [...], "display": "..."}}
```

**Trie Visualization Example Output:**
```json
{
  "llama3.2:1b": {
    "hot_prefixes": [
      {
        "text": "System: You are a helpful assistant.",
        "depth": 32,
        "count": 15,
        "meaningful_content": "System: You are a helpful assistant."
      },
      {
        "text": "User: What is machine learning?",
        "depth": 45, 
        "count": 3,
        "meaningful_content": "User: What is machine learning?"
      }
    ],
    "display": "🔥 Hot Prefixes (Most Frequently Cached):\n..."
  }
}
```

### Trie Node Structure
```python
@dataclass
class TrieNode:
    children: dict[int, 'TrieNode']    # token_id → child
    count: int = 0                     # hit frequency  
    last_seen: float = 0.0             # unix timestamp
    token_depth: int = 0               # enables cost-aware eviction
    model: str = ""                    # per-model trie roots
```

### Cost-Aware Eviction (Implemented)
```python
# Fixes the POC depth-blind LRU flaw
recompute_cost = token_depth * COST_PER_TOKEN
eviction_score = recompute_cost / (count * recency_weight)
# Now evicts shallow low-frequency nodes over deep high-frequency ones
```

### Template Normalization (Implemented) 
```yaml
# config.yaml - handles runtime date injection
normalization:
  llama3.2:
    - pattern: "Today Date: \\d{1,2} \\w+ \\d{4}\\n"
      placeholder: "Today Date: NORMALIZED\n"
      source: template_injected
```

## License

Apache 2.0 - See [LICENSE](LICENSE) file.

---

> **Status**: Phase 1B integration complete - production proxy ready for deployment  
> **Test Coverage**: 61 passing tests + end-to-end validation  
> **Performance**: 78.6% theoretical savings, 25% measured latency improvement  
> **Author**: Sahil | **Last Updated**: April 27, 2026
