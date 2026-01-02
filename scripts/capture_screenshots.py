#!/usr/bin/env python3
"""
Capture terminal screenshots as SVG using Rich.

Usage:
    python scripts/capture_screenshots.py

Outputs SVG files to docs/assets/screenshots/
"""

import sys
from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Add cli/src to path for imports
CLI_SRC = Path(__file__).parent.parent / "cli" / "src"
sys.path.insert(0, str(CLI_SRC))

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "assets" / "screenshots"


def capture_help(filename: str = "help"):
    """Capture main help screen."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    console = Console(record=True, width=85, force_terminal=True)

    # Recreate the help output with Rich
    console.print()
    console.print(Text(" Usage: soong [OPTIONS] COMMAND [ARGS]...", style="bold"))
    console.print()
    console.print(" GPU session management for Lambda Labs")
    console.print()

    # Options panel
    options = Table.grid(padding=(0, 2))
    options.add_column(style="cyan bold")
    options.add_column()
    options.add_row("--help", "Show this message and exit.")
    console.print(Panel(options, title="Options", border_style="dim", padding=(0, 1)))

    # Commands panel
    commands = Table.grid(padding=(0, 2))
    commands.add_column(style="cyan bold", width=12)
    commands.add_column()
    commands.add_row("configure", "Interactive configuration wizard.")
    commands.add_row("start", "Launch new GPU instance with cloud-init.")
    commands.add_row("status", "Show status of running instances.")
    commands.add_row("extend", "Extend instance lease.")
    commands.add_row("stop", "Terminate instance.")
    commands.add_row("ssh", "SSH into instance.")
    commands.add_row("available", "Show available GPU types and models.")
    commands.add_row("models", "Manage AI models")
    commands.add_row("tunnel", "Manage SSH tunnels")
    console.print(Panel(commands, title="Commands", border_style="dim", padding=(0, 1)))

    svg_path = OUTPUT_DIR / f"{filename}.svg"
    console.save_svg(str(svg_path), title="soong --help")
    print(f"Saved: {svg_path}")


def capture_model_info(filename: str = "model-info"):
    """Capture model info screen."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    console = Console(record=True, width=80, force_terminal=True)

    # Model header
    console.print(Panel("DeepSeek-R1 70B", border_style="cyan", padding=(0, 1)))
    console.print()

    # Model details
    console.print("[bold]HuggingFace Path:[/bold] deepseek-ai/DeepSeek-R1-Distill-Llama-70B")
    console.print("[bold]Parameters:[/bold] 70B")
    console.print("[bold]Quantization:[/bold] INT4")
    console.print("[bold]Context Length:[/bold] [cyan]8,192[/cyan] tokens")
    console.print()

    # VRAM breakdown
    console.print("[bold]VRAM Breakdown:[/bold]")
    console.print("  Base weights:       [cyan]35.0[/cyan] GB")
    console.print("  KV cache:            [cyan]4.0[/cyan] GB")
    console.print("  Overhead:            [cyan]2.0[/cyan] GB")
    console.print("  Activations:         [cyan]3.5[/cyan] GB")
    console.print("  [cyan]Total estimated:    [/cyan][cyan]44.5[/cyan][cyan] GB[/cyan]")
    console.print()

    console.print("[bold]Recommended GPU:[/bold] 1x A100 SXM4 ([cyan]80[/cyan] GB)")
    console.print()

    # Good for
    console.print("[green bold]Good for:[/green bold]")
    console.print("  [dim]\u2022[/dim] Complex multi-step reasoning")
    console.print("  [dim]\u2022[/dim] Debugging difficult issues")
    console.print("  [dim]\u2022[/dim] Architecture decisions")
    console.print("  [dim]\u2022[/dim] Code review with explanations")
    console.print()

    # Not good for
    console.print("[yellow bold]Not good for:[/yellow bold]")
    console.print("  [dim]\u2022[/dim] Simple/quick tasks (overkill)")
    console.print("  [dim]\u2022[/dim] Long context windows (8K limit)")
    console.print("  [dim]\u2022[/dim] Speed-critical applications")
    console.print()

    console.print("[bold]Notes:[/bold] Chain-of-thought reasoning. Slower but more accurate.")

    svg_path = OUTPUT_DIR / f"{filename}.svg"
    console.save_svg(str(svg_path), title="soong models info deepseek-r1-70b")
    print(f"Saved: {svg_path}")


