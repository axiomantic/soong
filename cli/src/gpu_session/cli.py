"""CLI interface for GPU session management."""

import typer
import secrets
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from datetime import datetime

from .config import Config, ConfigManager, LambdaConfig, StatusDaemonConfig, DefaultsConfig, SSHConfig
from .lambda_api import LambdaAPI, LambdaAPIError
from .instance import InstanceManager
from .ssh import SSHTunnelManager
from .history import HistoryManager, HistoryEvent

app = typer.Typer(
    name="gpu-session",
    help="GPU session management for Lambda Labs",
    add_completion=False,
)
console = Console()

config_manager = ConfigManager()


def get_config() -> Config:
    """Load configuration or exit if not configured."""
    config = config_manager.load()
    if config is None:
        console.print("[red]Error: Not configured. Run 'gpu-session configure' first.[/red]")
        raise typer.Exit(1)
    return config


@app.command()
def configure(
    api_key: Optional[str] = typer.Option(None, prompt="Lambda API key"),
    status_token: Optional[str] = typer.Option(None, help="Shared secret for status daemon auth"),
    default_region: str = typer.Option("us-west-1", prompt="Default region"),
    filesystem_name: str = typer.Option("coding-stack", prompt="Filesystem name"),
    default_model: str = typer.Option("deepseek-r1-70b", prompt="Default model"),
    default_gpu: str = typer.Option("gpu_1x_a100_sxm4_80gb", prompt="Default GPU type"),
    lease_hours: int = typer.Option(4, prompt="Default lease hours"),
    ssh_key_path: str = typer.Option("~/.ssh/id_rsa", prompt="SSH key path"),
):
    """Configure CLI with API keys and defaults."""
    # Auto-generate status token if not provided
    if status_token is None:
        status_token = typer.prompt(
            "Status daemon token (shared secret for auth, leave blank to auto-generate)",
            default="",
            show_default=False,
        )
        if not status_token.strip():
            status_token = secrets.token_urlsafe(32)
            console.print(f"[cyan]Generated token:[/cyan] {status_token}")

    config = Config(
        lambda_config=LambdaConfig(
            api_key=api_key,
            default_region=default_region,
            filesystem_name=filesystem_name,
        ),
        status_daemon=StatusDaemonConfig(token=status_token),
        defaults=DefaultsConfig(
            model=default_model,
            gpu=default_gpu,
            lease_hours=lease_hours,
        ),
        ssh=SSHConfig(key_path=ssh_key_path),
    )

    config_manager.save(config)
    console.print("[green]Configuration saved successfully[/green]")
    console.print(f"Config file: {config_manager.config_file}")


