"""Tests for model registry and known models."""

import pytest
from gpu_session.models import (
    KNOWN_MODELS,
    MODEL_INFO,
    get_model_config,
    get_model_gpu_mapping,
    Quantization,
)


class TestKnownModelsValid:
    """Test that all known models have valid configurations."""

    def test_all_models_have_name(self):
        """Every model should have a non-empty name."""
        for model_id, config in KNOWN_MODELS.items():
            assert config.name, f"Model {model_id} has empty name"
            assert isinstance(config.name, str)
            assert len(config.name) > 0

    def test_all_models_have_hf_path(self):
        """Every model should have a valid HuggingFace path."""
        for model_id, config in KNOWN_MODELS.items():
            assert config.hf_path, f"Model {model_id} has empty hf_path"
            assert isinstance(config.hf_path, str)
            # HF paths should have format "org/model"
            assert "/" in config.hf_path, f"Model {model_id} has invalid HF path format"

    def test_all_models_have_positive_params(self):
        """Every model should have positive parameter count."""
        for model_id, config in KNOWN_MODELS.items():
            assert config.params_billions > 0, f"Model {model_id} has invalid params"
            assert isinstance(config.params_billions, (int, float))

    def test_all_models_have_valid_quantization(self):
        """Every model should have valid quantization."""
        for model_id, config in KNOWN_MODELS.items():
            assert isinstance(config.default_quantization, Quantization), (
                f"Model {model_id} has invalid quantization type"
            )

    def test_all_models_have_positive_context_length(self):
        """Every model should have positive context length."""
        for model_id, config in KNOWN_MODELS.items():
            assert config.context_length > 0, f"Model {model_id} has invalid context"
            assert isinstance(config.context_length, int)

    def test_all_models_match_model_info(self):
        """Every model in KNOWN_MODELS should have corresponding MODEL_INFO."""
        for model_id in KNOWN_MODELS.keys():
            assert model_id in MODEL_INFO, f"Model {model_id} missing from MODEL_INFO"

    def test_all_model_info_has_lists(self):
        """All MODEL_INFO entries should have good_for and not_good_for lists."""
        for model_id, info in MODEL_INFO.items():
            assert isinstance(info.good_for, list), (
                f"Model {model_id} good_for is not a list"
            )
            assert isinstance(info.not_good_for, list), (
                f"Model {model_id} not_good_for is not a list"
            )
            # Should have at least one item in each list
            assert len(info.good_for) > 0, f"Model {model_id} has empty good_for"
            assert len(info.not_good_for) > 0, f"Model {model_id} has empty not_good_for"


class TestGetModelConfigKnown:
    """Test get_model_config() for known models."""

    def test_deepseek_r1_70b_config(self):
        """DeepSeek-R1 70B should return correct config."""
        config = get_model_config("deepseek-r1-70b")

        assert config is not None
        assert config.model_id == "deepseek-r1-70b"
        assert config.name == "DeepSeek-R1 70B"
        assert config.params_billions == 70
        assert config.default_quantization == Quantization.INT4
        assert config.context_length == 8192
        # Validate HF path format exactly
        assert config.hf_path == "deepseek-ai/DeepSeek-R1-Distill-Llama-70B"
        parts = config.hf_path.split("/")
        assert len(parts) == 2
        assert parts[0] == "deepseek-ai"
        assert parts[1] == "DeepSeek-R1-Distill-Llama-70B"

    def test_llama_8b_config(self):
        """Llama 3.1 8B should return correct config."""
        config = get_model_config("llama-3.1-8b")

        assert config is not None
        assert config.model_id == "llama-3.1-8b"
        assert config.name == "Llama 3.1 8B"
        assert config.params_billions == 8
        assert config.default_quantization == Quantization.FP16
        # Validate HF path format exactly
        parts = config.hf_path.split("/")
        assert len(parts) == 2
        assert "llama" in parts[1].lower()  # Model name should contain llama
        assert "3.1" in config.hf_path or "3-1" in config.hf_path  # Version indicator

    def test_qwen_coder_32b_config(self):
        """Qwen2.5-Coder 32B should return correct config."""
        config = get_model_config("qwen2.5-coder-32b")

        assert config is not None
        assert config.model_id == "qwen2.5-coder-32b"
        assert config.params_billions == 32
        assert config.default_quantization == Quantization.FP16
        assert config.context_length == 32768  # Long context
        # Validate HF path format exactly
        parts = config.hf_path.split("/")
        assert len(parts) == 2
        assert "qwen" in parts[0].lower() or "qwen" in parts[1].lower()
        assert "32" in config.hf_path or "32b" in config.hf_path.lower()  # Size indicator

    def test_qwen_coder_32b_int4_config(self):
        """Qwen2.5-Coder 32B INT4 should return correct config."""
        config = get_model_config("qwen2.5-coder-32b-int4")

        assert config is not None
        assert config.model_id == "qwen2.5-coder-32b-int4"
        assert config.params_billions == 32
        assert config.default_quantization == Quantization.INT4
        assert config.context_length == 32768
        # INT4 should use quantized HF path - validate format
        parts = config.hf_path.split("/")
        assert len(parts) == 2
        # Must contain quantization indicator (awq, gptq, or int4)
        hf_lower = config.hf_path.lower()
        assert "awq" in hf_lower or "gptq" in hf_lower or "int4" in hf_lower, \
            f"INT4 model path should indicate quantization method: {config.hf_path}"


