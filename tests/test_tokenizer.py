"""
Unit tests for KVern tokenizer pipeline.

Tests model mapping, chat template application, and tokenization
that was validated in the POC notebook.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.tokenizer.pipeline import TokenizerPipeline  
from src.tokenizer.model_map import ModelMapper, get_tokenizer_id
from .fixtures import mock_tokenizer_responses, sample_conversations


class TestModelMapper:
    """Tests for model name to tokenizer ID mapping."""
    
    def test_default_model_map_contains_expected_models(self):
        """Test that default model map contains common models."""
        mapper = ModelMapper()
        
        expected_models = ["llama3", "mistral", "codellama", "gemma"]
        
        for model in expected_models:
            assert mapper.is_model_supported(model)
    
    def test_get_tokenizer_id_valid_model(self):
        """Test getting tokenizer ID for valid model."""
        mapper = ModelMapper()
        
        tokenizer_id = mapper.get_tokenizer_id("llama3")
        assert "llama" in tokenizer_id.lower()
        assert "/" in tokenizer_id  # Should be HuggingFace format
    
    def test_get_tokenizer_id_invalid_model(self):
        """Test error handling for invalid model."""
        mapper = ModelMapper()
        
        with pytest.raises(KeyError, match="Unknown model"):
            mapper.get_tokenizer_id("nonexistent-model")
    
    def test_case_insensitive_model_lookup(self):
        """Test case-insensitive model name lookup."""
        mapper = ModelMapper()
        
        # Should work with different cases
        assert mapper.get_tokenizer_id("llama3") == mapper.get_tokenizer_id("LLAMA3")
    
    def test_custom_model_mapping(self):
        """Test adding custom model mappings."""
        custom_map = {"custom-model": "huggingface/custom-tokenizer"}
        mapper = ModelMapper(custom_map)
        
        assert mapper.is_model_supported("custom-model")
        assert mapper.get_tokenizer_id("custom-model") == "huggingface/custom-tokenizer"
    
    def test_add_model_dynamically(self):
        """Test adding models after initialization."""
        mapper = ModelMapper()
        
        mapper.add_model("new-model", "org/new-tokenizer")
        
        assert mapper.is_model_supported("new-model")
        assert mapper.get_tokenizer_id("new-model") == "org/new-tokenizer"
    
    def test_remove_model(self):
        """Test removing model mappings.""" 
        mapper = ModelMapper()
        original_models = set(mapper.get_all_models().keys())
        
        # Remove a known model
        if "llama3" in original_models:
            mapper.remove_model("llama3")
            assert not mapper.is_model_supported("llama3")
    
    def test_convenience_functions(self):
        """Test global convenience functions."""
        # Should not raise errors for known models
        tokenizer_id = get_tokenizer_id("llama3")
        assert isinstance(tokenizer_id, str)
        
        assert is_model_supported("llama3") == True
        assert is_model_supported("nonexistent") == False


class TestTokenizerPipeline:
    """Tests for the main tokenizer pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_model_map = {
            "test-llama": "meta-llama/Llama-3.2-1B-Instruct",
            "test-mistral": "mistralai/Mistral-7B-Instruct-v0.2"
        }
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_pipeline_initialization(self, mock_auto_tokenizer):
        """Test pipeline initialization with model map.""" 
        pipeline = TokenizerPipeline(self.test_model_map)
        
        assert pipeline.model_map == self.test_model_map
        assert pipeline._registry == {}  # Should start empty
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')  
    def test_tokenizer_loading_and_caching(self, mock_auto_tokenizer):
        """Test tokenizer loading and registry caching."""
        mock_tokenizer = Mock()
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        # First call should load tokenizer
        result1 = pipeline._get_or_load("test-llama")
        mock_auto_tokenizer.from_pretrained.assert_called_once_with(
            "meta-llama/Llama-3.2-1B-Instruct"
        )
        
        # Second call should use cached version
        result2 = pipeline._get_or_load("test-llama")
        assert mock_auto_tokenizer.from_pretrained.call_count == 1  # Not called again
        assert result1 is result2  # Same object returned
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_unsupported_model_error(self, mock_auto_tokenizer):
        """Test error handling for unsupported models."""
        pipeline = TokenizerPipeline(self.test_model_map)
        
        with pytest.raises(KeyError, match="Unknown model"):
            pipeline._get_or_load("unsupported-model")
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_tokenize_method_flow(self, mock_auto_tokenizer):
        """Test the main tokenize method flow."""
        # Mock tokenizer behavior
        mock_tokenizer = Mock()
        mock_tokenizer.apply_chat_template.return_value = "templated text"
        mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        messages = [
            {"role": "user", "content": "Hello"}
        ]
        
        result = pipeline.tokenize("test-llama", messages)
        
        # Verify the flow
        mock_tokenizer.apply_chat_template.assert_called_once_with(
            messages, tokenize=False, add_generation_prompt=True
        )
        mock_tokenizer.encode.assert_called_once_with("templated text")
        
        assert result == [1, 2, 3, 4, 5]
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_chat_template_parameters(self, mock_auto_tokenizer):
        """Test that chat template is called with correct parameters."""
        mock_tokenizer = Mock()
        mock_tokenizer.apply_chat_template.return_value = "templated"
        mock_tokenizer.encode.return_value = [1, 2, 3]
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        messages = [{"role": "user", "content": "test"}]
        pipeline.tokenize("test-llama", messages)
        
        # Verify chat template call
        mock_tokenizer.apply_chat_template.assert_called_once_with(
            messages, 
            tokenize=False,  # Critical: should be False to get string
            add_generation_prompt=True  # Should add generation prompt
        )
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_async_tokenize_method(self, mock_auto_tokenizer):
        """Test async tokenize method."""
        mock_tokenizer = Mock()
        mock_tokenizer.apply_chat_template.return_value = "async test"
        mock_tokenizer.encode.return_value = [10, 20, 30]
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        messages = [{"role": "user", "content": "async test"}]
        
        # Test async version
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                pipeline.tokenize_async("test-llama", messages)
            )
            assert result == [10, 20, 30]
        finally:
            loop.close()
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_error_handling_tokenizer_loading(self, mock_auto_tokenizer):
        """Test error handling when tokenizer fails to load."""
        mock_auto_tokenizer.from_pretrained.side_effect = Exception("Network error")
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        with pytest.raises(Exception, match="Network error"):
            pipeline.tokenize("test-llama", [])
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')  
    def test_multiple_models_isolation(self, mock_auto_tokenizer):
        """Test that multiple models are handled correctly and cached separately."""
        mock_llama_tokenizer = Mock()
        mock_mistral_tokenizer = Mock()
        
        # Set up different responses for different models
        def mock_from_pretrained(model_id):
            if "llama" in model_id.lower():
                return mock_llama_tokenizer
            elif "mistral" in model_id.lower():
                return mock_mistral_tokenizer
            else:
                raise ValueError(f"Unknown model: {model_id}")
        
        mock_auto_tokenizer.from_pretrained.side_effect = mock_from_pretrained
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        # Load both tokenizers
        llama_tok = pipeline._get_or_load("test-llama")
        mistral_tok = pipeline._get_or_load("test-mistral")
        
        # Should be different objects
        assert llama_tok is not mistral_tok
        
        # Should be cached
        assert len(pipeline._registry) == 2
        assert pipeline._registry["test-llama"] is mock_llama_tokenizer
        assert pipeline._registry["test-mistral"] is mock_mistral_tokenizer


