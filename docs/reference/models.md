# Model Registry Reference

Complete reference for built-in AI models supported by `gpu-session`.

## Overview

`gpu-session` includes 7 pre-configured models optimized for different use cases. Each model includes:

- **VRAM estimation** - Automatic calculation of memory requirements
- **GPU recommendation** - Best GPU type for the model
- **Quantization** - Memory-efficient compression
- **Use case guidance** - What the model is good (and not good) for

## Quick Model Comparison

| Model | Size | VRAM | Min GPU | Best For | Cost/hr |
|-------|------|------|---------|----------|---------|
| Llama 3.1 8B | 8B | 18 GB | A10 (24GB) | Quick tasks, prototyping | ~$0.60 |
| Mistral 7B | 7B | 20 GB | A10 (24GB) | Long contexts, efficiency | ~$0.60 |
| Qwen 2.5 Coder 32B INT4 | 32B | 22 GB | A10 (24GB) | Code on budget | ~$0.60 |
| Code Llama 34B | 34B | 73 GB | A100 (80GB) | Code completion | ~$1.29 |
| Qwen 2.5 Coder 32B | 32B | 69 GB | A100 (80GB) | Fast code generation | ~$1.29 |
| **DeepSeek-R1 70B** | 70B | 44 GB | A100 (80GB) | **Complex reasoning** | **~$1.29** |
| Llama 3.1 70B | 70B | 44 GB | A100 (80GB) | General purpose | ~$1.29 |

## Built-in Models

### DeepSeek-R1 70B ⭐ Recommended

**Best for complex coding tasks requiring deep reasoning.**

