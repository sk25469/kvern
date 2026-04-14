# Tokenizer Pipeline — Design Notes

> **Author:** Sahil  
> **Last Updated:** April 2026  
> **Status:** Pre-implementation — design validated via notebook

---

## What This Component Does

The tokenizer pipeline sits between the proxy and the trie. Its job is deceptively simple:

```
messages[] → token_ids[]
```

But the details matter enormously. Get this wrong and your trie keys on phantom prefixes that don't correspond to real KV reuse. The trie is only as correct as what you feed it.

---

## The Core Pipeline

```
messages[]
    ↓
apply_chat_template()       ← model-specific Jinja2 template
    ↓
normalize(model)            ← strip dynamic injections (see below)
    ↓
tokenizer.encode()          ← string → token IDs
    ↓
token_ids[]                 ← what the trie operates on
```

The normalization step is the non-obvious one. Everything else is standard HuggingFace.

---

## Why Normalization Exists — The Template Injection Problem

Every model has a Jinja2 chat template stored in `tokenizer_config.json`. When you call `apply_chat_template()`, this template wraps your messages in model-specific boilerplate before tokenization.

The problem: **some of that boilerplate is dynamic**. It changes per-request or per-day, even when the client sends identical messages. This silently invalidates your cache.

We audited the Llama 3.2 template directly (see `notebooks/llama32_template_analysis.ipynb`) to understand exactly what gets injected.

---

## Llama 3.2 Template Audit — Findings

### Raw template variables

The Llama 3.2 chat template references these variables:

```
add_generation_prompt    ← controls assistant header at end
bos_token                ← always <|begin_of_text|>, fixed per model
custom_tools             ← client can override tool definitions
date_string              ← TODAY'S DATE — changes daily
first_user_message       ← extracted when tools are injected into user message
messages                 ← the conversation (expected)
raise_exception          ← utility function, not content
strftime_now             ← runtime function that generates date_string
system_message           ← extracted from messages[0]
tool_call                ← extracted from assistant tool_calls
tools                    ← tool definitions array
tools_in_user_message    ← controls WHERE tools get injected
```

### Rendered structure (no tools)

Every Llama 3.2 request renders to this structure:

```
<|begin_of_text|>
<|start_header_id|>system<|end_header_id|>\n\n
Cutting Knowledge Date: December 2023\n     ← STATIC, hardcoded in template
Today Date: {date_string}\n\n               ← DYNAMIC, changes daily
{system_message}                            ← your actual content
<|eot_id|>
<|start_header_id|>user<|end_header_id|>\n\n
{user_message}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>\n\n
```

### Token-level breakdown (validated)

For a minimal conversation (47 tokens total):

```
Pos 0-15:   STABLE    bos + system header + "Cutting Knowledge Date: December 2023\n"
Pos 16-19:  STABLE    "Today Date: "
Pos 20-24:  DYNAMIC   "14 Apr 2026"  ← diverges here when date changes
Pos 25-46:  STRANDED  your system message + user message + assistant header
```

Key finding: **the day token at pos 20 changes daily**. Everything after it — including your entire system message — is stranded and uncacheable, even though it's perfectly static content.

### Cache impact (measured)

```
Without normalization:
  Stable prefix:  20 / 47 tokens = 42.6%
  Resets:         every day at midnight, silently

With normalization:
  Stable prefix:  47 / 47 tokens = 100%
  Resets:         only when system prompt actually changes
```

In production with a 1000-token system prompt:

```
Stable prefix without normalization:  ~20 tokens  (the boilerplate before the date)
Stable prefix with normalization:     ~1020 tokens (everything)
Daily cache loss without fix:         ~1000 tokens stranded every 24h
```

The longer your system prompt, the worse the damage from date injection.

### Tools injection (validated)

When tools are present, the template injects `"Environment: ipython\n"` before `"Cutting Knowledge Date"`:

```
Pos 6: diverges immediately
  Without tools: 'Cut'           (start of "Cutting Knowledge Date")
  With tools:    'Environment'   (start of "Environment: ipython")
```

Stable prefix drops from 20 tokens to **6 tokens** when tools are present vs absent.

However, tools are a **deployment-level config**, not a request-level variable. Every request from a given deployment uses the same tool definitions. Within a deployment, tool variation is zero — the trie path is consistent and you get full prefix reuse. Cross-deployment tool differences are correct cache misses — different tool sets mean genuinely different token sequences.

---

## Variable Classification

Not all dynamic variables are equal. Three categories:

