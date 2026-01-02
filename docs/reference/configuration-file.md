# Configuration File Reference

Complete reference for the `gpu-session` YAML configuration file.

## File Location

```
~/.config/gpu-dashboard/config.yaml
```

## File Permissions

The configuration file is automatically created with `0600` permissions (owner read/write only) to protect sensitive data like API keys.

```bash
# Check permissions
ls -l ~/.config/gpu-dashboard/config.yaml
# Should show: -rw------- 1 user user ...
```

## Configuration Schema

### Complete Example

```yaml
# Lambda Labs API Configuration
lambda:
  api_key: sk_1234567890abcdef1234567890abcdef
  default_region: us-west-1
  filesystem_name: coding-stack

# Status Daemon Configuration
status_daemon:
  token: abc123xyz789_secure_token_here
  port: 8080

# Default Session Settings
defaults:
  model: deepseek-r1-70b
  gpu: gpu_1x_a100_sxm4_80gb
  lease_hours: 4

# SSH Configuration
ssh:
  key_path: ~/.ssh/id_rsa

# Custom Models (optional)
custom_models:
  my-custom-model:
    hf_path: myorg/my-model-70b
    params_billions: 70
    quantization: int4
    context_length: 8192
    notes: My custom fine-tuned model
```

---

## Section Reference

### `lambda`

Lambda Labs API credentials and defaults.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `api_key` | String | **Yes** | - | Lambda Labs API key (starts with `sk_`) |
| `default_region` | String | No | `us-west-1` | Default region for launching instances |
| `filesystem_name` | String | No | `coding-stack` | Persistent filesystem to attach |

**Example:**

```yaml
lambda:
  api_key: sk_1234567890abcdef1234567890abcdef
  default_region: us-east-1
  filesystem_name: my-projects
```

**Notes:**

- Get your API key at: https://cloud.lambdalabs.com/api-keys
- Available regions: `us-west-1`, `us-east-1`, `us-south-1`, `us-midwest-1`, `europe-central-1`, `asia-northeast-1`, etc.
- Filesystem must exist in your Lambda Labs account

---

### `status_daemon`

Configuration for the status daemon running on instances.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `token` | String | **Yes** | - | Shared secret for daemon authentication |
| `port` | Integer | No | `8080` | Port daemon listens on |

**Example:**

```yaml
status_daemon:
  token: my_secure_random_token_here
  port: 8080
```

**Notes:**

- Token is auto-generated during `configure` if left blank
- Use a long random string (at least 32 characters)
- Token authenticates CLI commands like `extend`
- Port must not conflict with other services (SGLang uses 8000, n8n uses 5678)

---

### `defaults`

Default settings for new instances.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | String | No | `deepseek-r1-70b` | Default model to load |
| `gpu` | String | No | `gpu_1x_a100_sxm4_80gb` | Default GPU type |
| `lease_hours` | Integer | No | `4` | Default lease duration in hours |

**Example:**

```yaml
defaults:
  model: qwen2.5-coder-32b
  gpu: gpu_1x_a6000
  lease_hours: 6
```

**Valid GPU Types:**

See [GPU Types Reference](gpu-types.md) for complete list.

**Valid Models:**

See [Model Registry](models.md) for built-in models, or use custom model IDs from `custom_models` section.

**Lease Hours:**

- Minimum: 1 hour
- Maximum: 8 hours (Lambda Labs limit)
- Can be extended later with `gpu-session extend`

---

### `ssh`

SSH connection settings.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `key_path` | String | No | `~/.ssh/id_rsa` | Path to SSH private key |

**Example:**

```yaml
ssh:
  key_path: ~/.ssh/lambda_labs_key
```

**Notes:**

- Key must be registered in your Lambda Labs account: https://cloud.lambdalabs.com/ssh-keys
- Supports `~` expansion for home directory
- Key must have correct permissions (0600)

---

### `custom_models`

Define custom models not in the built-in registry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hf_path` | String | **Yes** | HuggingFace model path |
| `params_billions` | Float | **Yes** | Parameter count in billions |
| `quantization` | String | **Yes** | Quantization: `fp32`, `fp16`, `bf16`, `int8`, `int4` |
| `context_length` | Integer | **Yes** | Context window size (≥ 512) |
| `name` | String | No | Model name for display |
| `notes` | String | No | Description or usage notes |

**Example:**

```yaml
custom_models:
  my-llama-70b-finetune:
    hf_path: myorg/llama-70b-custom
    params_billions: 70
    quantization: int4
    context_length: 8192
    name: My Custom Llama 70B
    notes: Fine-tuned on domain-specific data

  small-test-model:
    hf_path: test/tiny-model
    params_billions: 1.5
    quantization: fp16
    context_length: 2048
```

**Quantization Values:**

| Value | Bytes/Param | Use Case |
|-------|-------------|----------|
| `fp32` | 4.0 | Maximum precision (rarely needed) |
| `fp16` | 2.0 | Standard precision, good quality |
| `bf16` | 2.0 | Brain float, similar to FP16 |
| `int8` | 1.0 | Quantized, some quality loss |
| `int4` | 0.5 | GPTQ/AWQ, 2x memory savings |

**Managing Custom Models:**

```bash
# Add via CLI (interactive)
gpu-session models add

