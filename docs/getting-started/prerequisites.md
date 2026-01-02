# Prerequisites

Before installing Soong CLI, you'll need to set up your Lambda Labs account and gather the required credentials.

---

## 1. Create a Lambda Labs Account

If you don't already have a Lambda Labs account:

1. Go to [cloud.lambdalabs.com](https://cloud.lambdalabs.com)
2. Click **Sign Up** and create an account
3. Verify your email address
4. Add a payment method to your account

!!! warning "Payment Method Required"
    Lambda Labs requires a valid payment method before you can launch GPU instances. Make sure to add your payment information in the account settings.

---

## 2. Generate an API Key

Soong CLI uses the Lambda Labs API to manage instances. You'll need an API key to authenticate.

### Steps to Generate an API Key

1. Log in to [cloud.lambdalabs.com](https://cloud.lambdalabs.com)
2. Navigate to **Account Settings** → **API Keys**
3. Click **Generate New API Key**
4. Copy the API key immediately—you won't be able to see it again
5. Store the API key securely (you'll need it during configuration)

!!! danger "Keep Your API Key Secret"
    Your API key provides full access to your Lambda Labs account. Never share it or commit it to version control.

### Example API Key Format

```
lam_1234567890abcdefghijklmnopqrstuvwxyz
```

---

## 3. Create and Upload SSH Keys (Optional)

Soong CLI uses SSH to connect to your instances. If you don't have an SSH key uploaded to Lambda Labs, Soong will detect this when you try to launch an instance and prompt you to add one.

!!! tip "You can skip this step"
    Soong will check for SSH keys when launching and guide you if none are found.

### Generate an SSH Key Pair (if you don't have one)

=== "Linux/macOS"

    ```bash
    # Generate a new SSH key pair
    ssh-keygen -t ed25519 -C "your_email@example.com"

    # Press Enter to save to the default location (~/.ssh/id_ed25519)
    # Optionally set a passphrase for extra security

    # Display your public key
    cat ~/.ssh/id_ed25519.pub
    ```

=== "Windows (PowerShell)"

    ```powershell
    # Generate a new SSH key pair
    ssh-keygen -t ed25519 -C "your_email@example.com"

    # Press Enter to save to the default location
    # Optionally set a passphrase for extra security

    # Display your public key
    Get-Content ~\.ssh\id_ed25519.pub
    ```

### Upload SSH Key to Lambda Labs

1. Log in to [cloud.lambdalabs.com](https://cloud.lambdalabs.com)
2. Navigate to **Account Settings** → **SSH Keys**
3. Click **Add SSH Key**
4. Paste your **public key** (the content of `id_ed25519.pub`)
5. Give it a memorable name (e.g., "My Laptop")
6. Click **Save**

!!! warning "Public Key Only"
    Upload your **public key** (`id_ed25519.pub`), NOT your private key (`id_ed25519`). Never share your private key with anyone.

---

## 4. Create a Persistent Filesystem (Recommended)

Lambda Labs instances are ephemeral—when stopped, all data is lost. A persistent filesystem preserves your data across instances.

### Why Use a Persistent Filesystem?

- **Preserve models**: Downloaded models persist across sessions
- **Save work**: Code, datasets, and results aren't lost
- **Faster startup**: No need to re-download dependencies

### Create a Persistent Filesystem

1. Log in to [cloud.lambdalabs.com](https://cloud.lambdalabs.com)
2. Navigate to **Storage** → **Filesystems**
3. Click **Create Filesystem**
4. Choose a region (must match your instance region)
5. Set the size (recommended: 512GB or larger for ML models)
6. Name your filesystem (e.g., "ml-workspace")
7. Click **Create**

!!! tip "Filesystem Naming"
    Use a descriptive name—you'll reference it during Soong CLI configuration.

### Filesystem Costs

Persistent filesystems are charged separately from instances:

- **Cost**: ~$0.20/GB/month
- **Example**: 512GB filesystem = ~$100/month

---

## 5. Verify Prerequisites

Before proceeding, make sure you have:

- [x] Lambda Labs account with verified email
- [x] Payment method added to your account
- [x] Lambda Labs API key generated and saved
- [ ] SSH key pair (optional - Soong will prompt when needed)
- [x] Persistent filesystem created (optional but recommended)

---

## Next Steps

Once you've completed all prerequisites, proceed to **[Installation](installation.md)** to install Soong CLI.

---

## Troubleshooting

### "Unable to generate API key"

**Solution**: Make sure you've verified your email address and added a payment method to your account.

### "SSH key upload failed"

**Solution**: Verify you're uploading your **public key** (`id_ed25519.pub`), not your private key. The public key should start with `ssh-ed25519` or `ssh-rsa`.

### "Filesystem creation unavailable in my region"

**Solution**: Persistent filesystems are only available in certain Lambda Labs regions. Choose a region that supports filesystems, then launch instances in that same region.

---

!!! info "Lambda Labs Documentation"
    For more details on Lambda Labs features, see the [official Lambda Labs documentation](https://docs.lambdalabs.com).
