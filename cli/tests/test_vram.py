"""Tests for VRAM calculation functions."""

import pytest
from soong.models import (
    Quantization,
    ModelConfig,
    estimate_vram,
)


class TestQuantizationBytesPerParam:
    """Test quantization bytes per parameter calculations."""

    def test_fp32_bytes_per_param(self):
        """FP32 should be 4.0 bytes per parameter."""
        assert Quantization.FP32.bytes_per_param == 4.0

    def test_fp16_bytes_per_param(self):
        """FP16 should be 2.0 bytes per parameter."""
        assert Quantization.FP16.bytes_per_param == 2.0

    def test_bf16_bytes_per_param(self):
        """BF16 should be 2.0 bytes per parameter."""
        assert Quantization.BF16.bytes_per_param == 2.0

    def test_int8_bytes_per_param(self):
        """INT8 should be 1.0 bytes per parameter."""
        assert Quantization.INT8.bytes_per_param == 1.0

    def test_int4_bytes_per_param(self):
        """INT4 should be 0.5 bytes per parameter."""
        assert Quantization.INT4.bytes_per_param == 0.5


class TestEstimateVramLlama70bInt4:
    """Test VRAM estimation for Llama 70B with INT4 quantization."""

    def test_base_vram_calculation(self):
        """Base VRAM should be params * bytes_per_param."""
        result = estimate_vram(
            params_billions=70.0,
            quantization=Quantization.INT4,
            context_length=8192,
        )
        # 70B * 0.5 bytes = 35GB
        assert result["base_vram_gb"] == 35.0

    def test_kv_cache_calculation(self):
        """KV cache should be min(4.0, context/2048)."""
        result = estimate_vram(
            params_billions=70.0,
            quantization=Quantization.INT4,
            context_length=8192,
        )
        # 8192 / 2048 = 4.0, min(4.0, 4.0) = 4.0
        assert result["kv_cache_gb"] == 4.0

    def test_overhead_calculation(self):
        """Overhead should be fixed at 2.0 GB."""
        result = estimate_vram(
            params_billions=70.0,
            quantization=Quantization.INT4,
            context_length=8192,
        )
        assert result["overhead_gb"] == 2.0

    def test_total_estimated_vram(self):
        """Total VRAM should include base + kv_cache + overhead + activations."""
        result = estimate_vram(
            params_billions=70.0,
            quantization=Quantization.INT4,
            context_length=8192,
        )
        # base=35, kv=4, overhead=2, activations=35*0.1=3.5
        # total = 35 + 4 + 2 + 3.5 = 44.5
        assert result["total_estimated_gb"] == 44.5

    def test_min_vram_recommendation(self):
        """Min VRAM should round up to next GPU size with headroom."""
        result = estimate_vram(
            params_billions=70.0,
            quantization=Quantization.INT4,
            context_length=8192,
        )
        # 44.5GB with 10% headroom needs: 44.5 / 0.9 = 49.4GB
        # Next GPU size up is 80GB
        assert result["min_vram_gb"] == 80


class TestVramSmallModel:
    """Test VRAM estimation for small 7B FP16 model."""

    def test_small_model_base_vram(self):
        """7B FP16 base VRAM should be 14GB."""
        result = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=4096,
        )
        # 7B * 2.0 bytes = 14GB
        assert result["base_vram_gb"] == 14.0

    def test_small_model_total_vram(self):
        """7B FP16 total should be approximately 19.4GB."""
        result = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=4096,
        )
        # base=14, kv=2.0, overhead=2, activations=1.4
        # total = 14 + 2 + 2 + 1.4 = 19.4
        assert result["total_estimated_gb"] == 19.4

    def test_small_model_recommended_gpu(self):
        """7B FP16 should fit on 24GB GPU."""
        result = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=4096,
        )
        # 19.4GB fits in 24GB with headroom (24*0.9=21.6GB)
        assert result["min_vram_gb"] == 24


