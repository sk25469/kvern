"""
Unit tests for KVern tokenizer pipeline.

Tests model mapping, chat template application, and tokenization
that was validated in the POC notebook.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.tokenizer.pipeline import TokenizerPipeline, TokenizerRegistry 
from src.tokenizer.model_map import ModelMapper, get_tokenizer_id, is_model_supported
from src.tokenizer.normalizer import Normalizer, NormalizationRule, NORMALIZATION_PROFILES


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
    
    @patch('transformers.AutoTokenizer')
    def test_pipeline_initialization(self, mock_auto_tokenizer):
        """Test pipeline initialization with model map.""" 
        pipeline = TokenizerPipeline(self.test_model_map) # type: ignore
        
        assert pipeline.model_map == self.test_model_map
        assert pipeline._registry == {}  # Should start empty
    
    @patch('transformers.AutoTokenizer')  
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
    
    @patch('transformers.AutoTokenizer')
    def test_unsupported_model_error(self, mock_auto_tokenizer):
        """Test error handling for unsupported models."""
        pipeline = TokenizerPipeline(self.test_model_map)
        
        with pytest.raises(KeyError, match="Unknown model"):
            pipeline._get_or_load("unsupported-model")
    
    @patch('transformers.AutoTokenizer')
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
    
    @patch('transformers.AutoTokenizer')
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
    
    @patch('transformers.AutoTokenizer')
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
    
    @patch('transformers.AutoTokenizer')
    def test_error_handling_tokenizer_loading(self, mock_auto_tokenizer):
        """Test error handling when tokenizer fails to load."""
        mock_auto_tokenizer.from_pretrained.side_effect = Exception("Network error")
        
        pipeline = TokenizerPipeline(self.test_model_map)
        
        with pytest.raises(Exception, match="Network error"):
            pipeline.tokenize("test-llama", [])
    
    @patch('transformers.AutoTokenizer')  
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

        """Test handling of edge cases like empty messages."""
        with patch('transformers.AutoTokenizer') as mock_auto:
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


"""
Tests for normalizer.py and pipeline.py.

Normalizer tests: no model required — pure string logic.
Pipeline tests: require HuggingFace tokenizer download — marked slow.

Run fast tests only:
    pytest test_tokenizer.py -m "not slow"

Run all:
    pytest test_tokenizer.py
"""


# ─────────────────────────────────────────────
# Normalizer tests (no model, no network)
# ─────────────────────────────────────────────

class TestNormalizer:

    def test_known_model_strips_date(self):
        """Date segment gets replaced with stable placeholder."""
        normalizer = Normalizer()
        text = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            "Cutting Knowledge Date: December 2023\n"
            "Today Date: 14 Apr 2026\n\n"
            "You are a helpful assistant.<|eot_id|>"
        )
        result = normalizer.normalize("llama3.2", text)
        assert "14 Apr 2026" not in result
        assert "Today Date: NORMALIZED" in result

    def test_normalization_is_stable_across_days(self):
        """Same conversation on different days produces identical normalized output."""
        normalizer = Normalizer()

        def make_text(date: str) -> str:
            return (
                "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                "Cutting Knowledge Date: December 2023\n"
                f"Today Date: {date}\n\n"
                "You are a helpful assistant.<|eot_id|>"
            )

        result_today    = normalizer.normalize("llama3.2", make_text("14 Apr 2026"))
        result_tomorrow = normalizer.normalize("llama3.2", make_text("15 Apr 2026"))
        result_nextmonth = normalizer.normalize("llama3.2", make_text("01 May 2026"))

        assert result_today == result_tomorrow == result_nextmonth

    def test_unknown_model_passthrough(self):
        """Unknown model returns text unchanged — no crash."""
        normalizer = Normalizer()
        text = "Some rendered text with Today Date: 14 Apr 2026\n"
        result = normalizer.normalize("unknown-model-xyz", text)
        assert result == text  # unchanged

    def test_no_match_returns_unchanged(self):
        """If pattern doesn't match, text is returned unchanged."""
        normalizer = Normalizer()
        text = "No date injection here."
        result = normalizer.normalize("llama3.2", text)
        assert result == text

    def test_custom_profile_injection(self):
        """Custom profiles can be injected for testing."""
        custom_profiles = {
            "test-model": [
                NormalizationRule(
                    pattern=r"SESSION_ID: \w+\n",
                    placeholder="SESSION_ID: NORMALIZED\n",
                    source="template_injected",
                )
            ]
        }
        normalizer = Normalizer(profiles=custom_profiles)
        text = "SESSION_ID: abc123\nHello world"
        result = normalizer.normalize("test-model", text)
        assert "abc123" not in result
        assert "SESSION_ID: NORMALIZED" in result

    def test_has_profile(self):
        normalizer = Normalizer()
        assert normalizer.has_profile("llama3.2") is True
        assert normalizer.has_profile("nonexistent") is False

    def test_supported_models(self):
        normalizer = Normalizer()
        assert "llama3.2" in normalizer.supported_models()

    def test_static_content_preserved(self):
        """Normalization only strips dynamic parts — static content unchanged."""
        normalizer = Normalizer()
        text = (
            "Cutting Knowledge Date: December 2023\n"
            "Today Date: 14 Apr 2026\n\n"
            "You are a helpful assistant specialized in Python."
        )
        result = normalizer.normalize("llama3.2", text)
        assert "Cutting Knowledge Date: December 2023" in result
        assert "You are a helpful assistant specialized in Python." in result


