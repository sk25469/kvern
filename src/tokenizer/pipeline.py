"""
pipeline.py

Converts messages[] → token_ids[] for trie insertion.

Pipeline:
    messages[]
        → apply_chat_template()   (model-specific Jinja2 template)
        → normalize()             (strip dynamic injections)
        → encode()                (string → token IDs)
        → token_ids[]

The token_ids produced here are used exclusively as trie cache keys.
They are never forwarded to the backend — the original request is always
passed through unmodified.
"""

import logging
from dataclasses import dataclass, field

from transformers import AutoTokenizer, PreTrainedTokenizerBase

from .normalizer import Normalizer

logger = logging.getLogger(__name__)


@dataclass
class TokenizerRegistry:
    """
    Lazy-loading registry of tokenizers keyed by model name.

    Phase 1: lazy load on first request per model.
    Phase 2: eager load for high-traffic models at startup
             based on analytics (most-seen models in last 24h).
    """
    model_map: dict[str, str]                           # model_name → hf_id
    _cache: dict[str, PreTrainedTokenizerBase] = field(
        default_factory=dict, init=False
    )

    def get(self, model: str) -> PreTrainedTokenizerBase | None:
        """
        Return tokenizer for model, loading it if not yet cached.
        Returns None if model is not in the model map.

        NOTE: Not thread-safe in v1. Two concurrent requests for the same
        unknown model may both trigger a load. This is benign — the second
        load overwrites the first with an identical tokenizer. Fix in v2
        with an asyncio.Lock per model name.
        """
        if model in self._cache:
            return self._cache[model]

        hf_id = self.model_map.get(model)
        if not hf_id:
            logger.warning(
                "Model '%s' not in model map. "
                "Cannot tokenize — trie will not record this request.",
                model
            )
            return None

        logger.info("Loading tokenizer for model '%s' (hf_id: %s)", model, hf_id)
        try:
            tokenizer = AutoTokenizer.from_pretrained(hf_id)
            self._cache[model] = tokenizer
            logger.info("Tokenizer loaded for model '%s'", model)
            return tokenizer
        except Exception as e:
            logger.error(
                "Failed to load tokenizer for model '%s' (hf_id: %s): %s",
                model, hf_id, e
            )
            return None

    def preload(self, models: list[str]) -> None:
        """
        Eagerly load tokenizers for a list of model names.
        Called at startup for high-traffic models.
        Phase 2 feature — wired up here but not called in Phase 1.
        """
        for model in models:
            if model not in self._cache:
                self.get(model)

    def loaded_models(self) -> list[str]:
        """Currently loaded models."""
        return list(self._cache.keys())


class TokenizerPipeline:
    """
    Converts messages[] → token_ids[] for trie insertion.

    Takes a Normalizer as a dependency for testability —
    normalization and tokenization can be tested independently.

    Usage:
        pipeline = TokenizerPipeline(
            model_map={"llama3.2": "meta-llama/Llama-3.2-1B-Instruct"},
            normalizer=Normalizer()
        )
        token_ids = pipeline.tokenize("llama3.2", messages)
        if token_ids is None:
            # Unknown model or tokenizer load failed — skip trie recording
            ...
    """

    def __init__(
        self,
        model_map: dict[str, str],
        normalizer: Normalizer,
    ):
        self._registry = TokenizerRegistry(model_map)
        self._normalizer = normalizer

    def tokenize(
        self,
        model: str,
        messages: list[dict],
        add_generation_prompt: bool = True,
    ) -> list[int] | None:
        """
        Full pipeline: messages → normalized rendered string → token IDs.

        Returns None if the model is unknown or tokenizer load fails.
        Callers treat None as "skip trie recording for this request."

        Args:
            model:                  model name as it appears in the API request
            messages:               list of {role, content} dicts
            add_generation_prompt:  whether to append assistant header
                                    (should match what the backend receives)
        """
        tokenizer = self._registry.get(model)
        if tokenizer is None:
            return None

        # Step 1: Apply chat template → rendered string
        # This is what the model actually processes (minus normalization).
        try:
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=add_generation_prompt,
            )
        except Exception as e:
            logger.error(
                "Chat template application failed for model '%s': %s",
                model, e
            )
            return None

        # Step 2: Normalize dynamic injections
        # Replaces dynamic segments (e.g. today's date) with stable placeholders.
        # The normalized string is the trie key — never forwarded to backend.
        normalized = self._normalizer.normalize(model, rendered)

        # Step 3: Encode → token IDs
        try:
            token_ids: list[int] = tokenizer.encode(normalized)
        except Exception as e:
            logger.error(
                "Tokenization failed for model '%s': %s",
                model, e
            )
            return None

        logger.debug(
            "Tokenized model='%s' messages=%d tokens=%d",
            model, len(messages), len(token_ids)
        )
        return token_ids

    def preload(self, models: list[str]) -> None:
        """Eagerly load tokenizers. Phase 2 entry point."""
        self._registry.preload(models)

    def loaded_models(self) -> list[str]:
        """Currently loaded tokenizers."""
        return self._registry.loaded_models()