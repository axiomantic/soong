# Installation

This guide covers installing GPU Session CLI on your local machine.

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
    GPU Session CLI requires Python 3.10 or later. If you have an older version, [download the latest Python](https://www.python.org/downloads/) before proceeding.

---

## Installation Methods

### Option 1: Install from Source (Recommended)

Clone the repository and install in development mode:

```bash
# Clone the repository
git clone https://github.com/yourusername/gpu-session.git
cd gpu-session

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with all dependencies
pip install -e .
```

### Option 2: Install from PyPI (Coming Soon)

Once published to PyPI, you'll be able to install with:

```bash
pip install gpu-session
```

---

## Verify Installation

After installation, verify that GPU Session CLI is working:

```bash
gpu-session --version
```

**Expected Output**:
```
gpu-session version 1.0.0
```

### Run the Help Command

```bash
gpu-session --help
```

**Expected Output**:
```
Usage: gpu-session [OPTIONS] COMMAND [ARGS]...

  GPU Session CLI - Manage Lambda Labs GPU instances

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  configure  Configure GPU Session CLI with Lambda Labs credentials
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
    If you see the help output, GPU Session CLI is installed correctly!

---

## Troubleshooting

### "command not found: gpu-session"

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
pip install -e .

# Option 2: User installation
pip install --user -e .
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

To uninstall GPU Session CLI:

```bash
pip uninstall gpu-session
```

---

## Next Steps

Now that GPU Session CLI is installed, proceed to **[Configuration](configuration.md)** to set up your Lambda Labs credentials.

---

!!! tip "Using Virtual Environments"
    We strongly recommend using Python virtual environments to avoid dependency conflicts. Learn more in the [Python venv documentation](https://docs.python.org/3/library/venv.html).