# Add via CLI (flags)
gpu-session models add --name my-model --hf-path org/model --params 70 --quantization int4 --context 8192

# Remove custom model
gpu-session models remove my-model

# List all models (shows custom ones too)
gpu-session models
```

---

## Validation Rules

The configuration is validated on load:

### API Key

- Must be non-empty string
- Typically starts with `sk_`
- Validated by attempting API call during `configure`

### Status Daemon Token

- Must be non-empty string
- Recommended: at least 32 characters
- Auto-generated during `configure` using `secrets.token_urlsafe(32)`

### GPU Type

- Must match Lambda Labs GPU names
- Checked against available instance types

### Lease Hours

- Must be integer
- Between 1 and 8 hours (Lambda Labs limit)

### Custom Model Fields

- `params_billions`: Must be positive number
- `context_length`: Must be ≥ 512
- `quantization`: Must be one of: `fp32`, `fp16`, `bf16`, `int8`, `int4`

---

## Example Configurations

### Minimal Configuration

```yaml
lambda:
  api_key: sk_1234567890abcdef1234567890abcdef

status_daemon:
  token: auto_generated_token_here
```

All other fields use defaults.

---

### Budget-Conscious Setup

```yaml
lambda:
  api_key: sk_1234567890abcdef1234567890abcdef
  default_region: us-west-1
  filesystem_name: shared-workspace

status_daemon:
  token: my_secure_token

defaults:
  model: llama-3.1-8b          # Cheapest model
  gpu: gpu_1x_a10              # Cheapest GPU
  lease_hours: 2               # Short sessions

ssh:
  key_path: ~/.ssh/id_rsa
```

---

### Power User Setup

```yaml
lambda:
  api_key: sk_1234567890abcdef1234567890abcdef
  default_region: us-east-1
  filesystem_name: ml-projects

status_daemon:
  token: super_secure_64_char_token_here_for_production_use_12345678
  port: 8080

defaults:
  model: deepseek-r1-70b       # Best reasoning
  gpu: gpu_1x_h100_pcie        # Fastest GPU
  lease_hours: 8               # Maximum allowed

ssh:
  key_path: ~/.ssh/lambda_dedicated

custom_models:
  my-finetune-70b:
    hf_path: myorg/llama-70b-code-finetune
    params_billions: 70
    quantization: int4
    context_length: 16384
    notes: Fine-tuned on internal codebase

  test-model:
    hf_path: test/small-debug-model
    params_billions: 7
    quantization: fp16
    context_length: 4096
```

---

## Editing Configuration

### Manual Editing

```bash
# Open in default editor
${EDITOR:-nano} ~/.config/gpu-dashboard/config.yaml

# Validate after editing
gpu-session status
```

### Via CLI

```bash
# Re-run configuration wizard
gpu-session configure

# Add custom models
gpu-session models add

# Remove custom models
gpu-session models remove my-model
```

---

## Troubleshooting

### Invalid API Key

**Symptom:** `Error: Invalid API key`

**Solution:**

1. Check key at: https://cloud.lambdalabs.com/api-keys
2. Ensure no extra whitespace in YAML
3. Re-run `gpu-session configure`

### Filesystem Not Found

**Symptom:** Launch fails with filesystem error

**Solution:**

1. Check filesystem name at: https://cloud.lambdalabs.com/file-systems
2. Update `lambda.filesystem_name` in config
3. Or create filesystem in Lambda Labs dashboard

### SSH Permission Denied

**Symptom:** Cannot SSH to instance

**Solution:**

1. Check SSH key registered: https://cloud.lambdalabs.com/ssh-keys
2. Verify `ssh.key_path` points to correct private key
3. Check key permissions: `chmod 600 ~/.ssh/id_rsa`

### Invalid Custom Model

**Symptom:** `Warning: Invalid custom model`

**Solution:**

1. Check all required fields present
2. Verify `quantization` is valid value
3. Ensure `params_billions` is positive number
4. Ensure `context_length` ≥ 512

---

## Security Best Practices

1. **Never commit config to git**
   ```bash
   echo "~/.config/gpu-dashboard/config.yaml" >> ~/.gitignore
   ```

2. **Use environment variables for CI/CD**
   ```bash
   # Don't store API keys in config for CI
   # Use Lambda Labs API directly or secure secrets management
   ```

3. **Rotate tokens periodically**
   - Regenerate `status_daemon.token` every few months
   - Update instances with new token

4. **Restrict file permissions**
   ```bash
   chmod 600 ~/.config/gpu-dashboard/config.yaml
   ```

5. **Use dedicated SSH keys**
   - Don't use your primary SSH key
   - Create Lambda-specific key: `ssh-keygen -t ed25519 -f ~/.ssh/lambda_labs`
