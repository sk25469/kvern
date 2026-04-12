# tokenizer

Converts raw `messages[]` arrays into token ID sequences that the trie can operate on. This is not optional plumbing — **it is the correctness boundary of the entire system**. If tokenization is wrong, trie paths diverge for prompts that are semantically identical, and the cache is useless.

---

## Responsibilities

- Map model names (as they appear in API requests) to HuggingFace tokenizer identifiers
- Load and cache tokenizer instances per model (loaded once, reused across requests)
- Apply the model's **chat template** to serialize `messages[]` into a flat string
- Tokenize the flat string into `token_ids: list[int]`
- Return token IDs to the proxy for trie dispatch

---

## Why token IDs, not strings

The trie keys on token IDs — not raw text. Two reasons:

**1. Model-specific token spaces.** The same string tokenizes differently across models. `"Hello"` might be token `9906` in LLaMA 3 and `15496` in Mistral. Mixing string-keyed paths in one trie would produce incorrect prefix matches across models.

**2. Chat template application.** The model does not see `"You are a helpful assistant. User: Hello."` — it sees a tokenized sequence that includes role markers, separators, and special tokens defined by the chat template. The trie must match on what the model actually processes, not on the raw message content.

---

## Chat template

Every instruct-tuned model defines a Jinja2 chat template in its `tokenizer_config.json`. This template specifies how `[{role, content}]` maps to a flat string with role tokens and separators.

Example — LLaMA 3:
```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are helpful.<|eot_id|><|start_header_id|>user<|end_header_id|>

Hello<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```

Two conversations with identical content but different whitespace or role casing will produce different strings — and different token IDs — if the template is not applied consistently. The tokenizer pipeline applies the template via `tokenizer.apply_chat_template()` before tokenizing.

---

## Files

| File | Purpose |
|---|---|
| `pipeline.py` | Main pipeline class — template application, tokenization, instance caching |
| `model_map.py` | Config-driven map: model name → HuggingFace tokenizer identifier |

---

## Model map

Defined in `config.yaml` and loaded into `model_map.py` at startup:

```yaml
tokenizer:
  model_map:
    llama3:   meta-llama/Meta-Llama-3-8B-Instruct
    mistral:  mistralai/Mistral-7B-Instruct-v0.2
    qwen2:    Qwen/Qwen2-7B-Instruct
```

If a model name in a request is not found in the map, the tokenizer raises a `ModelNotSupportedError` and the proxy logs it — the request is still forwarded to the backend, but trie dispatch is skipped for that request.

---

## Instance caching

Tokenizers are expensive to load (~200ms for a full HuggingFace tokenizer with sentencepiece). They are loaded once per model on first request and stored in a module-level registry:

```python
_registry: dict[str, PreTrainedTokenizer] = {}
```

Loading is protected by a per-model `asyncio.Lock` to prevent thundering herd on cold start.

---

## Key gotcha: tokenizer version drift

The same model with different tokenizer versions can produce different token IDs for the same string. This silently breaks trie path matching. Mitigate by:

- Pinning tokenizer versions in `requirements.txt` (e.g. `transformers==4.40.0`)
- Storing the tokenizer version string alongside trie metadata (future: for cache invalidation)

This is tracked as open question Q2 in `DESIGN.md`.

---

## Configuration (from `config.yaml`)

```yaml
tokenizer:
  model_map:
    llama3: meta-llama/Meta-Llama-3-8B-Instruct
    # add models as needed
```

---

## Testing

The tokenizer pipeline can be tested entirely without a running model or GPU. Unit tests should cover:

- Correct chat template application per model (compare output against HuggingFace reference)
- Token ID determinism (same input → same IDs across multiple calls)
- Model map miss handling (`ModelNotSupportedError`)
- Tokenizer instance reuse (second call for same model does not reload)

See `tests/test_tokenizer.py`.

---

## Phase roadmap

- **Phase 1:** HuggingFace tokenizers, chat template application, model map, instance caching
- **Phase 2:** Tokenizer version pinning and drift detection
- **Phase 3:** No changes expected — tokenizer is stable infrastructure
