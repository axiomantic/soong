"""Tests for GPU recommendation functions."""

import pytest
from gpu_session.models import (
    get_recommended_gpu,
    get_model_config,
    ModelConfig,
    Quantization,
    KNOWN_GPUS,
)


class TestGetRecommendedGpuDeepseekR170b:
    """Test GPU recommendation for DeepSeek-R1 70B model."""

    def test_returns_80gb_gpu(self):
        """DeepSeek-R1 70B should recommend 80GB GPU."""
        gpu = get_recommended_gpu("deepseek-r1-70b")

        # Should return a GPU with at least 80GB (needs ~44.5GB + 10% headroom)
        assert gpu is not None
        gpu_info = KNOWN_GPUS[gpu]
        assert gpu_info["vram_gb"] >= 80

    def test_returns_cheapest_viable_gpu(self):
        """Should return the cheapest GPU that can run the model."""
        gpu = get_recommended_gpu("deepseek-r1-70b")

        # Should be 80GB GPU (smallest that fits with headroom)
        assert gpu is not None
        gpu_info = KNOWN_GPUS[gpu]
        assert gpu_info["vram_gb"] == 80

    def test_model_min_vram_matches_recommendation(self):
        """Recommended GPU VRAM should match model's min_vram_gb."""
        config = get_model_config("deepseek-r1-70b")
        gpu = get_recommended_gpu("deepseek-r1-70b")

        assert config is not None
        assert gpu is not None

        gpu_info = KNOWN_GPUS[gpu]
        # GPU VRAM should be >= model min requirement
        assert gpu_info["vram_gb"] >= config.min_vram_gb


class TestGetRecommendedGpuLlama8b:
    """Test GPU recommendation for Llama 8B model."""

    def test_returns_smallest_viable_gpu(self):
        """Llama 8B should recommend smallest GPU that fits."""
        gpu = get_recommended_gpu("llama-3.1-8b")

        assert gpu is not None
        gpu_info = KNOWN_GPUS[gpu]

        # 8B FP16: 16GB base + 4GB kv + 2GB overhead + 1.6GB activations = 23.6GB
        # With 10% headroom needs 26.2GB, rounds up to 40GB
        assert gpu_info["vram_gb"] == 40

    def test_does_not_over_provision(self):
        """Should not recommend 48GB+ GPU for small model."""
        gpu = get_recommended_gpu("llama-3.1-8b")

        assert gpu is not None
        gpu_info = KNOWN_GPUS[gpu]

        # Should be 40GB, not 48GB+
        assert gpu_info["vram_gb"] <= 40


class TestGetRecommendedGpuQwen32b:
    """Test GPU recommendation for Qwen 32B models."""

    def test_qwen_fp16_recommendation(self):
        """Qwen2.5-Coder 32B FP16 should need 80GB GPU."""
        gpu = get_recommended_gpu("qwen2.5-coder-32b")

        assert gpu is not None
        gpu_info = KNOWN_GPUS[gpu]

        # 32B FP16 = 64GB base + overhead ≈ 73GB, needs 80GB GPU
        assert gpu_info["vram_gb"] >= 80

    def test_qwen_int4_recommendation(self):
        """Qwen2.5-Coder 32B INT4 should need less VRAM than FP16."""
        gpu_fp16 = get_recommended_gpu("qwen2.5-coder-32b")
        gpu_int4 = get_recommended_gpu("qwen2.5-coder-32b-int4")

        assert gpu_fp16 is not None
        assert gpu_int4 is not None

        vram_fp16 = KNOWN_GPUS[gpu_fp16]["vram_gb"]
        vram_int4 = KNOWN_GPUS[gpu_int4]["vram_gb"]

        # INT4 should need less or equal VRAM
        assert vram_int4 <= vram_fp16


class TestGetRecommendedGpuUnknownModel:
    """Test GPU recommendation for unknown/invalid models."""

    def test_unknown_model_returns_none(self):
        """Unknown model should return None."""
        gpu = get_recommended_gpu("nonexistent-model")
        assert gpu is None

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        gpu = get_recommended_gpu("")
        assert gpu is None

    def test_invalid_model_id_returns_none(self):
        """Invalid model ID should return None."""
        gpu = get_recommended_gpu("invalid/model/id/format")
        assert gpu is None


