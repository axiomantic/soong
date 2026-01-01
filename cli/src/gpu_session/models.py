"""Model configurations and GPU requirements."""

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum


class Quantization(Enum):
    """Quantization levels."""
    FP32 = "fp32"      # 4 bytes per param
    FP16 = "fp16"      # 2 bytes per param
    BF16 = "bf16"      # 2 bytes per param
    INT8 = "int8"      # 1 byte per param
    INT4 = "int4"      # 0.5 bytes per param (GPTQ, AWQ, GGUF Q4)

    @property
    def bytes_per_param(self) -> float:
        return {
            Quantization.FP32: 4.0,
            Quantization.FP16: 2.0,
            Quantization.BF16: 2.0,
            Quantization.INT8: 1.0,
            Quantization.INT4: 0.5,
        }[self]


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str                          # Display name
    model_id: str                      # Internal ID used in config
    hf_path: str                       # HuggingFace path
    params_billions: float             # Parameter count in billions
    default_quantization: Quantization # Default quantization for SGLang
    context_length: int = 8192         # Default context length
    description: str = ""              # Short description

    @property
    def base_vram_gb(self) -> float:
        """Calculate base VRAM requirement (model weights only)."""
        return self.params_billions * self.default_quantization.bytes_per_param

    @property
    def estimated_vram_gb(self) -> float:
        """
        Estimate total VRAM with overhead.

        Includes:
        - Model weights
        - KV cache (~2-4GB depending on context)
        - CUDA/framework overhead (~2GB)
        - Activation memory (~10% of weights)
        """
        base = self.base_vram_gb
        kv_cache = min(4.0, self.context_length / 2048)  # ~1GB per 2k context
        overhead = 2.0  # CUDA, framework
        activations = base * 0.1  # ~10% for activations
        return base + kv_cache + overhead + activations

    @property
    def min_vram_gb(self) -> int:
        """Minimum VRAM needed (rounded up to common GPU sizes)."""
        estimated = self.estimated_vram_gb
        # Round up to common GPU VRAM sizes
        gpu_sizes = [16, 24, 40, 48, 80, 160]
        for size in gpu_sizes:
            if estimated <= size * 0.9:  # 10% headroom
                return size
        return 160  # Multi-GPU needed

    def recommended_gpus(self, available_gpus: List[dict]) -> List[str]:
        """
        Get list of recommended GPU types for this model.

        Args:
            available_gpus: List of GPU info dicts with 'name' and 'vram_gb' keys

        Returns:
            List of GPU names that can run this model
        """
        min_vram = self.min_vram_gb
        return [
            gpu['name'] for gpu in available_gpus
            if gpu.get('vram_gb', 0) >= min_vram
        ]


def estimate_vram(
    params_billions: float,
    quantization: Quantization = Quantization.FP16,
    context_length: int = 8192,
) -> dict:
    """
    Estimate VRAM requirements for any model.

    Args:
        params_billions: Parameter count in billions
        quantization: Quantization level
        context_length: Context window size

    Returns:
        Dict with VRAM estimates and recommended GPU
    """
    base = params_billions * quantization.bytes_per_param
    kv_cache = min(4.0, context_length / 2048)
    overhead = 2.0
    activations = base * 0.1
    total = base + kv_cache + overhead + activations

    # Find minimum GPU size
    gpu_sizes = [16, 24, 40, 48, 80, 160]
    min_gpu = 160
    for size in gpu_sizes:
        if total <= size * 0.9:
            min_gpu = size
            break

    return {
        "params_billions": params_billions,
        "quantization": quantization.value,
        "base_vram_gb": round(base, 1),
        "kv_cache_gb": round(kv_cache, 1),
        "overhead_gb": round(overhead, 1),
        "total_estimated_gb": round(total, 1),
        "min_vram_gb": min_gpu,
    }


