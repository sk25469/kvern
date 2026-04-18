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

### 🔄 **Phase 1B - Integration Layer** (In Progress)

Main proxy server integration:

```
src/
├── proxy/
│   ├── main.py (FastAPI app - partial)
│   ├── middleware.py (request/response handling)
│   └── backend.py (upstream forwarding)
└── dashboard/
    └── app.py (Streamlit metrics dashboard)
```

## Quick Start

### Prerequisites
- Python 3.9+  
- Virtual environment
- (Optional) Ollama or vLLM backend for testing

### Installation

```bash
git clone <repo-url>
cd kvern
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Run the Notebook POC

```bash
jupyter notebook notebooks/KVern_POC.ipynb
```

**Expected Output**:
- Tokenization of sample conversation (52 tokens)
- Trie insertion and prefix matching across turns
- Visualization showing shared spine vs. unique branches
- Eviction simulation (demonstrates depth-blind LRU issue)

## Key Findings from POC

### 1. **Multi-turn Prefix Sharing Works**
```
Turn 1: "You are a helpful assistant." + "Hello!"
Turn 2: Turn 1 + "Explain Tries."
Result: 100% prefix match for Turn 1 sequence
```

### 2. **Eviction Policy Needs Improvement** 
Current naive LRU evicted a high-traffic node at depth 47, requiring recomputation of 47 tokens.
**Solution**: Cost-aware eviction using `recompute_cost = token_depth * count`.

### 3. **Runtime Template Drift Challenge**
Date injection breaks daily cache persistence. Requires template normalization before trie operations.

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
| **Proxy Layer** | FastAPI transparent proxy | 🔄 **Partial** |
| **Dashboard** | Streamlit metrics visualization | 🔄 **Partial** |

### Target Metrics

| Metric | Goal |
|--------|------|
| **Cache Hit Rate** | ≥40% on templated workloads |
| **Token Reuse Ratio** | Measured and optimized |
| **Proxy Overhead** | <5ms p99 added latency |
| **Compute Savings** | Theoretical FLOP reduction tracking |

## Roadmap

### Phase 1 - Core Infrastructure ✅ **95% Complete**
**Goal**: Production-ready caching components

- [x] Notebook prototype validation
- [x] Trie data structure with eviction policies
- [x] Tokenizer pipeline with normalization
- [x] SQLite analytics store with query engine
- [x] Cost-aware eviction policy
- [x] YAML config system
- [x] Comprehensive test suite (61 tests)
- [ ] FastAPI proxy server integration (80% done)
- [ ] Streamlit dashboard completion

### Phase 1B - Integration ⚡ **Current**
**Goal**: End-to-end proxy deployment

- [ ] Complete proxy server middleware
- [ ] Backend forwarding with error handling
- [ ] Dashboard real-time metrics
- [ ] Docker deployment package
- [ ] Performance benchmarking

### Phase 2 - vLLM Integration  
**Goal**: Actually influence GPU KV block eviction decisions

- [ ] vLLM block manager integration
- [ ] Map trie nodes → GPU block IDs
- [ ] CPU block offload for evicted cache
- [ ] Measure real prompt processing speedup

### Phase 3 - Distributed Cache
**Goal**: Share KV cache across multiple replicas

- [ ] Redis metadata store
- [ ] KV block serialization/transport  
- [ ] Load balancer integration

## Contributing

This is early-stage research. Current focus:

1. **Data Structure Optimization**: Improve eviction policies, add path compression
2. **Template Normalization**: Solve runtime drift for production deployment
3. **Backend Integration**: FastAPI proxy with real model backends
4. **Metrics Collection**: SQLite analytics with meaningful dashboards

## Technical Details

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

> **Status**: Core components complete, integrating proxy server.  
> **Test Coverage**: 61 passing tests  
> **Author**: Sahil | **Last Updated**: April 18, 2026