class TestVramLargeContext:
    """Test VRAM estimation with large context windows."""

    def test_kv_cache_capped_at_4gb(self):
        """KV cache should be capped at 4.0GB even with 32K context."""
        result = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=32768,
        )
        # 32768 / 2048 = 16.0, but min(4.0, 16.0) = 4.0
        assert result["kv_cache_gb"] == 4.0

    def test_large_context_increases_total_vram(self):
        """32K context should increase total VRAM vs 4K context."""
        from tests.helpers.assertions import assert_bounds

        result_4k = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=4096,
        )
        result_32k = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=32768,
        )
        # 32K has larger kv_cache (4.0 vs 2.0), difference should be exactly 2.0GB
        kv_diff = result_32k["kv_cache_gb"] - result_4k["kv_cache_gb"]
        assert kv_diff == 2.0, f"Expected 2.0GB kv_cache difference, got {kv_diff}"

        total_diff = result_32k["total_estimated_gb"] - result_4k["total_estimated_gb"]
        assert total_diff == 2.0, f"Expected 2.0GB total difference, got {total_diff}"

        # Verify bounds for both results
        assert_bounds(result_4k["total_estimated_gb"], min_bound=18, max_bound=22, value_name="4K context VRAM")
        assert_bounds(result_32k["total_estimated_gb"], min_bound=20, max_bound=24, value_name="32K context VRAM")


class TestModelConfigVramProperties:
    """Test ModelConfig VRAM calculation properties."""

    def test_base_vram_gb_property(self):
        """base_vram_gb should match params * bytes_per_param."""
        config = ModelConfig(
            name="Test",
            model_id="test",
            hf_path="test/test",
            params_billions=70.0,
            default_quantization=Quantization.INT4,
            context_length=8192,
        )
        # 70 * 0.5 = 35
        assert config.base_vram_gb == 35.0

    def test_estimated_vram_gb_property(self):
        """estimated_vram_gb should include all overhead."""
        config = ModelConfig(
            name="Test",
            model_id="test",
            hf_path="test/test",
            params_billions=70.0,
            default_quantization=Quantization.INT4,
            context_length=8192,
        )
        # base=35, kv=4, overhead=2, activations=3.5 = 44.5
        assert config.estimated_vram_gb == 44.5

    def test_min_vram_gb_property(self):
        """min_vram_gb should round up to nearest GPU size."""
        config = ModelConfig(
            name="Test",
            model_id="test",
            hf_path="test/test",
            params_billions=70.0,
            default_quantization=Quantization.INT4,
            context_length=8192,
        )
        # 44.5 GB with 10% headroom needs 80GB GPU
        assert config.min_vram_gb == 80


class TestEstimateVramEdgeCases:
    """Test edge cases in VRAM estimation."""

    def test_very_small_model(self):
        """Test VRAM estimation for very small model."""
        result = estimate_vram(
            params_billions=1.0,
            quantization=Quantization.INT4,
            context_length=2048,
        )
        # Should still get valid result
        assert result["base_vram_gb"] == 0.5
        assert result["min_vram_gb"] == 16  # Smallest GPU size

    def test_very_large_model(self):
        """Test VRAM estimation for very large model."""
        result = estimate_vram(
            params_billions=400.0,
            quantization=Quantization.FP16,
            context_length=8192,
        )
        # 400 * 2 = 800 base, should need multi-GPU
        assert result["base_vram_gb"] == 800.0
        assert result["min_vram_gb"] == 160  # Max single config

    def test_minimal_context(self):
        """Test VRAM estimation with minimal context length."""
        from tests.helpers.assertions import assert_bounds

        result = estimate_vram(
            params_billions=7.0,
            quantization=Quantization.FP16,
            context_length=512,
        )
        # 512 / 2048 = 0.25, min(4.0, 0.25) = 0.25
        # Verify exact value with tolerance for rounding
        assert_bounds(result["kv_cache_gb"], min_bound=0.2, max_bound=0.3, value_name="KV cache")

        # Verify result structure is complete
        required_keys = ["base_vram_gb", "kv_cache_gb", "overhead_gb", "total_estimated_gb", "min_vram_gb"]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

        # Verify values are valid numbers and positive
        assert isinstance(result["kv_cache_gb"], (int, float))
        assert result["kv_cache_gb"] > 0
        assert isinstance(result["total_estimated_gb"], (int, float))
        assert result["total_estimated_gb"] > 0
        assert isinstance(result["min_vram_gb"], int)
        assert result["min_vram_gb"] > 0