class TestGetRecommendedGpuAllKnownModels:
    """Test that all known models have valid GPU recommendations."""

    def test_all_models_have_recommendation(self):
        """Every known model should have a GPU recommendation."""
        from gpu_session.models import KNOWN_MODELS

        for model_id in KNOWN_MODELS.keys():
            gpu = get_recommended_gpu(model_id)
            assert gpu is not None, f"Model {model_id} has no GPU recommendation"

    def test_all_recommendations_are_valid_gpus(self):
        """All recommendations should be valid GPU names."""
        from gpu_session.models import KNOWN_MODELS

        for model_id in KNOWN_MODELS.keys():
            gpu = get_recommended_gpu(model_id)
            assert gpu in KNOWN_GPUS, f"Model {model_id} recommends invalid GPU {gpu}"

    def test_recommended_gpu_has_sufficient_vram(self):
        """Recommended GPU should have enough VRAM for the model."""
        from gpu_session.models import KNOWN_MODELS

        for model_id in KNOWN_MODELS.keys():
            config = get_model_config(model_id)
            gpu = get_recommended_gpu(model_id)

            assert config is not None
            assert gpu is not None

            gpu_vram = KNOWN_GPUS[gpu]["vram_gb"]
            min_required = config.min_vram_gb

            assert gpu_vram >= min_required, (
                f"Model {model_id} needs {min_required}GB but "
                f"recommended GPU {gpu} only has {gpu_vram}GB"
            )


class TestModelConfigRecommendedGpus:
    """Test ModelConfig.recommended_gpus() method."""

    def test_filters_gpus_by_vram(self):
        """Should only return GPUs with sufficient VRAM."""
        # Use smaller model that fits in 48GB
        config = ModelConfig(
            name="Test",
            model_id="test",
            hf_path="test/test",
            params_billions=32.0,
            default_quantization=Quantization.INT4,
            context_length=8192,
        )

        available_gpus = [
            {"name": "gpu_1x_a10", "vram_gb": 24},
            {"name": "gpu_1x_a6000", "vram_gb": 48},
            {"name": "gpu_1x_a100_sxm4_80gb", "vram_gb": 80},
        ]

        recommended = config.recommended_gpus(available_gpus)

        # 32B INT4 needs ~22GB, fits in 48GB and 80GB
        assert "gpu_1x_a6000" in recommended
        assert "gpu_1x_a100_sxm4_80gb" in recommended
        assert "gpu_1x_a10" not in recommended

    def test_empty_list_when_no_gpus_sufficient(self):
        """Should return empty list when no GPU has enough VRAM."""
        config = ModelConfig(
            name="Huge Model",
            model_id="huge",
            hf_path="test/huge",
            params_billions=400.0,
            default_quantization=Quantization.FP16,
            context_length=8192,
        )

        available_gpus = [
            {"name": "gpu_1x_a10", "vram_gb": 24},
            {"name": "gpu_1x_a6000", "vram_gb": 48},
        ]

        recommended = config.recommended_gpus(available_gpus)

        assert recommended == []

    def test_all_gpus_when_model_very_small(self):
        """Should return all GPUs for very small model."""
        config = ModelConfig(
            name="Tiny Model",
            model_id="tiny",
            hf_path="test/tiny",
            params_billions=1.0,
            default_quantization=Quantization.INT4,
            context_length=2048,
        )

        available_gpus = [
            {"name": "gpu_1x_a10", "vram_gb": 24},
            {"name": "gpu_1x_a6000", "vram_gb": 48},
            {"name": "gpu_1x_a100_sxm4_80gb", "vram_gb": 80},
        ]

        recommended = config.recommended_gpus(available_gpus)

        # All GPUs should be sufficient
        assert len(recommended) == 3


class TestGpuRecommendationSorting:
    """Test that GPU recommendations return cheapest viable option."""

    def test_returns_cheapest_not_largest(self):
        """Should return cheapest GPU, not largest."""
        # Small model should get small GPU, not 80GB
        gpu_small = get_recommended_gpu("mistral-7b")  # Gets 24GB
        gpu_large = get_recommended_gpu("deepseek-r1-70b")  # Gets 80GB

        assert gpu_small is not None
        assert gpu_large is not None

        # Small should be 24GB, large should be 80GB
        assert KNOWN_GPUS[gpu_small]["vram_gb"] == 24
        assert KNOWN_GPUS[gpu_large]["vram_gb"] == 80

    def test_consistent_recommendations_for_same_size(self):
        """Models with same VRAM needs should get same recommendation."""
        # Both are 70B INT4 models
        gpu1 = get_recommended_gpu("deepseek-r1-70b")
        gpu2 = get_recommended_gpu("llama-3.1-70b")

        assert gpu1 is not None
        assert gpu2 is not None

        # Should have same VRAM capacity (though might be different GPU models)
        assert KNOWN_GPUS[gpu1]["vram_gb"] == KNOWN_GPUS[gpu2]["vram_gb"]
