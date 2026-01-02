# GPU Types Reference

Complete reference for Lambda Labs GPU types available through `gpu-session`.

## Overview

Lambda Labs offers GPUs from NVIDIA's professional and data center lines:

- **A10**: Entry-level, 24 GB VRAM
- **A6000/RTX 6000**: Workstation class, 48 GB VRAM
- **A100**: Data center standard, 40-80 GB VRAM
- **H100**: Latest generation, 80 GB VRAM with faster performance

## GPU Comparison Table

| GPU Type | GPU | VRAM | vCPUs | RAM | Storage | Est. Price/hr |
|----------|-----|------|-------|-----|---------|---------------|
| `gpu_1x_a10` | 1x A10 | 24 GB | 30 | 200 GB | 1.4 TB | $0.60 |
| `gpu_1x_a6000` | 1x A6000 | 48 GB | 28 | 200 GB | 512 GB | $0.80 |
| `gpu_1x_rtx6000` | 1x RTX 6000 Ada | 48 GB | 30 | 200 GB | 1.4 TB | $0.80 |
| `gpu_1x_a100` | 1x A100 PCIe | 40 GB | 30 | 200 GB | 512 GB | $1.10 |
| `gpu_1x_a100_sxm4` | 1x A100 SXM4 | 40 GB | 30 | 200 GB | 512 GB | $1.10 |
| `gpu_1x_a100_sxm4_80gb` | 1x A100 SXM4 | **80 GB** | 30 | 200 GB | 1.4 TB | **$1.29** |
| `gpu_1x_h100_pcie` | 1x H100 PCIe | 80 GB | 26 | 200 GB | 512 GB | $1.99 |
| `gpu_1x_h100_sxm5` | 1x H100 SXM5 | 80 GB | 52 | 1000 GB | 2 TB | $2.49 |
| `gpu_2x_a100` | 2x A100 SXM4 | 80 GB (2×40) | 48 | 900 GB | 6 TB | $2.20 |
| `gpu_4x_a100` | 4x A100 SXM4 | 160 GB (4×40) | 120 | 1800 GB | 14 TB | $4.40 |
| `gpu_8x_a100` | 8x A100 SXM4 | 320 GB (8×40) | 240 | 1800 GB | 14 TB | $8.80 |
| `gpu_8x_h100` | 8x H100 SXM5 | 640 GB (8×80) | 416 | 7800 GB | 30 TB | $19.92 |

!!! note "Pricing"
    Prices are approximate and may vary by region and availability. Check Lambda Labs dashboard for current pricing.

---

## Single GPU Instances

### A10 (24 GB) - Budget Option

```yaml
Type: gpu_1x_a10
GPU: 1x NVIDIA A10
VRAM: 24 GB
Price: ~$0.60/hr
```

**Best For:**
- Small models (7-8B parameters)
- Quantized 32B models (INT4)
- Development and testing
- Cost-conscious workloads

**Compatible Models:**
- ✅ Llama 3.1 8B (FP16)
- ✅ Mistral 7B (FP16)
- ✅ Qwen 2.5 Coder 32B (INT4)

**Regions:** Usually good availability in `us-west-1`, `us-east-1`

---

### A6000 / RTX 6000 Ada (48 GB) - Mid-Range

```yaml
Type: gpu_1x_a6000 or gpu_1x_rtx6000
GPU: 1x NVIDIA A6000 or RTX 6000 Ada
VRAM: 48 GB
Price: ~$0.80/hr
```

**Best For:**
- Medium models (30-70B INT4)
- Small multi-GPU experiments
- Professional workstation workloads

**Compatible Models:**
- ✅ DeepSeek-R1 70B (INT4)
- ✅ Llama 3.1 70B (INT4)
- ✅ All smaller models

**Regions:** Limited availability, check `gpu-session available`

---

### A100 40 GB - Standard Data Center