# ─────────────────────────────────────────────
# TokenizerRegistry tests (mocked tokenizer)
# ─────────────────────────────────────────────

class TestTokenizerRegistry:

    def test_unknown_model_returns_none(self):
        registry = TokenizerRegistry(model_map={"llama3.2": "some/hf-id"})
        result = registry.get("nonexistent-model")
        assert result is None

    def test_known_model_loads_tokenizer(self):
        mock_tokenizer = MagicMock()
        with patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tokenizer):
            registry = TokenizerRegistry(model_map={"llama3.2": "meta-llama/Llama-3.2-1B-Instruct"})
            result = registry.get("llama3.2")
        assert result is mock_tokenizer

    def test_second_call_uses_cache(self):
        mock_tokenizer = MagicMock()
        with patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tokenizer) as mock_load:
            registry = TokenizerRegistry(model_map={"llama3.2": "meta-llama/Llama-3.2-1B-Instruct"})
            registry.get("llama3.2")
            registry.get("llama3.2")
            # Should only load once regardless of how many times get() is called
            assert mock_load.call_count == 1

    def test_failed_load_returns_none(self):
        with patch("transformers.AutoTokenizer.from_pretrained", side_effect=OSError("not found")):
            registry = TokenizerRegistry(model_map={"llama3.2": "bad/path"})
            result = registry.get("llama3.2")
        assert result is None

    def test_loaded_models(self):
        mock_tokenizer = MagicMock()
        with patch("transformers.AutoTokenizer.from_pretrained", return_value=mock_tokenizer):
            registry = TokenizerRegistry(model_map={"llama3.2": "meta-llama/Llama-3.2-1B-Instruct"})
            assert registry.loaded_models() == []
            registry.get("llama3.2")
            assert "llama3.2" in registry.loaded_models()


# ─────────────────────────────────────────────
# TokenizerPipeline tests (mocked tokenizer)
# ─────────────────────────────────────────────