### 1. Unintentional dynamic injection (normalize these)

Variables that change even when the client sends identical content. These are cache killers.

```
date_string / strftime_now    ← changes daily
                                 pos 20 in Llama 3.2
                                 silent cold start every 24h
```

### 2. Intentional structural variation (let trie diverge naturally)

Variables that change because the client deliberately sent different content. These are correct cache misses.

```
messages                      ← conversation content changed, should miss
tools / custom_tools          ← different tools = different token structure
system_message                ← extracted from messages[0], client-controlled
```

### 3. Structural flags (deployment-level, effectively static)

Variables that change the shape of the output but are set once per deployment, not per request.

```
tools_in_user_message         ← controls WHERE tools land (default: true)
add_generation_prompt         ← controls assistant header (default: true)
```

---

## Normalization Strategy

### Approach: string-level, pre-tokenization, per-model config

Normalize the rendered string **after** `apply_chat_template()` but **before** `encode()`. Replace dynamic segments with fixed placeholders so the token sequence is stable across days.

```python
# Pipeline with normalization
text = tokenizer.apply_chat_template(messages, tokenize=False)
text = normalizer.normalize(model, text)       # ← new step
token_ids = tokenizer.encode(text)
```

The actual request forwarded to the backend is **never touched**. Normalization only affects the trie key, not inference.

### Why string-level, not token-level

You could strip dynamic tokens after encoding instead. But the result is identical — the placeholder string tokenizes to the same fixed IDs either way. String-level is simpler, easier to debug, and keeps the pipeline linear.

### Phase 1: Manual normalization profiles

Automated profile generation (parsing Jinja2 AST, rendering with varied inputs, finding divergence points) is non-trivial and out of scope for Phase 1. We validated the process manually in the notebook.

Phase 1 ships with hand-curated profiles for the models we actually test against.

```yaml
# config.yaml
normalization:
  llama3.2:
    - pattern: "Today Date: \\d{1,2} \\w+ \\d{4}\\n"
      placeholder: "Today Date: NORMALIZED\n"
      source: template_injected
      validated: true
      notes: "Injected by strftime_now at token pos 20. Changes daily."
```

Unknown models get a passthrough — no normalization, conservative behavior.

### Phase 2: Automated profile generation

The notebook (`notebooks/llama32_template_analysis.ipynb`) codifies the manual process:

1. Pull raw Jinja2 template via `tokenizer.chat_template`
2. Parse AST with `jinja2.meta.find_undeclared_variables()`
3. Render with varied inputs (different dates, tools, flags)
4. Find divergence points via token-sequence diff
5. Output normalization profile

This becomes a script that runs once per model and emits a config entry.

---

## Open Questions

**Q1 — Tokenizer version pinning**
Same model, different tokenizer version → different token IDs for identical strings. Trie paths diverge silently. Need to pin tokenizer version in config and detect mismatches at startup.

**Q2 — Normalization correctness vs model behavior**
The normalized token sequence (with placeholder) is what the trie keys on, not what the model sees. The model still gets the real date. This is intentional — the trie key only needs to be stable and consistent, not identical to what the model processes.

**Q3 — Other models**
We only audited Llama 3.2. Mistral, Qwen, Gemma all have different templates with potentially different dynamic injections. Phase 1 is Llama 3.2 only. Each new model needs its own notebook audit before adding a normalization profile.

**Q4 — Tools injection position**
If tools are present, the stable prefix shrinks to 6 tokens. This means tool-enabled deployments get almost no prefix reuse on the system header. The conversation history (which grows across turns) becomes the primary cache value. Worth measuring in Phase 1 traffic.

---

## What This Validates from DESIGN.md

| Design Decision | Validation Status |
|---|---|
| Token IDs as trie keys, not strings (§8) | ✅ Confirmed — same string tokenizes differently across models |
| Chat template application before tokenizing (§8) | ✅ Confirmed — model processes templated sequence |
| Per-model trie roots (§4.3) | ✅ Confirmed — token ID spaces are model-specific |
| Min prefix depth threshold (§4.3) | ✅ Confirmed — short shared prefixes (< 32 tokens) are noise |
| Normalization layer | 🆕 New — not in original design, added based on template audit |

---

## Files

```
tokenizer/
├── pipeline.py          ← main pipeline: messages → token_ids
├── normalizer.py        ← per-model normalization, reads from config
└── model_map.py         ← model name → HuggingFace identifier

notebooks/
└── llama32_template_analysis.ipynb   ← audit notebook, ground truth for this doc
```