class TestTokenizerIntegration:
    """Integration tests with actual conversation data."""
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_realistic_conversation_tokenization(self, mock_auto_tokenizer):
        """Test tokenization of realistic conversation structures."""
        mock_tokenizer = Mock()
        
        # Mock responses for different conversation types
        def mock_apply_template(messages, **kwargs):
            if len(messages) == 1:
                return "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\nHello<|eot_id|>"
            elif len(messages) == 2:
                return "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are helpful.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\nHi<|eot_id|>"
            else:
                return "complex conversation template"
        
        def mock_encode(text):
            # Return different length sequences based on text complexity
            return list(range(len(text) // 10 + 1, len(text) // 5 + 10))
        
        mock_tokenizer.apply_chat_template.side_effect = mock_apply_template
        mock_tokenizer.encode.side_effect = mock_encode
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        
        pipeline = TokenizerPipeline({"test-model": "test/tokenizer"})
        
        # Test different conversation types
        conversations = [
            # Simple user message
            [{"role": "user", "content": "Hello"}],
            
            # System + user
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"}
            ],
            
            # Multi-turn conversation  
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is Python?"},
                {"role": "assistant", "content": "Python is a programming language."},
                {"role": "user", "content": "Can you show me code?"}
            ]
        ]
        
        for messages in conversations:
            result = pipeline.tokenize("test-model", messages)
            
            # Basic validation
            assert isinstance(result, list)
            assert len(result) > 0
            assert all(isinstance(token_id, int) for token_id in result)
    
    def test_tokenization_consistency(self, mock_tokenizer_responses):
        """Test that identical inputs produce identical outputs."""
        with patch('src.tokenizer.pipeline.AutoTokenizer') as mock_auto:
            mock_tokenizer = Mock()
            mock_auto.from_pretrained.return_value = mock_tokenizer
            
            # Set up consistent responses
            mock_tokenizer.apply_chat_template.return_value = "consistent template"
            mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]
            
            pipeline = TokenizerPipeline({"test": "test/model"})
            
            messages = [{"role": "user", "content": "test message"}]
            
            # Multiple calls should produce identical results
            result1 = pipeline.tokenize("test", messages)
            result2 = pipeline.tokenize("test", messages)
            
            assert result1 == result2
    
    def test_empty_messages_handling(self):
        """Test handling of edge cases like empty messages."""
        with patch('src.tokenizer.pipeline.AutoTokenizer') as mock_auto:
            mock_tokenizer = Mock()
            mock_tokenizer.apply_chat_template.return_value = ""
            mock_tokenizer.encode.return_value = []
            mock_auto.from_pretrained.return_value = mock_tokenizer
            
            pipeline = TokenizerPipeline({"test": "test/model"})
            
            # Test empty messages list
            result = pipeline.tokenize("test", [])
            assert result == []
            
            # Test messages with empty content
            empty_messages = [{"role": "user", "content": ""}]
            result = pipeline.tokenize("test", empty_messages)
            assert isinstance(result, list)


class TestTokenizerPerformance:
    """Performance tests for tokenizer operations."""
    
    @patch('src.tokenizer.pipeline.AutoTokenizer')
    def test_tokenizer_caching_performance(self, mock_auto_tokenizer):
        """Test that tokenizer caching improves performance."""
        mock_tokenizer = Mock()
        mock_tokenizer.apply_chat_template.return_value = "test"
        mock_tokenizer.encode.return_value = [1, 2, 3]
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        
        pipeline = TokenizerPipeline({"test": "test/model"})
        
        messages = [{"role": "user", "content": "test"}]
        
        # First call loads the tokenizer
        pipeline.tokenize("test", messages)
        initial_call_count = mock_auto_tokenizer.from_pretrained.call_count
        
        # Subsequent calls should use cached tokenizer
        for _ in range(10):
            pipeline.tokenize("test", messages)
        
        # Should not have called from_pretrained again
        assert mock_auto_tokenizer.from_pretrained.call_count == initial_call_count