```yaml
Model ID: deepseek-r1-70b
HuggingFace: deepseek-ai/DeepSeek-R1-Distill-Llama-70B
Parameters: 70 billion
Quantization: INT4 (GPTQ/AWQ)
Context: 8,192 tokens
Est. VRAM: 44 GB
Min GPU: 1x A100 SXM4 (80 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 35.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 3.5 GB |
| **Total** | **44.5 GB** |

#### Use Cases

**Good for:**
- ✅ Complex multi-step reasoning
- ✅ Debugging difficult issues
- ✅ Architecture decisions
- ✅ Code review with explanations
- ✅ Chain-of-thought problem solving

**Not good for:**
- ❌ Simple/quick tasks (overkill)
- ❌ Long context windows (8K limit)
- ❌ Speed-critical applications

#### Notes

Chain-of-thought reasoning model. Slower but more accurate than general models. Uses reinforcement learning from human feedback (RLHF) for better reasoning.

---

### Qwen 2.5 Coder 32B

**Fast coding specialist with exceptional context length.**

```yaml
Model ID: qwen2.5-coder-32b
HuggingFace: Qwen/Qwen2.5-Coder-32B-Instruct
Parameters: 32 billion
Quantization: FP16
Context: 32,768 tokens (4x longer than DeepSeek)
Est. VRAM: 69 GB
Min GPU: 1x A100 SXM4 (80 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 64.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 6.4 GB |
| **Total** | **76.4 GB** |

#### Use Cases

**Good for:**
- ✅ Code generation and completion
- ✅ Large file refactoring (32K context)
- ✅ Fast iteration cycles
- ✅ Multiple programming languages
- ✅ Reviewing entire modules at once

**Not good for:**
- ❌ Complex reasoning chains
- ❌ Non-coding tasks
- ❌ Tasks requiring world knowledge

#### Notes

Purpose-built for code. Supports 80+ programming languages. 4x longer context than DeepSeek makes it ideal for working with large files.

---

### Qwen 2.5 Coder 32B INT4

**Budget-friendly quantized version of Qwen Coder.**

```yaml
Model ID: qwen2.5-coder-32b-int4
HuggingFace: Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
Parameters: 32 billion
Quantization: INT4 (AWQ)
Context: 32,768 tokens
Est. VRAM: 22 GB
Min GPU: 1x A10 (24 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 16.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 1.6 GB |
| **Total** | **23.6 GB** |

#### Use Cases

**Good for:**
- ✅ Same tasks as Qwen FP16
- ✅ Cheaper GPU requirements (A10 vs A100)
- ✅ Good quality/cost ratio
- ✅ Cost-conscious development

**Not good for:**
- ❌ Maximum accuracy (slight quality loss)
- ❌ Tasks where FP16 precision matters

#### Notes

~5% quality loss vs FP16, but runs on cheaper GPUs. Uses AWQ (Activation-aware Weight Quantization) for better quality than naive INT4.

---

### Llama 3.1 70B

**General-purpose powerhouse for diverse tasks.**

```yaml
Model ID: llama-3.1-70b
HuggingFace: meta-llama/Llama-3.1-70B-Instruct
Parameters: 70 billion
Quantization: INT4
Context: 8,192 tokens
Est. VRAM: 44 GB
Min GPU: 1x A100 SXM4 (80 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 35.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 3.5 GB |
| **Total** | **44.5 GB** |

#### Use Cases

**Good for:**
- ✅ Broad task coverage
- ✅ Instruction following
- ✅ Writing and documentation
- ✅ Code + general knowledge
- ✅ Balanced performance

**Not good for:**
- ❌ Pure coding (Qwen better)
- ❌ Deep reasoning (DeepSeek better)
- ❌ Very long contexts

#### Notes

Jack of all trades. Good baseline choice when task type is unclear. Strong instruction following and safer outputs due to extensive RLHF training.

---

### Llama 3.1 8B

**Fast and economical for simple tasks.**

```yaml
Model ID: llama-3.1-8b
HuggingFace: meta-llama/Llama-3.1-8B-Instruct
Parameters: 8 billion
Quantization: FP16
Context: 8,192 tokens
Est. VRAM: 18 GB
Min GPU: 1x A10 (24 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 16.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 1.6 GB |
| **Total** | **23.6 GB** |

#### Use Cases

**Good for:**
- ✅ Quick simple tasks
- ✅ Lowest cost
- ✅ Rapid prototyping
- ✅ Simple code changes
- ✅ Testing workflows

**Not good for:**
- ❌ Complex reasoning
- ❌ Large codebases
- ❌ Nuanced decisions
- ❌ Multi-step tasks

#### Notes

Use when speed/cost matters more than quality. Great for testing infrastructure or simple repetitive tasks.

---

### Code Llama 34B

**Meta's dedicated coding model (older generation).**

```yaml
Model ID: codellama-34b
HuggingFace: codellama/CodeLlama-34b-Instruct-hf
Parameters: 34 billion
Quantization: FP16
Context: 16,384 tokens
Est. VRAM: 73 GB
Min GPU: 1x A100 SXM4 (80 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 68.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 6.8 GB |
| **Total** | **80.8 GB** |

#### Use Cases

**Good for:**
- ✅ Code completion
- ✅ Infilling (fill-in-the-middle)
- ✅ 16K context window
- ✅ Python, Java, C++

**Not good for:**
- ❌ Latest techniques (2023 model)
- ❌ Complex reasoning
- ❌ Non-code tasks

#### Notes

Older but still capable. Consider Qwen 2.5 Coder for newer alternative with better performance.

---

### Mistral 7B

**Efficient model with sliding window attention.**

```yaml
Model ID: mistral-7b
HuggingFace: mistralai/Mistral-7B-Instruct-v0.3
Parameters: 7 billion
Quantization: FP16
Context: 32,768 tokens
Est. VRAM: 20 GB
Min GPU: 1x A10 (24 GB)
```

#### VRAM Breakdown

| Component | Memory |
|-----------|--------|
| Base weights | 14.0 GB |
| KV cache | 4.0 GB |
| CUDA overhead | 2.0 GB |
| Activations | 1.4 GB |
| **Total** | **21.4 GB** |

#### Use Cases

**Good for:**
- ✅ Long documents (32K context)
- ✅ Low resource usage
- ✅ Fast inference
- ✅ Sliding window attention

**Not good for:**
- ❌ Complex coding tasks
- ❌ Tasks needing large model capacity

#### Notes

Great efficiency but limited capacity. Uses sliding window attention for efficient long context processing.

---

## Model Selection Guide

### By Use Case

| Task | Recommended Model | Why |
|------|------------------|-----|
| Complex debugging | DeepSeek-R1 70B | Chain-of-thought reasoning |
| Large file refactoring | Qwen 2.5 Coder 32B | 32K context window |
| Budget coding | Qwen 2.5 Coder 32B INT4 | Good quality, cheap GPU |
| General purpose | Llama 3.1 70B | Balanced performance |
| Quick testing | Llama 3.1 8B | Fast and cheap |
| Long documents | Mistral 7B | 32K context, efficient |

### By GPU Budget

| GPU Type | VRAM | Suitable Models |
|----------|------|-----------------|
| A10 (24 GB) | 24 GB | Llama 8B, Mistral 7B, Qwen 32B INT4 |
| A6000 (48 GB) | 48 GB | DeepSeek-R1 70B, Llama 70B |
| A100 (80 GB) | 80 GB | All models, especially Qwen 32B FP16 |
| H100 (80 GB) | 80 GB | All models with faster inference |

### By Context Length Needs

| Context Needed | Models |
|----------------|--------|
| 8K tokens | DeepSeek-R1, Llama 8B/70B |
| 16K tokens | Code Llama 34B |
| 32K tokens | Qwen 2.5 Coder, Mistral 7B |

---

## VRAM Estimation Formula

For any model, VRAM is estimated as:

```
Total VRAM = Base + KV Cache + Overhead + Activations

Base = params_billions × bytes_per_param
KV Cache = min(4.0 GB, context_length / 2048)
Overhead = 2.0 GB (CUDA, framework)
Activations = base × 0.1
```

### Quantization Levels

| Quantization | Bytes/Param | Memory vs FP32 | Quality Loss |
|--------------|-------------|----------------|--------------|
| FP32 | 4.0 | 100% | 0% (baseline) |
| FP16/BF16 | 2.0 | 50% | ~0-1% |
| INT8 | 1.0 | 25% | ~3-5% |
| INT4 (GPTQ/AWQ) | 0.5 | 12.5% | ~5-8% |

---

## Custom Models

You can add your own models using the CLI or config file.

### Via CLI

```bash
# Interactive
gpu-session models add

# With flags
gpu-session models add \
  --name my-model-70b \
  --hf-path myorg/custom-llama-70b \
  --params 70 \
  --quantization int4 \
  --context 8192
```

### Via Config File

Edit `~/.config/gpu-dashboard/config.yaml`:

```yaml
custom_models:
  my-model-70b:
    hf_path: myorg/custom-llama-70b
    params_billions: 70
    quantization: int4
    context_length: 8192
    notes: Fine-tuned on domain data
```

See [Configuration Reference](configuration-file.md#custom_models) for full schema.

---

## Listing Models

```bash
# List all models (built-in + custom)
gpu-session models

# Get detailed info
gpu-session models info deepseek-r1-70b
```

---

## Model Update Policy

Built-in models are updated when:

1. **New high-quality models release** (e.g., Llama 4, GPT-4 class)
2. **Better quantization methods** (e.g., ExLlamaV2, GGUF improvements)
3. **Lambda Labs adds new GPUs** (requiring different recommendations)

Check releases for model registry updates.

---

## Performance Benchmarks

Approximate tokens/second on Lambda Labs GPUs:

| Model | A10 (24GB) | A100 (80GB) | H100 (80GB) |
|-------|------------|-------------|-------------|
| Llama 8B FP16 | 80 tok/s | 120 tok/s | 200 tok/s |
| Qwen 32B INT4 | 40 tok/s | 60 tok/s | 100 tok/s |
| DeepSeek 70B INT4 | N/A | 30 tok/s | 50 tok/s |
| Qwen 32B FP16 | N/A | 45 tok/s | 75 tok/s |

*Benchmarks approximate. Actual performance varies by context length and prompt complexity.*

---

## Frequently Asked Questions

### Why INT4 for 70B models?

INT4 quantization (GPTQ/AWQ) allows 70B models to fit on 80GB GPUs with minimal quality loss (~5-8%). Without it, you'd need multi-GPU setups.

### Can I use GGUF models?

Currently, `gpu-session` uses SGLang which doesn't support GGUF. Models must be in HuggingFace Transformers format (safetensors).

### What about LoRA adapters?

Custom LoRA adapters can be loaded by specifying the adapter path in cloud-init scripts. Not currently automated in CLI.

### How do I choose between DeepSeek and Qwen?

- **DeepSeek**: Better for complex reasoning, architecture decisions, debugging
- **Qwen**: Better for code generation, refactoring, working with large files

### Why is Qwen FP16 so expensive (69 GB)?

FP16 doubles memory vs INT4. Qwen 32B FP16 = 64 GB base + overhead = 69 GB total. Use INT4 version if cost matters.

---

## See Also

- [GPU Types Reference](gpu-types.md) - Available GPUs
- [Configuration Reference](configuration-file.md) - Custom model setup
- [CLI Commands](cli-commands.md) - `models` command reference
