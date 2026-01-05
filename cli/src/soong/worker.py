"""Cloudflare Worker management."""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any

import requests
import questionary
from rich.console import Console
from rich.panel import Panel

from .config import Config, ConfigManager

console = Console()

WORKER_DIR = Path(__file__).parent.parent.parent.parent / "worker"


def parse_kv_namespace_id(wrangler_output: str) -> str:
    """
    Extract KV namespace ID from wrangler output.

    Args:
        wrangler_output: Output from 'wrangler kv:namespace create'

    Returns:
        KV namespace ID (alphanumeric string)

    Raises:
        ValueError: If namespace ID cannot be parsed
    """
    # Try pattern 1: id = "..." (allows alphanumeric with underscores)
    match = re.search(r'id\s*=\s*"([a-zA-Z0-9_-]+)"', wrangler_output)
    if match:
        return match.group(1)

    # Try pattern 2: id: ...
    match = re.search(r'id:\s*([a-zA-Z0-9_-]+)', wrangler_output)
    if match:
        return match.group(1)

    raise ValueError("Failed to parse KV namespace ID from wrangler output")


def parse_worker_url(wrangler_output: str) -> str:
    """
    Extract Worker URL from wrangler deploy output.

    Args:
        wrangler_output: Output from 'wrangler deploy'

    Returns:
        Worker URL (e.g., https://gpu-watchdog.example.workers.dev)

    Raises:
        ValueError: If Worker URL cannot be parsed
    """
    # Pattern: https://*.workers.dev
    match = re.search(
        r'(https://[a-z0-9-]+(?:\.[a-z0-9-]+)?\.workers\.dev)',
        wrangler_output,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    raise ValueError("Failed to parse Worker URL from wrangler deploy output")


def set_worker_secret(secret_name: str, secret_value: str) -> None:
    """
    Set a Worker secret via wrangler.

    Args:
        secret_name: Name of the secret (e.g., "LAMBDA_API_KEY")
        secret_value: Value to set

    Raises:
        RuntimeError: If wrangler command fails
    """
    result = subprocess.run(
        ["npx", "wrangler", "secret", "put", secret_name],
        input=secret_value,
        cwd=str(WORKER_DIR),
        capture_output=True,
        text=True,
        shell=False,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to set secret {secret_name}: {result.stderr}")


def update_wrangler_toml(kv_namespace_id: str) -> None:
    """
    Update wrangler.toml with KV namespace ID.

    Args:
        kv_namespace_id: KV namespace ID to insert
    """
    wrangler_toml = WORKER_DIR / "wrangler.toml"

    # Read current content
    with open(wrangler_toml, 'r') as f:
        content = f.read()

    # Replace placeholder
    updated_content = content.replace(
        'id = "REPLACE_WITH_YOUR_KV_NAMESPACE_ID"',
        f'id = "{kv_namespace_id}"',
    )

    # Write back
    with open(wrangler_toml, 'w') as f:
        f.write(updated_content)


def deploy_worker(config: Config, config_manager: ConfigManager) -> Config:
    """
    Deploy Cloudflare Worker with KV namespace.

    Args:
        config: Current configuration
        config_manager: ConfigManager instance for saving updates

    Returns:
        Updated configuration with worker_url and kv_namespace_id

    Raises:
        RuntimeError: If deployment fails
    """
    console.print("[cyan]Deploying Cloudflare Worker...[/cyan]\n")

    # Step 1: Check Node.js availability
    console.print("Checking Node.js installation...")
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("Node.js not found")
        console.print(f"[green]✓[/green] Node.js {result.stdout.strip()}\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        console.print("[red]Error: Node.js is required for Wrangler[/red]")
        console.print("Install from: https://nodejs.org/")
        raise RuntimeError("Node.js not found")

    # Step 2: Check Worker dependencies
    console.print("Checking Worker dependencies...")
    node_modules = WORKER_DIR / "node_modules"
    if not node_modules.exists():
        console.print("[yellow]Installing Worker dependencies (this may take a minute)...[/yellow]")
        result = subprocess.run(
            ["npm", "ci"],
            cwd=str(WORKER_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"npm ci failed: {result.stderr}")
        console.print("[green]✓[/green] Dependencies installed\n")
    else:
        console.print("[green]✓[/green] Dependencies already installed\n")

    # Step 3: Create KV namespace if needed
    kv_namespace_id = config.cloudflare.kv_namespace_id
    if not kv_namespace_id:
        console.print("Creating KV namespace...")
        result = subprocess.run(
            ["npx", "wrangler", "kv:namespace", "create", "KV"],
            cwd=str(WORKER_DIR),
            capture_output=True,
            text=True,
            shell=False,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"KV namespace creation failed: {result.stderr}")

        kv_namespace_id = parse_kv_namespace_id(result.stdout)
        console.print(f"[green]✓[/green] KV namespace created: {kv_namespace_id}\n")

        # Update config
        config.cloudflare.kv_namespace_id = kv_namespace_id
        config_manager.save(config)
    else:
        console.print(f"[green]✓[/green] Using existing KV namespace: {kv_namespace_id}\n")

    # Step 4: Update wrangler.toml
    console.print("Updating wrangler.toml...")
    update_wrangler_toml(kv_namespace_id)
    console.print("[green]✓[/green] wrangler.toml updated\n")

    # Step 5: Set Worker secrets
    console.print("Setting Worker secrets...")
    set_worker_secret("LAMBDA_API_KEY", config.lambda_config.api_key)
    set_worker_secret("STATUS_DAEMON_TOKEN", config.status_daemon.token)
    console.print("[green]✓[/green] Secrets configured\n")

    # Step 6: Deploy Worker
    console.print("Deploying Worker (this may take a minute)...")
    result = subprocess.run(
        ["npx", "wrangler", "deploy"],
        cwd=str(WORKER_DIR),
        capture_output=True,
        text=True,
        shell=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Worker deployment failed: {result.stderr}")

    worker_url = parse_worker_url(result.stdout)
    console.print(f"[green]✓[/green] Worker deployed: {worker_url}\n")

    # Update config
    config.cloudflare.worker_url = worker_url
    config_manager.save(config)

    # Step 7: Verify deployment
    console.print("Verifying deployment...")
    try:
        response = requests.get(
            f"{worker_url}/health",
            timeout=(5, 10),
        )
        response.raise_for_status()
        health_data = response.json()
        if health_data.get("status") == "healthy":
            console.print("[green]✓[/green] Health check passed\n")
        else:
            console.print(f"[yellow]Warning: Unexpected health status: {health_data}[/yellow]\n")
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
        console.print(f"[yellow]Warning: Health check failed: {e}[/yellow]")
        console.print("[dim]Worker may still be initializing. Try 'soong worker status' in a few seconds.[/dim]\n")

    # Success summary
    console.print("[green]✓ Worker deployed successfully[/green]")
    console.print(f"  URL: {worker_url}")
    console.print(f"  KV Namespace: {kv_namespace_id}")
    console.print("\n[dim]Next steps:[/dim]")
    console.print("[dim]  - Test: soong worker status[/dim]")
    console.print("[dim]  - Deploy triggers: soong start[/dim]")

    return config


def worker_status(config: Config) -> Dict[str, Any]:
    """
    Fetch Worker health status.

    Args:
        config: Current configuration

    Returns:
        Health status dictionary

    Raises:
        RuntimeError: If Worker is not deployed or health check fails
    """
    if not config.cloudflare.worker_url:
        raise RuntimeError("Worker not deployed. Run 'soong worker deploy' first.")

    try:
        response = requests.get(
            f"{config.cloudflare.worker_url}/health",
            timeout=(5, 10),
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Worker status: {e}")


def worker_logs() -> None:
    """
    Stream Worker logs via wrangler tail.

    Raises:
        RuntimeError: If wrangler tail fails
    """
    console.print("[cyan]Streaming Worker logs (Ctrl+C to stop)...[/cyan]\n")

    result = subprocess.run(
        ["npx", "wrangler", "tail"],
        cwd=str(WORKER_DIR),
        shell=False,
    )

    if result.returncode != 0:
        raise RuntimeError("Failed to stream Worker logs")


def destroy_worker(config: Config, config_manager: ConfigManager, force: bool = False) -> Config:
    """
    Destroy Worker deployment and KV namespace.

    Args:
        config: Current configuration
        config_manager: ConfigManager instance for saving updates
        force: Skip confirmation if True

    Returns:
        Updated configuration with cleared Worker fields

    Raises:
        RuntimeError: If destruction fails
    """
    if not config.cloudflare.kv_namespace_id and not config.cloudflare.worker_url:
        console.print("[yellow]No Worker deployment found[/yellow]")
        return config

    # Confirmation
    if not force:
        console.print(Panel(
            "[bold yellow]Warning: This will delete the KV namespace and all history data.[/bold yellow]\n\n"
            "Worker deletion requires manual action in Cloudflare dashboard:\n"
            "https://dash.cloudflare.com/",
            title="[red]Destroy Worker[/red]",
            border_style="red",
        ))

        confirmed = questionary.confirm(
            "Delete KV namespace and clear Worker configuration?",
            default=False,
        ).ask()

        if not confirmed:
            console.print("[yellow]Destroy cancelled[/yellow]")
            return config

    # Delete KV namespace if it exists
    if config.cloudflare.kv_namespace_id:
        console.print("\nDeleting KV namespace...")
        result = subprocess.run(
            ["npx", "wrangler", "kv:namespace", "delete", "--namespace-id", config.cloudflare.kv_namespace_id],
            cwd=str(WORKER_DIR),
            capture_output=True,
            text=True,
            shell=False,
            timeout=30,
        )

        if result.returncode != 0:
            console.print(f"[yellow]Warning: KV namespace deletion failed: {result.stderr}[/yellow]")
        else:
            console.print("[green]✓[/green] KV namespace deleted")

    # Clear configuration
    config.cloudflare.kv_namespace_id = ""
    config.cloudflare.worker_url = ""
    config_manager.save(config)

    console.print("\n[green]Worker configuration cleared[/green]")
    console.print("\n[dim]Note: To delete the Worker deployment itself:[/dim]")
    console.print("[dim]  1. Go to https://dash.cloudflare.com/[/dim]")
    console.print("[dim]  2. Navigate to Workers & Pages[/dim]")
    console.print("[dim]  3. Delete 'gpu-watchdog' Worker[/dim]")

    return config
