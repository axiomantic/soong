# Configuration

After installing GPU Session CLI, you'll need to configure it with your Lambda Labs credentials and preferences.

---

## Running the Configuration Wizard

GPU Session CLI includes an interactive configuration wizard that guides you through setup:

```bash
gpu-session configure
```

The wizard will prompt you for the following information:

1. Lambda Labs API key
2. SSH private key path
3. Persistent filesystem name (optional)
4. Default instance type
5. Default region
6. Default maximum runtime hours

---

## Configuration Parameters

### Lambda Labs API Key

**Prompt**: `Enter your Lambda Labs API key:`

**Description**: Your Lambda Labs API key for authentication.

**Example**: `lam_1234567890abcdefghijklmnopqrstuvwxyz`

**Where to find it**: [cloud.lambdalabs.com](https://cloud.lambdalabs.com) → Account Settings → API Keys

!!! danger "Security Warning"
    Your API key will be stored in `~/.config/gpu-dashboard/config.yaml` with restricted permissions (0600). Never share this file or commit it to version control.

---

### SSH Private Key Path

**Prompt**: `Enter path to your SSH private key:`

**Description**: Path to your SSH private key file (the key pair you uploaded to Lambda Labs).

**Default**: `~/.ssh/id_ed25519`

**Example**: `/home/user/.ssh/id_ed25519`

**Validation**: The wizard verifies that:
- The file exists
- The file has correct permissions (0600)
- The file is a valid private key

!!! tip "SSH Key Permissions"
    SSH requires private keys to have restrictive permissions. The wizard will warn you if permissions are too open and offer to fix them automatically.

---

### Persistent Filesystem Name

**Prompt**: `Enter persistent filesystem name (optional):`

**Description**: Name of your Lambda Labs persistent filesystem. If provided, this filesystem will be automatically attached to launched instances.

**Example**: `ml-workspace`

**Optional**: Press Enter to skip if you don't have a persistent filesystem.

**Where to find it**: [cloud.lambdalabs.com](https://cloud.lambdalabs.com) → Storage → Filesystems

---

### Default Instance Type

**Prompt**: `Enter default instance type (e.g., gpu_1x_a10):`

**Description**: The GPU instance type to use by default when launching instances.

**Default**: `gpu_1x_a10`

**Common Options**:
- `gpu_1x_a10` - Single A10 GPU (24GB VRAM)
- `gpu_1x_a100` - Single A100 GPU (40GB VRAM)
- `gpu_1x_h100_pcie` - Single H100 GPU (80GB VRAM)

**See all options**: Run `gpu-session available` after configuration

!!! tip "Choosing an Instance Type"
    Start with `gpu_1x_a10` for smaller models. You can override this when launching instances with the `--instance-type` flag.

---

### Default Region

**Prompt**: `Enter default region (e.g., us-west-1):`

**Description**: The Lambda Labs region where instances will be launched by default.

**Default**: `us-west-1`

**Common Options**:
- `us-west-1` - US West (California)
- `us-east-1` - US East (Virginia)
- `us-south-1` - US South (Texas)
- `europe-central-1` - Europe (Germany)

!!! warning "Filesystem Region"
    If using a persistent filesystem, make sure to select the same region where your filesystem is located.

---

### Default Max Hours

**Prompt**: `Enter default maximum runtime hours (0 for unlimited):`

**Description**: Maximum number of hours an instance can run before automatically stopping. This helps prevent unexpected costs.

**Default**: `2`

**Example**: `4` (instance stops after 4 hours)

**Unlimited**: Enter `0` for no time limit

!!! tip "Cost Control"
    Setting a default max hours helps prevent forgetting to stop instances. You can always extend the runtime with `gpu-session extend`.

---

## Configuration File Location

Your configuration is stored in:

```
~/.config/gpu-dashboard/config.yaml
```

**Permissions**: `0600` (read/write for owner only)

### Example Configuration File

```yaml
lambda_api_key: lam_1234567890abcdefghijklmnopqrstuvwxyz
ssh_private_key_path: /home/user/.ssh/id_ed25519
persistent_filesystem_name: ml-workspace
default_instance_type: gpu_1x_a10
default_region: us-west-1
default_max_hours: 2
```

---

## Reconfiguring

To update your configuration, run the wizard again:

```bash
gpu-session configure
```

The wizard will display your current values and allow you to change them.

### Manual Configuration

Advanced users can edit the configuration file directly:

```bash
# Open configuration in your default editor
nano ~/.config/gpu-dashboard/config.yaml

# Or use your preferred editor
vim ~/.config/gpu-dashboard/config.yaml
code ~/.config/gpu-dashboard/config.yaml
```

!!! warning "Manual Editing"
    If you edit the configuration manually, make sure the file permissions remain `0600`:
    ```bash
    chmod 0600 ~/.config/gpu-dashboard/config.yaml
    ```

---

## Verifying Configuration

After configuration, verify your settings:

```bash
# Check that you can list available instance types
gpu-session available

# Check that you can list models
gpu-session models --limit 5
```

**Expected Output**:
```
Available instance types:
- gpu_1x_a10 (24GB VRAM) - $0.60/hr
- gpu_1x_a100 (40GB VRAM) - $1.10/hr
...

Available models:
- meta-llama/Llama-2-7b-hf
- mistralai/Mistral-7B-v0.1
...
```

!!! success "Configuration Complete"
    If you see instance types and models, your configuration is working correctly!

---

## Troubleshooting

### "Invalid API key"

**Cause**: The API key is incorrect or has been revoked.

**Solution**:
1. Go to [cloud.lambdalabs.com](https://cloud.lambdalabs.com) → Account Settings → API Keys
2. Generate a new API key
3. Run `gpu-session configure` and enter the new key

---

### "SSH key not found"

**Cause**: The specified SSH key path doesn't exist.

**Solution**:
1. Verify the path is correct: `ls -la ~/.ssh/`
2. If the key doesn't exist, generate one: `ssh-keygen -t ed25519`
3. Upload the public key to Lambda Labs
4. Run `gpu-session configure` with the correct path

---

### "Permission denied" when accessing config file

**Cause**: The configuration file has incorrect permissions.

**Solution**:
```bash
# Fix permissions
chmod 0600 ~/.config/gpu-dashboard/config.yaml
```

---

### "Filesystem not found"

**Cause**: The specified filesystem name doesn't exist or is in a different region.

**Solution**:
1. Check your filesystems: [cloud.lambdalabs.com](https://cloud.lambdalabs.com) → Storage → Filesystems
2. Verify the name matches exactly
3. If using a filesystem, make sure your default region matches the filesystem region
4. Run `gpu-session configure` to update the settings

---

## Next Steps

Now that GPU Session CLI is configured, proceed to the **[Quick Start Guide](quick-start.md)** to launch your first GPU instance!

---

!!! tip "Configuration Best Practices"
    - Use a short max hours default (2-4 hours) to prevent unexpected costs
    - Store your API key securely—treat it like a password
    - Use a persistent filesystem for any data you want to keep across sessions
    - Choose a region close to you for better SSH latency
