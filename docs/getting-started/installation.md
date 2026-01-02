# Installation

This guide covers installing Soong CLI on your local machine.

---

## System Requirements

Before installing, verify your system meets these requirements:

| Requirement | Minimum Version |
|------------|----------------|
| **Python** | 3.10 or later |
| **pip** | 21.0 or later |
| **Operating System** | Linux, macOS, or Windows (WSL) |

---

## Check Python Version

Verify you have Python 3.10 or later installed:

```bash
python --version
# or
python3 --version
```

**Expected Output**:
```
Python 3.10.0  # or later
```

!!! warning "Python Version"
    Soong CLI requires Python 3.10 or later. If you have an older version, [download the latest Python](https://www.python.org/downloads/) before proceeding.

---

## Installation Methods

### Option 1: Install from Source (Recommended)

Clone the repository and install in development mode:

```bash
# Clone the repository
git clone https://github.com/axiomantic/soong.git
cd soong

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the CLI
pip install -e ./cli
```

!!! note "Project Structure"
    Soong is a monorepo containing multiple components (CLI, dashboard, worker). The Python CLI lives in the `cli/` subdirectory, which is why you install from `./cli` rather than the repository root.

### Option 2: Install from PyPI (Coming Soon)

Once published to PyPI, you'll be able to install with:

```bash
pip install soong
```

---

## Verify Installation

After installation, verify that Soong CLI is working:

```bash
soong --version
```

**Expected Output**:
```
soong version 1.0.0
```

### Run the Help Command

```bash
soong --help
```

**Expected Output**:
```
Usage: soong [OPTIONS] COMMAND [ARGS]...

  Soong CLI - Manage Lambda Labs GPU instances

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  configure  Configure Soong CLI with Lambda Labs credentials
  start      Start a new GPU instance
  status     Show current instance status
  extend     Extend instance runtime
  stop       Stop the current instance
  ssh        SSH into the running instance
  tunnel     Create SSH tunnels to instance ports
  available  List available instance types
  models     List and search available models
```

!!! success "Installation Complete"
    If you see the help output, Soong CLI is installed correctly!

---

## Troubleshooting

### "command not found: soong"

**Cause**: The installation directory isn't in your PATH.

**Solution**:

=== "Linux/macOS"

    ```bash
    # If installed with --user flag
    export PATH="$HOME/.local/bin:$PATH"

    # Add to your shell profile (~/.bashrc or ~/.zshrc)
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    ```

=== "Windows (PowerShell)"

    ```powershell
    # Check if Scripts directory is in PATH
    $env:Path

    # If not, add it to your user PATH through System Properties
    # or use a virtual environment
    ```

### "pip: command not found"

**Solution**: Install pip for your Python version:

```bash
# Linux/macOS
python3 -m ensurepip --upgrade

# Or use your package manager
sudo apt install python3-pip  # Debian/Ubuntu
brew install python3  # macOS with Homebrew
```

### Installation fails with permission errors

**Solution**: Use a virtual environment or install with the `--user` flag:

```bash
# Option 1: Virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install -e ./cli

# Option 2: User installation
pip install --user -e ./cli
```

### Dependencies fail to install

**Solution**: Make sure you have build tools installed:

=== "Debian/Ubuntu"

    ```bash
    sudo apt update
    sudo apt install python3-dev build-essential
    ```

=== "macOS"

    ```bash
    xcode-select --install
    ```

=== "Windows"

    Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

---

## Uninstalling

To uninstall Soong CLI:

```bash
pip uninstall soong
```

---

## Next Steps

Now that Soong CLI is installed, proceed to **[Configuration](configuration.md)** to set up your Lambda Labs credentials.

---

!!! tip "Using Virtual Environments"
    We strongly recommend using Python virtual environments to avoid dependency conflicts. Learn more in the [Python venv documentation](https://docs.python.org/3/library/venv.html).
