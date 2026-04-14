"""
normalizer.py

Strips dynamic template injections from rendered chat strings before tokenization.
Operates on the rendered string AFTER apply_chat_template(), BEFORE encode().

The normalized string is only used as a trie cache key — it is never forwarded
to the backend. The model always receives the original, unmodified request.
"""

import re
import logging
import yaml
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NormalizationRule:
    """
    A single normalization rule for a dynamic segment.

    pattern:     regex matching the dynamic content in the rendered string
    placeholder: stable string to replace it with
    source:      where the injection comes from (for documentation/debugging)
    """
    pattern: str
    placeholder: str
    source: str  # "template_injected" | "client_provided"


@dataclass
class NormalizationRule:
    """
    A single normalization rule for a dynamic segment.

    pattern:     regex matching the dynamic content in the rendered string
    placeholder: stable string to replace it with
    source:      where the injection comes from (for documentation/debugging)
    """
    pattern: str
    placeholder: str
    source: str  # "template_injected" | "client_provided"


def load_normalization_profiles() -> dict[str, list[NormalizationRule]]:
    """
    Load normalization profiles from config.yaml.
    
    Returns a dict mapping model names to lists of NormalizationRule objects.
    Falls back to empty dict if config is not found or invalid.
    """
    try:
        # Look for config.yaml in project root (relative to this file)
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        normalization_config = config.get("normalization", {})
        profiles = {}
        
        for model, rules in normalization_config.items():
            if not isinstance(rules, list):
                logger.warning(f"Invalid rules format for model '{model}', skipping")
                continue
                
            normalized_rules = []
            for rule_dict in rules:
                try:
                    rule = NormalizationRule(
                        pattern=rule_dict["pattern"],
                        placeholder=rule_dict["placeholder"],
                        source=rule_dict["source"]
                    )
                    normalized_rules.append(rule)
                except (KeyError, TypeError) as e:
                    logger.warning(f"Invalid rule format for model '{model}': {e}")
                    continue
            
            if normalized_rules:
                profiles[model] = normalized_rules
                logger.debug(f"Loaded {len(normalized_rules)} normalization rules for model '{model}'")
        
        return profiles
        
    except FileNotFoundError:
        logger.warning("config.yaml not found, using empty normalization profiles")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"Error parsing config.yaml: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading normalization profiles: {e}")
        return {}


# Load normalization profiles from config.yaml at module import time
# This is cached for the lifetime of the process - if config changes, restart is needed
NORMALIZATION_PROFILES = load_normalization_profiles()


class Normalizer:
    """
    Applies per-model normalization rules to a rendered chat string.

    Rules are loaded from config.yaml by default, but can be overridden for testing.

    Usage:
        normalizer = Normalizer()
        normalized_text = normalizer.normalize("llama3.2", rendered_text)
        token_ids = tokenizer.encode(normalized_text)
    """

    def __init__(self, profiles: dict[str, list[NormalizationRule]] | None = None):
        # Allow injecting custom profiles for testing, otherwise use config-loaded profiles
        self._profiles = profiles if profiles is not None else NORMALIZATION_PROFILES

    def normalize(self, model: str, text: str) -> str:
        """
        Apply all normalization rules for the given model.

        If no profile exists for the model, returns text unchanged.
        Unknown models are a passthrough — we can't cache them optimally
        but we don't break them either.
        """
        rules = self._profiles.get(model)

        if not rules:
            if model not in self._profiles:
                logger.debug(
                    "No normalization profile for model '%s'. "
                    "Passing through unchanged — cache hit rate may be suboptimal.",
                    model
                )
            return text

        normalized = text
        for rule in rules:
            before = normalized
            normalized = re.sub(rule.pattern, rule.placeholder, normalized)
            if normalized != before:
                logger.debug(
                    "Normalized dynamic segment [%s] in model '%s'",
                    rule.source, model
                )

        return normalized

    def has_profile(self, model: str) -> bool:
        """Whether a normalization profile exists for this model."""
        return model in self._profiles

    def supported_models(self) -> list[str]:
        """Models with validated normalization profiles."""
        return list(self._profiles.keys())