```yaml
Type: gpu_1x_a100 or gpu_1x_a100_sxm4
GPU: 1x NVIDIA A100 (PCIe or SXM4)
VRAM: 40 GB
Price: ~$1.10/hr
```

**Best For:**
- 70B models with tight VRAM (INT4)
- Production inference
- Training small models

**Compatible Models:**
- ✅ DeepSeek-R1 70B (INT4)
- ✅ Llama 3.1 70B (INT4)
- ⚠️ Qwen 2.5 Coder 32B (FP16) - tight fit

**Notes:**
- SXM4 has faster interconnect (useful for multi-GPU)
- PCIe version has slightly lower bandwidth

---

### A100 80 GB - Recommended ⭐

```yaml
Type: gpu_1x_a100_sxm4_80gb
GPU: 1x NVIDIA A100 SXM4
VRAM: 80 GB
Price: ~$1.29/hr
```

**Best For:**
- All 70B models (FP16 and INT4)
- 32B models at full precision (FP16)
- Most flexible option
- Default for `gpu-session`

**Compatible Models:**
- ✅ **All models in registry**
- ✅ Qwen 2.5 Coder 32B (FP16) - recommended
- ✅ DeepSeek-R1 70B (INT4)
- ✅ Code Llama 34B (FP16)

**Regions:** Best availability across all regions

**Why Recommended:**
- 2x VRAM of A100 40GB for only 17% more cost
- Runs all models comfortably
- Good availability

---

### H100 PCIe (80 GB) - Latest Generation

```yaml
Type: gpu_1x_h100_pcie
GPU: 1x NVIDIA H100 PCIe
VRAM: 80 GB
Price: ~$1.99/hr
```

**Best For:**
- Faster inference (2-3x vs A100)
- Production with tight latency requirements
- Latest Transformer Engine features

**Compatible Models:**
- ✅ Same as A100 80GB
- ⚡ 2-3x faster inference

**Notes:**
- Worth the premium for production workloads
- Not necessary for development

---

### H100 SXM5 (80 GB) - Maximum Performance

```yaml
Type: gpu_1x_h100_sxm5
GPU: 1x NVIDIA H100 SXM5
VRAM: 80 GB
Price: ~$2.49/hr
CPU: 52 vCPUs
RAM: 1 TB
```

**Best For:**
- Maximum single-GPU performance
- Large batch sizes
- NVLink for multi-GPU scaling

**Compatible Models:**
- ✅ Same as A100 80GB
- ⚡ 3-4x faster than A100

**Notes:**
- SXM5 has faster interconnect than PCIe
- 2× more CPU cores and RAM than H100 PCIe

---

## Multi-GPU Instances

!!! warning "Multi-GPU Support"
    Multi-GPU instances require distributed inference setup (e.g., vLLM, Ray). Not currently automated in `gpu-session`.

### 2x A100 (80 GB Total)

```yaml
Type: gpu_2x_a100
GPUs: 2x A100 SXM4 (40 GB each)
Total VRAM: 80 GB
Price: ~$2.20/hr
```

**When to Use:**
- Models that need 60-80 GB total
- Cheaper than 1x A100 80GB? No - use single 80GB instead
- Training with data parallelism

---

### 4x A100 (160 GB Total)

```yaml
Type: gpu_4x_a100
GPUs: 4x A100 SXM4 (40 GB each)
Total VRAM: 160 GB
Price: ~$4.40/hr
```

**When to Use:**
- 70B models at FP32 precision
- Large 175B+ models with quantization
- Multi-GPU training

---

### 8x A100 (320 GB Total)

```yaml
Type: gpu_8x_a100
GPUs: 8x A100 SXM4 (40 GB each)
Total VRAM: 320 GB
Price: ~$8.80/hr
```

**When to Use:**
- 175B models (FP16)
- Large-scale training
- Multi-user inference serving

---

### 8x H100 (640 GB Total)

