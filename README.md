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

```
Client Request ──┐
(OpenAI API)     │   ┌─────────────────────────────────┐
                 └──►│          KV Cache Manager        │
                     │  ┌─────────┐  ┌──────────────┐   │
                     │  │  Proxy  │  │  Tokenizer   │   │
                     │  │FastAPI  │  │  Pipeline    │   │
                     │  └─────────┘  └──────────────┘   │
                     │       │              │           │
                     │       │       ┌──────▼────────┐  │
                     │       │       │  Prefix Trie  │  │
                     │       │       │ (token-level) │  │
                     │       │       └───────────────┘  │
                     │       │                          │
                     │       └──────────────────────────┼──┐
                     └──────────────────────────────────┘  │
                                                           ▼
                                                 ┌─────────────────┐
                                                 │  vLLM / Ollama  │
                                                 │ (model backend) │
                                                 └─────────────────┘
```

**Transparent Proxy**: Zero API changes - clients use standard OpenAI `/v1/chat/completions` endpoint

### 📊 Request Flow Visualization

**[→ Interactive Request Flow Demo](./docs/kvern_request_flow.html)** *(download and open in browser)*

7-step walkthrough showing how a single request moves through KVern's components, with async analytics recording and background eviction engine.

## Current Status 

### ✅ **Phase 1 - Notebook Prototype Complete** (April 12, 2026)

**Validated Core Concepts:**
- [x] **Tokenizer Pipeline**: `messages[]` → chat template → token IDs (52 tokens for test case)
- [x] **MiniTrie Implementation**: Insert, lookup, prefix sharing across conversation turns
- [x] **Multi-turn Validation**: Correctly identifies shared token sequences (100% prefix match in test)
- [x] **Trie Visualization**: Tree structure shows hot paths vs. unique branches
- [x] **Basic Eviction**: Leaf-node LRU (with identified depth-blindness flaw)

**Key Discovery - Runtime Template Drift:**
```
Llama 3.2 system prefix: "Today Date: 12 Apr 2026"
```
**Problem**: Token sequence changes daily, invalidating cache every 24 hours.
**Impact**: Need normalization strategy before trie insertion.

### 🔄 **Next - Production Implementation**

Refactoring notebook POC into modular source files:

```
src/
├── main.py (entry point)
├── proxy/server.py (FastAPI transparent proxy) 
├── tokenizer/pipeline.py (HuggingFace tokenization)
└── trie/
    ├── node.py (TrieNode with token_depth, timestamps)
    └── manager.py (per-model roots, async locks)
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

### Core Components (DESIGN.md §4)

| Component | Technology | Status |
|-----------|------------|---------|
| **Proxy Layer** | FastAPI | 🔄 Next |
| **Tokenizer Pipeline** | HuggingFace transformers | ✅ Validated |
| **Prefix Trie** | Custom token-level trie | ✅ POC done |
| **Analytics Store** | SQLite | 🔄 Next |
| **Eviction Engine** | Pluggable policies (LRU/LFU/Cost-aware) | 🔄 Next |
| **Dashboard** | Streamlit | 🔄 Next |

### Target Metrics

| Metric | Goal |
|--------|------|
| **Cache Hit Rate** | ≥40% on templated workloads |
| **Token Reuse Ratio** | Measured and optimized |
| **Proxy Overhead** | <5ms p99 added latency |
| **Compute Savings** | Theoretical FLOP reduction tracking |

## Roadmap

### Phase 1 - Observability (Current)
**Goal**: Measure prefix reuse without GPU dependency

- [x] Notebook prototype validation
- [ ] FastAPI transparent proxy  
- [ ] SQLite analytics store
- [ ] Streamlit dashboard
- [ ] Cost-aware eviction policy
- [ ] Config system (YAML)

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

### Cost-Aware Eviction
```python
recompute_cost = token_depth * COST_PER_TOKEN
eviction_score = recompute_cost / (count * recency_weight)
# Evict high recompute cost + low reuse frequency
```

## License

Apache 2.0 - See [LICENSE](LICENSE) file.

---

> **Status**: Prototype validated, moving to production implementation.  
> **Author**: Sahil | **Last Updated**: April 12, 2026