def capture_available(filename: str = "available"):
    """Capture available GPUs screen."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    console = Console(record=True, width=95, force_terminal=True)

    # Create GPU table
    table = Table(title="Available GPU Types")
    table.add_column("GPU Type", style="cyan")
    table.add_column("Description", style="dim")
    table.add_column("Price", style="yellow")
    table.add_column("Regions", style="green")

    # Sample GPU data
    gpus = [
        ("gpu_1x_h100_sxm5", "1x H100 (80 GB SXM5)", "$3.29/hr", "us-south-2, us-south-3"),
        ("gpu_1x_h100_pcie", "1x H100 (80 GB PCIe)", "$2.49/hr", "us-west-3"),
        ("gpu_1x_a100_sxm4", "1x A100 (80 GB SXM4)", "$1.99/hr", "us-east-1, us-west-2"),
        ("gpu_1x_gh200", "1x GH200 (96 GB)", "$1.49/hr", "[dim]-[/dim]"),
        ("gpu_1x_a100", "1x A100 (40 GB PCIe)", "$1.29/hr", "[dim]-[/dim]"),
        ("gpu_1x_a6000", "1x A6000 (48 GB)", "$0.80/hr", "[dim]-[/dim]"),
        ("gpu_1x_a10", "1x A10 (24 GB PCIe)", "$0.75/hr", "us-east-1, us-west-1"),
        ("gpu_1x_rtx6000", "1x RTX 6000 (24 GB)", "$0.50/hr", "[dim]-[/dim]"),
    ]

    for gpu in gpus:
        table.add_row(*gpu)

    console.print(table)
    console.print()
    console.print("[cyan]Recommended Models:[/cyan]")
    console.print("  deepseek-r1-70b (requires A100 80GB)")
    console.print("  qwen2.5-coder-32b (works on RTX 6000)")

    svg_path = OUTPUT_DIR / f"{filename}.svg"
    console.save_svg(str(svg_path), title="soong available")
    print(f"Saved: {svg_path}")


def capture_start_help(filename: str = "start-help"):
    """Capture start command help."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    console = Console(record=True, width=85, force_terminal=True)

    console.print()
    console.print(Text(" Usage: soong start [OPTIONS]", style="bold"))
    console.print()
    console.print(" Launch new GPU instance with cloud-init.")
    console.print()

    # Options panel
    options = Table.grid(padding=(0, 2))
    options.add_column(style="cyan bold", width=22)
    options.add_column(style="dim", width=10)
    options.add_column()
    options.add_row("--model", "TEXT", "Model to load (overrides default)")
    options.add_row("--gpu", "TEXT", "GPU type (overrides default)")
    options.add_row("--region", "TEXT", "Region (overrides default)")
    options.add_row("--hours", "INTEGER", "Lease hours (overrides default)")
    options.add_row("--name", "TEXT", "Instance name")
    options.add_row("--wait / --no-wait", "", "Wait for instance to be ready")
    options.add_row("-y, --yes", "", "Skip cost confirmation")
    options.add_row("--help", "", "Show this message and exit.")
    console.print(Panel(options, title="Options", border_style="dim", padding=(0, 1)))

    svg_path = OUTPUT_DIR / f"{filename}.svg"
    console.save_svg(str(svg_path), title="soong start --help")
    print(f"Saved: {svg_path}")


def capture_status(filename: str = "status"):
    """Capture status screen with sample data."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    console = Console(record=True, width=100, force_terminal=True)

    # Create status table
    table = Table(title="Running Instances")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("GPU", style="yellow")
    table.add_column("Region")
    table.add_column("IP", style="green")
    table.add_column("Status", style="bold green")
    table.add_column("Lease", style="dim")

    table.add_row(
        "inst_abc123",
        "soong-session",
        "gpu_1x_a100_sxm4",
        "us-east-1",
        "203.0.113.42",
        "active",
        "3h 24m remaining",
    )

    console.print(table)
    console.print()
    console.print("[dim]Estimated cost so far: $1.29[/dim]")

    svg_path = OUTPUT_DIR / f"{filename}.svg"
    console.save_svg(str(svg_path), title="soong status")
    print(f"Saved: {svg_path}")


def main():
    """Capture all screenshots."""
    print(f"Capturing screenshots to {OUTPUT_DIR}...\n")

    capture_help()
    capture_model_info()
    capture_available()
    capture_start_help()
    capture_status()

    print(f"\nDone! Screenshots saved to {OUTPUT_DIR}")
    print("\nTo use in docs, reference as: ![Description](../assets/screenshots/filename.svg)")


if __name__ == "__main__":
    main()