```yaml
Type: gpu_8x_h100
GPUs: 8x H100 SXM5 (80 GB each)
Total VRAM: 640 GB
Price: ~$19.92/hr
CPU: 416 vCPUs
RAM: 7.8 TB
```

**When to Use:**
- Largest models (400B+)
- High-throughput production serving
- Multi-GPU training at scale

---

## GPU Selection Guide

### By Model Size

| Model Size | Recommended GPU | Alternative |
|------------|----------------|-------------|
| 7-8B FP16 | A10 (24 GB) | A6000 (48 GB) |
| 32B INT4 | A10 (24 GB) | A6000 (48 GB) |
| 32B FP16 | A100 (80 GB) | H100 (80 GB) |
| 70B INT4 | A100 (80 GB) | A6000 (48 GB) |
| 70B FP16 | 2x A100 (80 GB) | H100 (80 GB) |

### By Budget

| Budget/hr | GPU Type | Models |
|-----------|----------|--------|
| < $1 | A10 (24 GB) | Small models, INT4 quantized |
| $1-2 | A100 80GB | All common models |
| $2-5 | H100 or 2-4x A100 | Large models, fast inference |
| $5+ | 8x A100/H100 | Multi-GPU production |

### By Use Case

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Development/Testing | A10 (24 GB) | Cheapest, fast iteration |
| Production Inference | A100 80GB | Best price/performance |
| Low Latency | H100 PCIe | 2-3x faster inference |
| Training | Multi-GPU A100 | NVLink, large batches |
| Maximum Performance | H100 SXM5 | Latest tech, fastest |

---

## Availability

GPU availability varies by region and time. Check current availability:

```bash
gpu-session available
```

### Typical Availability (by region)

| Region | A10 | A100 80GB | H100 |
|--------|-----|-----------|------|
| `us-west-1` | ✅ High | ✅ High | ⚠️ Limited |
| `us-east-1` | ✅ High | ✅ High | ⚠️ Limited |
| `us-south-1` | ✅ Medium | ✅ Medium | ❌ Rare |
| `europe-central-1` | ⚠️ Limited | ✅ Medium | ❌ Rare |

!!! tip "Availability Strategy"
    - A100 80GB has best availability across regions
    - H100s are often scarce - check multiple regions
    - A10 is usually available but may have waitlists
    - Multi-GPU instances (4x, 8x) often require scheduling

---

## Cost Examples

### 4-Hour Coding Session

| GPU | Cost | Suitable Models |
|-----|------|-----------------|
| A10 | $2.40 | Llama 8B, Qwen 32B INT4 |
| A100 80GB | $5.16 | All models |
| H100 PCIe | $7.96 | All models, faster |

### Full Day (8 hours)

| GPU | Cost | Suitable Models |
|-----|------|-----------------|
| A10 | $4.80 | Small models |
| A100 80GB | $10.32 | All models |
| H100 PCIe | $15.92 | All models, production |

### Weekly Development (40 hours)

| GPU | Cost | Suitable Models |
|-----|------|-----------------|
| A10 | $24 | Budget coding |
| A100 80GB | $51.60 | Professional use |
| H100 PCIe | $79.60 | High performance |

---

## GPU Specifications Deep Dive

### Compute Architecture

| GPU | Architecture | CUDA Cores | Tensor Cores | TDP |
|-----|-------------|-----------|--------------|-----|
| A10 | Ampere | 9,216 | 288 (3rd gen) | 150W |
| A6000 | Ampere | 10,752 | 336 (3rd gen) | 300W |
| RTX 6000 Ada | Ada Lovelace | 18,176 | 568 (4th gen) | 300W |
| A100 | Ampere | 6,912 | 432 (3rd gen) | 400W |
| H100 | Hopper | 16,896 | 528 (4th gen) | 700W |

### Memory Bandwidth