# Known GPU configurations (VRAM in GB)
KNOWN_GPUS = {
    "gpu_1x_a10": {"vram_gb": 24, "description": "1x A10 (24 GB)"},
    "gpu_1x_a100": {"vram_gb": 40, "description": "1x A100 (40 GB)"},
    "gpu_1x_a100_sxm4": {"vram_gb": 40, "description": "1x A100 SXM4 (40 GB)"},
    "gpu_1x_a100_sxm4_80gb": {"vram_gb": 80, "description": "1x A100 SXM4 (80 GB)"},
    "gpu_1x_a6000": {"vram_gb": 48, "description": "1x A6000 (48 GB)"},
    "gpu_1x_rtx6000": {"vram_gb": 48, "description": "1x RTX 6000 (48 GB)"},
    "gpu_1x_h100_pcie": {"vram_gb": 80, "description": "1x H100 PCIe (80 GB)"},
    "gpu_1x_h100_sxm5": {"vram_gb": 80, "description": "1x H100 SXM5 (80 GB)"},
    "gpu_2x_a100": {"vram_gb": 80, "description": "2x A100 (80 GB total)"},
    "gpu_4x_a100": {"vram_gb": 160, "description": "4x A100 (160 GB total)"},
    "gpu_8x_a100": {"vram_gb": 320, "description": "8x A100 (320 GB total)"},
    "gpu_8x_h100": {"vram_gb": 640, "description": "8x H100 (640 GB total)"},
}


@dataclass
class ModelInfo:
    """Extended model information with pros/cons."""
    config: ModelConfig
    good_for: List[str]
    not_good_for: List[str]
    notes: str = ""


# Pre-configured models with their requirements
KNOWN_MODELS: Dict[str, ModelConfig] = {}
MODEL_INFO: Dict[str, ModelInfo] = {}


def _register_model(
    model_id: str,
    name: str,
    hf_path: str,
    params_billions: float,
    quantization: Quantization,
    context_length: int,
    description: str,
    good_for: List[str],
    not_good_for: List[str],
    notes: str = "",
):
    """Register a model with full info."""
    config = ModelConfig(
        name=name,
        model_id=model_id,
        hf_path=hf_path,
        params_billions=params_billions,
        default_quantization=quantization,
        context_length=context_length,
        description=description,
    )
    KNOWN_MODELS[model_id] = config
    MODEL_INFO[model_id] = ModelInfo(
        config=config,
        good_for=good_for,
        not_good_for=not_good_for,
        notes=notes,
    )


# Register all known models

_register_model(
    model_id="deepseek-r1-70b",
    name="DeepSeek-R1 70B",
    hf_path="deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    params_billions=70,
    quantization=Quantization.INT4,
    context_length=8192,
    description="Best reasoning model for complex coding tasks",
    good_for=[
        "Complex multi-step reasoning",
        "Debugging difficult issues",
        "Architecture decisions",
        "Code review with explanations",
    ],
    not_good_for=[
        "Simple/quick tasks (overkill)",
        "Long context windows (8K limit)",
        "Speed-critical applications",
    ],
    notes="Chain-of-thought reasoning. Slower but more accurate.",
)

_register_model(
    model_id="qwen2.5-coder-32b",
    name="Qwen2.5-Coder 32B",
    hf_path="Qwen/Qwen2.5-Coder-32B-Instruct",
    params_billions=32,
    quantization=Quantization.FP16,
    context_length=32768,
    description="Fast coding specialist with long context",
    good_for=[
        "Code generation and completion",
        "Large file refactoring (32K context)",
        "Fast iteration cycles",
        "Multiple language support",
    ],
    not_good_for=[
        "Complex reasoning chains",
        "Non-coding tasks",
        "Tasks requiring world knowledge",
    ],
    notes="Purpose-built for code. 4x longer context than DeepSeek.",
)

_register_model(
    model_id="qwen2.5-coder-32b-int4",
    name="Qwen2.5-Coder 32B (Quantized)",
    hf_path="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
    params_billions=32,
    quantization=Quantization.INT4,
    context_length=32768,
    description="Budget-friendly coding model",
    good_for=[
        "Same tasks as Qwen FP16",
        "Cheaper GPU requirements",
        "Good quality/cost ratio",
    ],
    not_good_for=[
        "Maximum accuracy (slight quality loss)",
        "Tasks where FP16 precision matters",
    ],
    notes="~5% quality loss vs FP16, but runs on cheaper GPUs.",
)