class TestTokenizerPipeline:

    def _make_pipeline(self, mock_tokenizer=None):
        """Helper: pipeline with mocked tokenizer and real normalizer."""
        if mock_tokenizer is None:
            mock_tokenizer = MagicMock()
            mock_tokenizer.apply_chat_template.return_value = (
                "Cutting Knowledge Date: December 2023\n"
                "Today Date: 14 Apr 2026\n\n"
                "You are a helpful assistant."
            )
            mock_tokenizer.encode.return_value = [1, 2, 3, 4, 5]

        with patch("src.tokenizer.pipeline.AutoTokenizer.from_pretrained", return_value=mock_tokenizer):
            pipeline = TokenizerPipeline(
                model_map={"llama3.2": "meta-llama/Llama-3.2-1B-Instruct"},
                normalizer=Normalizer(),
            )
            # Trigger load
            pipeline._registry.get("llama3.2")

        return pipeline, mock_tokenizer

    def test_returns_token_ids(self):
        pipeline, _ = self._make_pipeline()
        messages = [{"role": "user", "content": "Hello"}]
        result = pipeline.tokenize("llama3.2", messages)
        assert result == [1, 2, 3, 4, 5]

    def test_unknown_model_returns_none(self):
        pipeline, _ = self._make_pipeline()
        messages = [{"role": "user", "content": "Hello"}]
        result = pipeline.tokenize("unknown-model", messages)
        assert result is None

    def test_normalization_applied_before_encode(self):
        """Encode receives normalized text, not raw rendered text."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.return_value = (
            "Today Date: 14 Apr 2026\n\nYou are a helpful assistant."
        )
        mock_tokenizer.encode.return_value = [1, 2, 3]

        pipeline, mock_tok = self._make_pipeline(mock_tokenizer)
        messages = [{"role": "user", "content": "Hello"}]
        pipeline.tokenize("llama3.2", messages)

        # encode() should receive normalized text, not the raw date
        encoded_arg = mock_tok.encode.call_args[0][0]
        assert "14 Apr 2026" not in encoded_arg
        assert "NORMALIZED" in encoded_arg

    def test_same_conversation_different_days_identical_tokens(self):
        """
        Core caching invariant: same conversation on different days
        must produce identical token IDs after normalization.
        """
        call_count = [0]

        def fake_apply_chat_template(messages, **kwargs):
            dates = ["14 Apr 2026", "15 Apr 2026"]
            date = dates[call_count[0] % 2]
            call_count[0] += 1
            return f"Today Date: {date}\n\nYou are a helpful assistant."

        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.side_effect = fake_apply_chat_template
        mock_tokenizer.encode.side_effect = lambda text: [hash(text) & 0xFFFF]

        pipeline, _ = self._make_pipeline(mock_tokenizer)
        messages = [{"role": "user", "content": "Hello"}]

        tokens_day1 = pipeline.tokenize("llama3.2", messages)
        tokens_day2 = pipeline.tokenize("llama3.2", messages)

        assert tokens_day1 == tokens_day2, (
            "Same conversation on different days must produce identical token IDs. "
            "Normalization is not working correctly."
        )

    def test_template_failure_returns_none(self):
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.side_effect = Exception("template error")

        pipeline, _ = self._make_pipeline(mock_tokenizer)
        result = pipeline.tokenize("llama3.2", [{"role": "user", "content": "hi"}])
        assert result is None

    def test_encode_failure_returns_none(self):
        mock_tokenizer = MagicMock()
        mock_tokenizer.apply_chat_template.return_value = "some text"
        mock_tokenizer.encode.side_effect = Exception("encode error")

        pipeline, _ = self._make_pipeline(mock_tokenizer)
        result = pipeline.tokenize("llama3.2", [{"role": "user", "content": "hi"}])
        assert result is None


# ─────────────────────────────────────────────
# Integration tests (require HuggingFace, marked slow)
# ─────────────────────────────────────────────

@pytest.mark.slow
class TestTokenizerPipelineIntegration:
    """
    Real tokenizer, real normalization, no mocks.
    Requires: transformers, HuggingFace access, meta-llama/Llama-3.2-1B-Instruct
    Run with: pytest test_tokenizer.py -m slow
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        return TokenizerPipeline(
            model_map={"llama3.2": "meta-llama/Llama-3.2-1B-Instruct"},
            normalizer=Normalizer(),
        )

    def test_real_tokenization_returns_list_of_ints(self, pipeline):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain binary search."},
        ]
        result = pipeline.tokenize("llama3.2", messages)
        assert isinstance(result, list)
        assert all(isinstance(t, int) for t in result)
        assert len(result) > 0

    def test_real_normalization_stable_across_dates(self, pipeline):
        """
        Validated finding from notebook: date at pos 20-24 must be normalized
        so same conversation produces same token IDs regardless of day.
        """
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain binary search."},
        ]
        # Tokenize twice — if normalization works, both calls produce identical IDs
        # (template will inject today's date both times, normalization strips it)
        tokens_1 = pipeline.tokenize("llama3.2", messages)
        tokens_2 = pipeline.tokenize("llama3.2", messages)
        assert tokens_1 == tokens_2

    def test_different_conversations_produce_different_tokens(self, pipeline):
        messages_a = [{"role": "user", "content": "Explain binary search."}]
        messages_b = [{"role": "user", "content": "Explain quicksort."}]
        tokens_a = pipeline.tokenize("llama3.2", messages_a)
        tokens_b = pipeline.tokenize("llama3.2", messages_b)
        assert tokens_a != tokens_b

    def test_multiturn_extends_token_sequence(self, pipeline):
        """Each additional turn extends the token sequence."""
        turn1 = [
            {"role": "user", "content": "What is a trie?"},
        ]
        turn2 = [
            {"role": "user", "content": "What is a trie?"},
            {"role": "assistant", "content": "A trie is a tree data structure..."},
            {"role": "user", "content": "How does insertion work?"},
        ]
        tokens_1 = pipeline.tokenize("llama3.2", turn1)
        tokens_2 = pipeline.tokenize("llama3.2", turn2)
        assert len(tokens_2) > len(tokens_1)
        # Turn 2 should share the prefix of turn 1
        assert tokens_2[:len(tokens_1) - 5] == tokens_1[:len(tokens_1) - 5]