| GPU | Memory Type | Bandwidth | ECC |
|-----|------------|-----------|-----|
| A10 | GDDR6 | 600 GB/s | Yes |
| A6000 | GDDR6 | 768 GB/s | Yes |
| RTX 6000 Ada | GDDR6 | 960 GB/s | Yes |
| A100 40GB | HBM2e | 1,555 GB/s | Yes |
| A100 80GB | HBM2e | 2,039 GB/s | Yes |
| H100 | HBM3 | 3,350 GB/s | Yes |

### Inference Performance (relative)

| GPU | FP16 | INT8 | INT4 |
|-----|------|------|------|
| A10 | 1.0× | 1.0× | 1.0× |
| A100 | 1.5× | 2.0× | - |
| H100 | 3.0× | 4.0× | 6.0× |

*Performance relative to A10 baseline*

---

## Multi-GPU Interconnects

### PCIe (Standard)

- **Bandwidth**: 64 GB/s (PCIe 4.0 x16)
- **Use case**: Single GPU or CPU-bound workloads
- **GPUs**: A10, A6000, RTX 6000, H100 PCIe

### NVLink (A100 SXM4)

- **Bandwidth**: 600 GB/s (12 NVLink lanes)
- **Use case**: Multi-GPU training, large models
- **GPUs**: A100 SXM4 in multi-GPU configs

### NVLink 4 (H100 SXM5)

- **Bandwidth**: 900 GB/s (18 NVLink lanes)
- **Use case**: Highest multi-GPU performance
- **GPUs**: H100 SXM5 in multi-GPU configs

---

## Choosing the Right GPU

### Decision Tree

```
Need model > 70B?
├─ Yes → Multi-GPU or wait for larger models
└─ No
    ├─ Need FP16 precision for 32B model?
    │   └─ Yes → A100 80GB
    └─ No
        ├─ Budget < $1/hr?
        │   └─ Yes → A10 (use INT4 models)
        └─ No
            ├─ Need fastest inference?
            │   └─ Yes → H100
            └─ No → A100 80GB (best value)
```

### Common Mistakes

❌ **Using A100 40GB for Qwen 32B FP16**
- Too tight, may OOM
- Use A100 80GB instead

❌ **Using H100 for development**
- 2× cost for minimal benefit in dev
- Use A100 80GB instead

❌ **Using 2x A100 for 70B INT4**
- Doesn't need multi-GPU
- Use 1x A100 80GB instead

❌ **Using A10 for DeepSeek-R1 FP16**
- Won't fit (needs 140+ GB)
- Use A100 80GB with INT4

---

## Frequently Asked Questions

### Can I use multiple GPUs for one model?

Yes, but requires setup:
- vLLM supports tensor parallelism
- Ray supports pipeline parallelism
- Not currently automated in `gpu-session`

### What's the difference between PCIe and SXM?

- **PCIe**: Plugs into motherboard slot, lower bandwidth
- **SXM**: Direct socket, higher bandwidth, NVLink support
- For single GPU, minimal difference
- For multi-GPU, SXM much faster

### Should I get H100 over A100?

**Get H100 if:**
- Production workload with tight latency SLA
- Need maximum throughput
- Budget allows

**Get A100 if:**
- Development/testing
- Cost-conscious
- 2-3x inference speed sufficient

### Why is A100 80GB only 17% more than 40GB?

Lambda Labs prices by total cost of ownership. 80GB variant has:
- 2× VRAM
- 31% higher memory bandwidth
- Better availability

It's the best value in their lineup.

### What about RTX 4090 or consumer GPUs?

Lambda Labs only offers professional/data center GPUs:
- Better reliability (ECC memory)
- Official driver support
- Better multi-GPU scaling
- Data center warranties

---

## See Also

- [Model Registry](models.md) - Which models fit on which GPUs
- [CLI Commands](cli-commands.md) - `available` and `start` commands
- [Configuration](configuration-file.md) - Setting default GPU type
- [Lambda Labs Instance Types](https://lambdalabs.com/service/gpu-cloud) - Official specs