_register_model(
    model_id="llama-3.1-70b",
    name="Llama 3.1 70B",
    hf_path="meta-llama/Llama-3.1-70B-Instruct",
    params_billions=70,
    quantization=Quantization.INT4,
    context_length=8192,
    description="General-purpose powerhouse",
    good_for=[
        "Broad task coverage",
        "Instruction following",
        "Writing and documentation",
        "Code + general knowledge",
    ],
    not_good_for=[
        "Pure coding (Qwen better)",
        "Deep reasoning (DeepSeek better)",
        "Very long contexts",
    ],
    notes="Jack of all trades. Good baseline choice.",
)

_register_model(
    model_id="llama-3.1-8b",
    name="Llama 3.1 8B",
    hf_path="meta-llama/Llama-3.1-8B-Instruct",
    params_billions=8,
    quantization=Quantization.FP16,
    context_length=8192,
    description="Fast and cheap for simple tasks",
    good_for=[
        "Quick simple tasks",
        "Lowest cost",
        "Rapid prototyping",
        "Simple code changes",
    ],
    not_good_for=[
        "Complex reasoning",
        "Large codebases",
        "Nuanced decisions",
        "Multi-step tasks",
    ],
    notes="Use when speed/cost matters more than quality.",
)

_register_model(
    model_id="codellama-34b",
    name="Code Llama 34B",
    hf_path="codellama/CodeLlama-34b-Instruct-hf",
    params_billions=34,
    quantization=Quantization.FP16,
    context_length=16384,
    description="Meta's dedicated coding model",
    good_for=[
        "Code completion",
        "Infilling (fill-in-the-middle)",
        "16K context window",
    ],
    not_good_for=[
        "Latest techniques (older model)",
        "Complex reasoning",
        "Non-code tasks",
    ],
    notes="Older but still capable. Consider Qwen for newer alternative.",
)

_register_model(
    model_id="mistral-7b",
    name="Mistral 7B",
    hf_path="mistralai/Mistral-7B-Instruct-v0.3",
    params_billions=7,
    quantization=Quantization.FP16,
    context_length=32768,
    description="Efficient with sliding window attention",
    good_for=[
        "Long documents (32K context)",
        "Low resource usage",
        "Fast inference",
    ],
    not_good_for=[
        "Complex coding tasks",
        "Tasks needing large model capacity",
    ],
    notes="Great efficiency but limited capacity.",
)


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """Get configuration for a known model."""
    return KNOWN_MODELS.get(model_id)


def get_recommended_gpu(model_id: str) -> Optional[str]:
    """
    Get the recommended GPU for a model.

    Returns the cheapest GPU that can run the model.
    """
    config = get_model_config(model_id)
    if not config:
        return None

    min_vram = config.min_vram_gb

    # Sort GPUs by VRAM (ascending) to get cheapest viable option
    sorted_gpus = sorted(
        KNOWN_GPUS.items(),
        key=lambda x: x[1]['vram_gb']
    )

    for gpu_name, gpu_info in sorted_gpus:
        if gpu_info['vram_gb'] >= min_vram:
            return gpu_name

    return None


def get_model_gpu_mapping() -> Dict[str, str]:
    """
    Get mapping of all models to their recommended GPUs.

    Returns:
        Dict mapping model_id to recommended gpu_name
    """
    return {
        model_id: get_recommended_gpu(model_id)
        for model_id in KNOWN_MODELS
    }


def format_model_info(model: ModelConfig) -> str:
    """Format model info for display."""
    gpu = get_recommended_gpu(model.model_id)
    gpu_info = KNOWN_GPUS.get(gpu, {})

    return (
        f"{model.name}\n"
        f"  Parameters: {model.params_billions}B\n"
        f"  Quantization: {model.default_quantization.value.upper()}\n"
        f"  Est. VRAM: {model.estimated_vram_gb:.1f} GB\n"
        f"  Min GPU: {gpu_info.get('description', gpu)}\n"
        f"  HF Path: {model.hf_path}"
    )