@app.command()
def start(
    model: Optional[str] = typer.Option(None, help="Model to load (overrides default)"),
    gpu: Optional[str] = typer.Option(None, help="GPU type (overrides default)"),
    region: Optional[str] = typer.Option(None, help="Region (overrides default)"),
    hours: Optional[int] = typer.Option(None, help="Lease hours (overrides default)"),
    name: Optional[str] = typer.Option(None, help="Instance name"),
    wait: bool = typer.Option(True, help="Wait for instance to be ready"),
):
    """Launch new GPU instance with cloud-init."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)
    instance_mgr = InstanceManager(api)

    # Use config defaults if not specified
    model = model or config.defaults.model
    gpu = gpu or config.defaults.gpu
    region = region or config.lambda_config.default_region
    hours = hours or config.defaults.lease_hours

    console.print(f"[cyan]Launching instance...[/cyan]")
    console.print(f"  Model: {model}")
    console.print(f"  GPU: {gpu}")
    console.print(f"  Region: {region}")
    console.print(f"  Lease: {hours} hours")

    try:
        # Get SSH keys
        ssh_keys = api.list_ssh_keys()
        if not ssh_keys:
            console.print("[red]Error: No SSH keys found in Lambda account[/red]")
            console.print("Add an SSH key at: https://cloud.lambdalabs.com/ssh-keys")
            raise typer.Exit(1)

        # Launch instance
        instance_id = api.launch_instance(
            region=region,
            instance_type=gpu,
            ssh_key_names=ssh_keys,
            filesystem_names=[config.lambda_config.filesystem_name],
            name=name,
        )

        console.print(f"[green]Instance launched: {instance_id}[/green]")

        if wait:
            instance = instance_mgr.wait_for_ready(instance_id, timeout_seconds=600)
            if instance:
                console.print(f"[green]Instance ready at {instance.ip}[/green]")
                console.print(f"\nSSH: gpu-session ssh")
                console.print(f"Status: gpu-session status")
            else:
                console.print("[yellow]Instance launch timed out[/yellow]")
        else:
            console.print("\nCheck status with: gpu-session status")

    except LambdaAPIError as e:
        console.print(f"[red]Error launching instance: {e}[/red]")
        raise typer.Exit(1)


def show_termination_history(events: list, hours: int):
    """Display termination history in a rich table."""
    if not events:
        console.print(f"[yellow]No termination events found in the last {hours} hours[/yellow]")
        return

    table = Table(title=f"Termination History (Last {hours} Hours)")
    table.add_column("Time", style="cyan")
    table.add_column("Instance ID", style="magenta")
    table.add_column("Reason", style="yellow")
    table.add_column("Uptime", style="blue")
    table.add_column("GPU", style="green")
    table.add_column("Region", style="white")

    for event in events:
        # Color code reason
        reason_text = event.reason
        if "watchdog" in event.reason.lower():
            reason_style = "red"
        elif "idle" in event.reason.lower() or "timeout" in event.reason.lower():
            reason_style = "yellow"
        elif "lease" in event.reason.lower() or "expired" in event.reason.lower():
            reason_style = "orange1"
        else:
            reason_style = "white"

        # Format timestamp
        try:
            timestamp = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            time_str = event.timestamp

        # Format uptime
        hours_up = event.uptime_minutes // 60
        mins_up = event.uptime_minutes % 60
        uptime_str = f"{hours_up}h {mins_up}m" if hours_up > 0 else f"{mins_up}m"

        table.add_row(
            time_str,
            event.instance_id[:8],
            f"[{reason_style}]{reason_text}[/{reason_style}]",
            uptime_str,
            event.gpu_type,
            event.region,
        )

    console.print(table)


def show_stopped_instances(instances: list):
    """Display stopped instances grouped by termination reason."""
    stopped = [i for i in instances if i.status in ["terminated", "stopped"]]

    if not stopped:
        console.print("[yellow]No stopped instances found[/yellow]")
        return

    table = Table(title="Stopped Instances")
    table.add_column("Instance ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Status", style="red")
    table.add_column("GPU", style="yellow")
    table.add_column("Region", style="white")
    table.add_column("Created At", style="blue")

    for instance in stopped:
        # Format created_at
        try:
            created = datetime.fromisoformat(instance.created_at.replace('Z', '+00:00'))
            created_str = created.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            created_str = instance.created_at

        table.add_row(
            instance.id[:8],
            instance.name or "-",
            instance.status,
            instance.instance_type,
            instance.region,
            created_str,
        )

    console.print(table)


@app.command()
def status(
    instance_id: Optional[str] = typer.Option(None, help="Instance ID (uses active if not specified)"),
    history: bool = typer.Option(False, "--history", "-h", help="Show termination history"),
    stopped: bool = typer.Option(False, "--stopped", "-s", help="Show stopped instances"),
    history_hours: int = typer.Option(24, help="Hours of history to show"),
    worker_url: Optional[str] = typer.Option(None, help="Cloudflare Worker URL for history"),
):
    """Show status of running instances."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)

    try:
        # Show termination history if requested
        if history:
            history_mgr = HistoryManager()
            if worker_url:
                events = history_mgr.sync_from_worker(worker_url, history_hours)
            else:
                events = history_mgr.get_local_history(history_hours)
            show_termination_history(events, history_hours)
            return

        if instance_id:
            instances = [api.get_instance(instance_id)]
            if instances[0] is None:
                console.print(f"[red]Instance {instance_id} not found[/red]")
                raise typer.Exit(1)
        else:
            instances = api.list_instances()

        if not instances:
            console.print("[yellow]No instances found[/yellow]")
            return

        # Show stopped instances if requested
        if stopped:
            show_stopped_instances(instances)
            return

        # Filter to running instances only for default view
        running_instances = [i for i in instances if i.status not in ["terminated", "stopped"]]

        if not running_instances:
            console.print("[yellow]No running instances found[/yellow]")
            console.print("\nUse --stopped to see terminated instances")
            console.print("Use --history to see termination history")
            return

        # Create table
        table = Table(title="GPU Instances")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("IP", style="blue")
        table.add_column("GPU", style="yellow")
        table.add_column("Region", style="white")
        table.add_column("Lease Status", style="white")

        for instance in running_instances:
            # Determine lease status
            if instance.lease_expires_at:
                try:
                    expires_at = datetime.fromisoformat(instance.lease_expires_at.replace('Z', '+00:00'))
                    now = datetime.utcnow().replace(tzinfo=expires_at.tzinfo)
                    time_left = expires_at - now
                    hours_left = int(time_left.total_seconds() // 3600)
                    mins_left = int((time_left.total_seconds() % 3600) // 60)

                    if time_left.total_seconds() < 0:
                        lease_text = "[red]EXPIRED[/red]"
                    elif hours_left < 1:
                        lease_text = f"[yellow]{mins_left}m[/yellow]"
                    else:
                        lease_text = f"[green]{hours_left}h {mins_left}m[/green]"
                except (ValueError, AttributeError):
                    lease_text = "-"
            else:
                lease_text = "-"

            table.add_row(
                instance.id[:8],
                instance.name or "-",
                instance.status,
                instance.ip or "-",
                instance.instance_type,
                instance.region,
                lease_text,
            )

        console.print(table)

    except LambdaAPIError as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def extend(
    hours: int = typer.Argument(..., help="Hours to extend lease"),
    instance_id: Optional[str] = typer.Option(None, help="Instance ID (uses active if not specified)"),
):
    """Extend instance lease."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)
    instance_mgr = InstanceManager(api)

    # Get instance
    if instance_id:
        instance = api.get_instance(instance_id)
    else:
        instance = instance_mgr.get_active_instance()

    if not instance:
        console.print("[red]No instance found[/red]")
        raise typer.Exit(1)

    if not instance.ip:
        console.print("[red]Instance has no IP address[/red]")
        raise typer.Exit(1)

    # Make request to status daemon
    import requests
    try:
        url = f"http://{instance.ip}:{config.status_daemon.port}/extend"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.status_daemon.token}"},
            data={"hours": hours},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()

        console.print(f"[green]Lease extended by {result['extended_by_hours']} hours[/green]")
        console.print(f"New shutdown time: {result['new_shutdown_at']}")

    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error extending lease: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def stop(
    instance_id: Optional[str] = typer.Option(None, help="Instance ID (uses active if not specified)"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Terminate instance."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)
    instance_mgr = InstanceManager(api)

    # Get instance
    if instance_id:
        instance = api.get_instance(instance_id)
    else:
        instance = instance_mgr.get_active_instance()

    if not instance:
        console.print("[red]No instance found[/red]")
        raise typer.Exit(1)

    if not confirm:
        confirmed = typer.confirm(f"Terminate instance {instance.id}?")
        if not confirmed:
            raise typer.Abort()

    try:
        api.terminate_instance(instance.id)
        console.print(f"[green]Instance {instance.id} terminated[/green]")
    except LambdaAPIError as e:
        console.print(f"[red]Error terminating instance: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def ssh(
    instance_id: Optional[str] = typer.Option(None, help="Instance ID (uses active if not specified)"),
):
    """SSH into instance."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)
    instance_mgr = InstanceManager(api)
    ssh_mgr = SSHTunnelManager(config.ssh.key_path)

    # Get instance
    if instance_id:
        instance = api.get_instance(instance_id)
    else:
        instance = instance_mgr.get_active_instance()

    if not instance:
        console.print("[red]No instance found[/red]")
        raise typer.Exit(1)

    if not instance.ip:
        console.print("[red]Instance has no IP address[/red]")
        raise typer.Exit(1)

    ssh_mgr.connect_ssh(instance.ip)


@app.command()
def available():
    """Show available GPU types and models."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)

    try:
        instance_types = api.list_instance_types()

        # Create table
        table = Table(title="Available GPU Types")
        table.add_column("GPU Type", style="cyan")
        table.add_column("Regions", style="yellow")
        table.add_column("Available", style="green")

        for gpu_name, gpu_info in instance_types.items():
            regions_available = []
            for region_name, region_data in gpu_info.get("regions_with_capacity_available", {}).items():
                if region_data.get("available", False):
                    regions_available.append(region_name)

            availability = "Yes" if regions_available else "No"
            regions_str = ", ".join(regions_available) if regions_available else "-"

            table.add_row(gpu_name, regions_str, availability)

        console.print(table)

        # Show recommended models
        console.print("\n[cyan]Recommended Models:[/cyan]")
        console.print("  deepseek-r1-70b (requires A100 80GB)")
        console.print("  qwen2.5-coder-32b (works on RTX 6000)")

    except LambdaAPIError as e:
        console.print(f"[red]Error getting GPU types: {e}[/red]")
        raise typer.Exit(1)


# Tunnel subcommand group
tunnel_app = typer.Typer(help="Manage SSH tunnels")
app.add_typer(tunnel_app, name="tunnel")


@tunnel_app.command("start")
def tunnel_start(
    instance_id: Optional[str] = typer.Option(None, help="Instance ID (uses active if not specified)"),
    sglang_port: int = typer.Option(8000, help="Local port for SGLang"),
    n8n_port: int = typer.Option(5678, help="Local port for n8n"),
    status_port: int = typer.Option(8080, help="Local port for status daemon"),
):
    """Start SSH tunnel to instance."""
    config = get_config()
    api = LambdaAPI(config.lambda_config.api_key)
    instance_mgr = InstanceManager(api)
    ssh_mgr = SSHTunnelManager(config.ssh.key_path)

    # Get instance
    if instance_id:
        instance = api.get_instance(instance_id)
    else:
        instance = instance_mgr.get_active_instance()

    if not instance:
        console.print("[red]No instance found[/red]")
        raise typer.Exit(1)

    if not instance.ip:
        console.print("[red]Instance has no IP address[/red]")
        raise typer.Exit(1)

    # Start tunnel
    success = ssh_mgr.start_tunnel(
        instance.ip,
        local_ports=[sglang_port, n8n_port, status_port],
        remote_ports=[8000, 5678, 8080],
    )

    if not success:
        raise typer.Exit(1)


@tunnel_app.command("stop")
def tunnel_stop():
    """Stop SSH tunnel."""
    config = get_config()
    ssh_mgr = SSHTunnelManager(config.ssh.key_path)

    if not ssh_mgr.stop_tunnel():
        raise typer.Exit(1)


@tunnel_app.command("status")
def tunnel_status():
    """Check tunnel status."""
    config = get_config()
    ssh_mgr = SSHTunnelManager(config.ssh.key_path)

    if ssh_mgr.is_tunnel_running():
        console.print("[green]Tunnel is running[/green]")
    else:
        console.print("[yellow]Tunnel is not running[/yellow]")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
