"""
Model name to HuggingFace tokenizer identifier mapping.

This module provides the mapping between model names (as they appear in API requests)
and their corresponding HuggingFace tokenizer identifiers.
"""

from typing import Dict, Optional

# Default mapping from model names to HuggingFace identifiers
DEFAULT_MODEL_MAP: Dict[str, str] = {
    # Llama models
    "llama3": "meta-llama/Meta-Llama-3-8B-Instruct",
    "llama3-8b": "meta-llama/Meta-Llama-3-8B-Instruct", 
    "llama3-70b": "meta-llama/Meta-Llama-3-70B-Instruct",
    "llama32": "meta-llama/Llama-3.2-1B-Instruct",
    "llama3.2-1b": "meta-llama/Llama-3.2-1B-Instruct",
    "llama3.2-3b": "meta-llama/Llama-3.2-3B-Instruct",
    
    # Mistral models  
    "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
    "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.2",
    "mixtral": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    
    # CodeLlama models
    "codellama": "codellama/CodeLlama-7b-Instruct-hf",
    "codellama-7b": "codellama/CodeLlama-7b-Instruct-hf",
    "codellama-13b": "codellama/CodeLlama-13b-Instruct-hf",
    
    # SmolLM models
    "smollm": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "smollm-1.7b": "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    
    # Gemma models
    "gemma": "google/gemma-7b-it",
    "gemma-7b": "google/gemma-7b-it",
    "gemma-2b": "google/gemma-2b-it",
    
    # Qwen models
    "qwen": "Qwen/Qwen2-7B-Instruct",
    "qwen2-7b": "Qwen/Qwen2-7B-Instruct",
    
    # Generic/common aliases
    "gpt-3.5-turbo": "openai-community/gpt2",  # Fallback for OpenAI API compat
    "gpt-4": "openai-community/gpt2",          # Fallback for OpenAI API compat
}


class ModelMapper:
    """
    Maps model names to HuggingFace tokenizer identifiers.
    
    Supports both default built-in mappings and custom user-defined mappings.
    """
    
    def __init__(self, custom_map: Optional[Dict[str, str]] = None):
        """
        Initialize model mapper.
        
        Args:
            custom_map: Optional custom model name mappings. 
                       Overrides default mappings for matching keys.
        """
        self.model_map = DEFAULT_MODEL_MAP.copy()
        
        if custom_map:
            self.model_map.update(custom_map)
    
    def get_tokenizer_id(self, model_name: str) -> str:
        """
        Get HuggingFace tokenizer identifier for a model name.
        
        Args:
            model_name: Model name as it appears in API requests
            
        Returns:
            HuggingFace tokenizer identifier
            
        Raises:
            KeyError: If model name is not found in mapping
        """
        if model_name in self.model_map:
            return self.model_map[model_name]
        
        # Try case-insensitive lookup
        lower_name = model_name.lower()
        for key, value in self.model_map.items():
            if key.lower() == lower_name:
                return value
        
        # Model not found
        available_models = list(self.model_map.keys())
        raise KeyError(
            f"Unknown model '{model_name}'. "
            f"Available models: {', '.join(available_models[:10])}..."
            if len(available_models) > 10 
            else f"Available models: {', '.join(available_models)}"
        )
    
    def add_model(self, model_name: str, tokenizer_id: str) -> None:
        """
        Add or update a model mapping.
        
        Args:
            model_name: Model name as it appears in API requests
            tokenizer_id: HuggingFace tokenizer identifier
        """
        self.model_map[model_name] = tokenizer_id
    
    def remove_model(self, model_name: str) -> None:
        """
        Remove a model mapping.
        
        Args:
            model_name: Model name to remove
            
        Raises:
            KeyError: If model name is not found
        """
        if model_name not in self.model_map:
            raise KeyError(f"Model '{model_name}' not found in mapping")
        
        del self.model_map[model_name]
    
    def get_all_models(self) -> Dict[str, str]:
        """
        Get all model mappings.
        
        Returns:
            Dictionary of model_name -> tokenizer_id mappings
        """
        return self.model_map.copy()
    
    def is_model_supported(self, model_name: str) -> bool:
        """
        Check if a model is supported.
        
        Args:
            model_name: Model name to check
            
        Returns:
            True if model is supported, False otherwise
        """
        return model_name in self.model_map or model_name.lower() in {
            k.lower() for k in self.model_map.keys()
        }


# Default global mapper instance
_default_mapper = ModelMapper()

def get_tokenizer_id(model_name: str) -> str:
    """
    Convenience function to get tokenizer ID using the default mapper.
    
    Args:
        model_name: Model name as it appears in API requests
        
    Returns:
        HuggingFace tokenizer identifier
        
    Raises:
        KeyError: If model name is not found
    """
    return _default_mapper.get_tokenizer_id(model_name)


def is_model_supported(model_name: str) -> bool:
    """
    Convenience function to check if a model is supported.
    
    Args:
        model_name: Model name to check
        
    Returns:
        True if model is supported, False otherwise
    """
    return _default_mapper.is_model_supported(model_name)


def get_all_supported_models() -> Dict[str, str]:
    """
    Get all supported model mappings.
    
    Returns:
        Dictionary of model_name -> tokenizer_id mappings
    """
    return _default_mapper.get_all_models()