class TestGetModelConfigUnknown:
    """Test get_model_config() for unknown models."""

    def test_unknown_model_returns_none(self):
        """Unknown model ID should return None."""
        config = get_model_config("nonexistent-model")
        assert config is None

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        config = get_model_config("")
        assert config is None

    def test_invalid_format_returns_none(self):
        """Invalid model format should return None."""
        config = get_model_config("invalid/model/format")
        assert config is None

    def test_partial_match_returns_none(self):
        """Partial match should not return config."""
        config = get_model_config("deepseek")  # Not full ID
        assert config is None


class TestSpecificKnownModels:
    """Test specific known model configurations."""

    def test_deepseek_is_int4_quantized(self):
        """DeepSeek-R1 70B should use INT4 quantization."""
        config = get_model_config("deepseek-r1-70b")
        assert config is not None
        assert config.default_quantization == Quantization.INT4

    def test_llama_70b_is_int4_quantized(self):
        """Llama 3.1 70B should use INT4 quantization."""
        config = get_model_config("llama-3.1-70b")
        assert config is not None
        assert config.default_quantization == Quantization.INT4

    def test_small_models_use_fp16(self):
        """Small models (7-8B) should use FP16 by default."""
        llama_8b = get_model_config("llama-3.1-8b")
        mistral_7b = get_model_config("mistral-7b")

        assert llama_8b is not None
        assert mistral_7b is not None

        assert llama_8b.default_quantization == Quantization.FP16
        assert mistral_7b.default_quantization == Quantization.FP16

    def test_qwen_models_have_long_context(self):
        """Qwen models should have 32K context length."""
        qwen_fp16 = get_model_config("qwen2.5-coder-32b")
        qwen_int4 = get_model_config("qwen2.5-coder-32b-int4")

        assert qwen_fp16 is not None
        assert qwen_int4 is not None

        assert qwen_fp16.context_length == 32768
        assert qwen_int4.context_length == 32768

    def test_mistral_has_long_context(self):
        """Mistral should have 32K context length."""
        config = get_model_config("mistral-7b")
        assert config is not None
        assert config.context_length == 32768


class TestGetModelGpuMapping:
    """Test get_model_gpu_mapping() function."""

    def test_returns_dict(self):
        """Should return a dictionary."""
        mapping = get_model_gpu_mapping()
        assert isinstance(mapping, dict)

    def test_includes_all_known_models(self):
        """Mapping should include all known models."""
        mapping = get_model_gpu_mapping()

        for model_id in KNOWN_MODELS.keys():
            assert model_id in mapping, f"Model {model_id} missing from mapping"

    def test_all_values_are_strings_or_none(self):
        """All GPU recommendations should be strings or None."""
        mapping = get_model_gpu_mapping()

        for model_id, gpu in mapping.items():
            assert gpu is not None, f"Model {model_id} has None GPU recommendation"
            assert isinstance(gpu, str), f"Model {model_id} GPU is not a string"

    def test_no_extra_models_in_mapping(self):
        """Mapping should not include models not in KNOWN_MODELS."""
        mapping = get_model_gpu_mapping()

        for model_id in mapping.keys():
            assert model_id in KNOWN_MODELS, (
                f"Mapping contains unknown model {model_id}"
            )


class TestModelRegistryConsistency:
    """Test consistency between KNOWN_MODELS and MODEL_INFO."""

    def test_same_model_ids(self):
        """KNOWN_MODELS and MODEL_INFO should have same model IDs."""
        assert set(KNOWN_MODELS.keys()) == set(MODEL_INFO.keys())

    def test_model_info_config_matches(self):
        """ModelInfo.config should match KNOWN_MODELS entry."""
        for model_id in KNOWN_MODELS.keys():
            known_config = KNOWN_MODELS[model_id]
            info_config = MODEL_INFO[model_id].config

            # Should be the same object or have same values
            assert known_config.model_id == info_config.model_id
            assert known_config.params_billions == info_config.params_billions
            assert known_config.default_quantization == info_config.default_quantization

    def test_at_least_five_models(self):
        """Should have at least 5 known models registered."""
        assert len(KNOWN_MODELS) >= 5, "Not enough models in registry"

    def test_has_small_medium_large_models(self):
        """Should have models of different sizes."""
        params = [config.params_billions for config in KNOWN_MODELS.values()]

        # Should have at least one small (<10B), medium (10-40B), and large (>40B)
        assert any(p < 10 for p in params), "No small models"
        assert any(10 <= p <= 40 for p in params), "No medium models"
        assert any(p > 40 for p in params), "No large models"
