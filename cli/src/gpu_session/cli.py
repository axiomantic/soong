"""CLI interface for GPU session management."""

import typer
import secrets
import questionary
from typing import Optional, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from datetime import datetime

from .config import Config, ConfigManager, LambdaConfig, StatusDaemonConfig, DefaultsConfig, SSHConfig
from .lambda_api import LambdaAPI, LambdaAPIError, InstanceType
from .instance import InstanceManager
from .ssh import SSHTunnelManager
from .history import HistoryManager, HistoryEvent
from .models import (
    KNOWN_MODELS, KNOWN_GPUS, ModelConfig, Quantization,
    get_model_config, get_recommended_gpu, estimate_vram, format_model_info
)

app = typer.Typer(
    name="gpu-session",
    help="GPU session management for Lambda Labs",
    add_completion=False,
)
console = Console()

config_manager = ConfigManager()


def show_gpu_size_warning(console, selected_vram, min_vram_needed, viable_gpus, selected_gpu):
    """Show warning if selected GPU is larger than minimum needed."""
    if selected_vram > min_vram_needed and min_vram_needed > 0:
        # Find cheapest viable GPU
        cheapest_viable = None
        for g in viable_gpus:
            if g['available']:
                cheapest_viable = g
                break

        if cheapest_viable and cheapest_viable['type'].name != selected_gpu:
            console.print(
                f"[dim]Note: {cheapest_viable['type'].description} "
                f"({cheapest_viable['vram']}GB) would also work and costs "
                f"{cheapest_viable['type'].format_price()}[/dim]\n"
            )


def get_config() -> Config:
    """Load configuration or exit if not configured."""
    config = config_manager.load()
    if config is None:
        console.print("[red]Error: Not configured. Run 'gpu-session configure' first.[/red]")
        raise typer.Exit(1)
    return config


@app.command()
def configure():
    """Interactive configuration wizard."""
    console.print(Panel(
        "[bold]GPU Session Configuration Wizard[/bold]\n\n"
        "This will guide you through setting up your Lambda Labs credentials and defaults.",
        border_style="cyan",
    ))
    console.print()

    # Step 1: Lambda API Key
    api_key = questionary.text(
        "Lambda API key:",
        validate=lambda x: len(x) > 0 or "API key is required",
    ).ask()
    if not api_key:
        console.print("[red]Configuration cancelled.[/red]")
        raise typer.Exit(1)

    # Validate API key by fetching instance types
    console.print("[cyan]Validating API key...[/cyan]")
    api = LambdaAPI(api_key)
    try:
        instance_types = api.list_instance_types()
        console.print("[green]API key valid.[/green]\n")
    except LambdaAPIError as e:
        console.print(f"[red]Invalid API key: {e}[/red]")
        raise typer.Exit(1)

    # Step 2: Status daemon token
    console.print("[dim]The status daemon token is a shared secret for authenticating with the instance.[/dim]")
    status_token = questionary.text(
        "Status daemon token (leave blank to auto-generate):",
        default="",
    ).ask()
    if status_token is None:
        raise typer.Exit(1)
    if not status_token.strip():
        status_token = secrets.token_urlsafe(32)
        console.print(f"[cyan]Generated token:[/cyan] {status_token}\n")
    else:
        console.print()

    # Step 3: Select model first (determines GPU requirements)
    console.print("[bold]Step 3: Select default model[/bold]")
    console.print("[dim]The model determines minimum GPU requirements.[/dim]\n")

    model_choices = []
    for model_id, model in KNOWN_MODELS.items():
        rec_gpu = get_recommended_gpu(model_id)
        gpu_info = KNOWN_GPUS.get(rec_gpu, {})
        vram = model.estimated_vram_gb
        label = f"{model.name} ({model.params_billions:.0f}B {model.default_quantization.value.upper()}) - needs {vram:.0f}GB+ VRAM"
        model_choices.append(questionary.Choice(title=label, value=model_id))

    model_choices.append(questionary.Choice(title="Custom model (enter manually)", value="_custom"))

    default_model = questionary.select(
        "Default model:",
        choices=model_choices,
        style=questionary.Style([
            ('selected', 'fg:cyan bold'),
            ('pointer', 'fg:cyan bold'),
        ]),
    ).ask()
    if not default_model:
        raise typer.Exit(1)

    # Handle custom model
    recommended_gpu = None
    model_config = None
    if default_model == "_custom":
        default_model = questionary.text("Enter model name/path:").ask()
        if not default_model:
            raise typer.Exit(1)

        # Ask for custom model specs to estimate GPU
        console.print("\n[dim]Enter model specs to calculate GPU requirements:[/dim]")
        try:
            params_b = float(questionary.text("Parameter count (billions):", default="70").ask() or "70")
            quant = questionary.select(
                "Quantization:",
                choices=[
                    questionary.Choice(title="FP16 (2 bytes/param)", value="fp16"),
                    questionary.Choice(title="INT8 (1 byte/param)", value="int8"),
                    questionary.Choice(title="INT4/GPTQ/AWQ (0.5 bytes/param)", value="int4"),
                ],
            ).ask()

            quant_enum = {"fp16": Quantization.FP16, "int8": Quantization.INT8, "int4": Quantization.INT4}[quant]
            vram_info = estimate_vram(params_b, quant_enum)

            console.print(f"\n[cyan]Estimated VRAM:[/cyan] {vram_info['total_estimated_gb']:.1f} GB")
            console.print(f"[cyan]Minimum GPU:[/cyan] {vram_info['min_vram_gb']} GB\n")

            # Find recommended GPU
            for gpu_name, gpu_info in sorted(KNOWN_GPUS.items(), key=lambda x: x[1]['vram_gb']):
                if gpu_info['vram_gb'] >= vram_info['min_vram_gb']:
                    recommended_gpu = gpu_name
                    break
        except (ValueError, TypeError):
            console.print("[yellow]Could not parse specs, will select GPU manually.[/yellow]")
    else:
        model_config = get_model_config(default_model)
        recommended_gpu = get_recommended_gpu(default_model)
        if model_config:
            console.print(f"\n[green]Selected:[/green] {model_config.name}")
            console.print(f"  {model_config.description}")
            console.print(f"  Est. VRAM: {model_config.estimated_vram_gb:.1f} GB")
            if recommended_gpu:
                gpu_info = KNOWN_GPUS.get(recommended_gpu, {})
                console.print(f"  Recommended GPU: {gpu_info.get('description', recommended_gpu)}\n")

    # Step 4: GPU type selection (with recommendation)
    console.print("[bold]Step 4: Select GPU type[/bold]")

    # Calculate minimum VRAM needed
    min_vram_needed = 0
    if model_config:
        min_vram_needed = model_config.estimated_vram_gb
    elif 'vram_info' in dir() and vram_info:
        min_vram_needed = vram_info.get('total_estimated_gb', 0)

    if instance_types:
        # Build GPU list with VRAM info from our known GPUs
        gpu_options = []
        for t in instance_types:
            known_gpu = KNOWN_GPUS.get(t.name, {})
            vram = known_gpu.get('vram_gb', 0)

            # Try to infer VRAM from description if not in our list
            if vram == 0:
                import re
                match = re.search(r'\((\d+)\s*GB', t.description)
                if match:
                    vram = int(match.group(1))

            gpu_options.append({
                'type': t,
                'vram': vram,
                'available': len(t.regions_available) > 0,
            })

        # Sort by price
        gpu_options.sort(key=lambda x: x['type'].price_cents_per_hour)

        # Separate viable vs non-viable GPUs
        viable_gpus = [g for g in gpu_options if g['vram'] >= min_vram_needed]
        small_gpus = [g for g in gpu_options if g['vram'] < min_vram_needed and g['vram'] > 0]

        if min_vram_needed > 0:
            console.print(f"[dim]Model needs ~{min_vram_needed:.0f}GB VRAM. Showing compatible GPUs first.[/dim]\n")

        choices = []
        default_idx = 0
        cheapest_available_idx = None

        # Add viable GPUs first
        for i, g in enumerate(viable_gpus):
            t = g['type']
            vram = g['vram']
            avail = "available" if g['available'] else "no capacity"

            # Find cheapest available option
            if g['available'] and cheapest_available_idx is None:
                cheapest_available_idx = i

            marker = ""
            if cheapest_available_idx == i:
                marker = " ⟵ RECOMMENDED"

            label = f"{t.description} ({vram}GB) - {t.format_price()} ({avail}){marker}"
            choices.append(questionary.Choice(title=label, value=t.name))

        # Add separator if there are non-viable GPUs
        if small_gpus and viable_gpus:
            choices.append(questionary.Choice(title="─── Below: insufficient VRAM ───", value="_separator", disabled=""))

        # Add non-viable GPUs (disabled or marked)
        for g in small_gpus:
            t = g['type']
            vram = g['vram']
            avail = "available" if g['available'] else "no capacity"
            label = f"{t.description} ({vram}GB) - {t.format_price()} ({avail}) [TOO SMALL]"
            choices.append(questionary.Choice(title=label, value=t.name))

        if not choices:
            console.print("[red]No GPU types available![/red]")
            raise typer.Exit(1)

        # Set default to cheapest available viable option
        default_val = None
        if cheapest_available_idx is not None and viable_gpus:
            default_val = viable_gpus[cheapest_available_idx]['type'].name

        default_gpu = questionary.select(
            "GPU type:",
            choices=choices,
            default=default_val,
            style=questionary.Style([
                ('selected', 'fg:cyan bold'),
                ('pointer', 'fg:cyan bold'),
            ]),
        ).ask()

        if not default_gpu or default_gpu == "_separator":
            raise typer.Exit(1)

        selected_type = next((t for t in instance_types if t.name == default_gpu), None)
        if selected_type:
            selected_vram = next((g['vram'] for g in gpu_options if g['type'].name == default_gpu), 0)
            console.print(f"[green]Selected:[/green] {selected_type.description} ({selected_vram}GB) @ {selected_type.format_price()}\n")

            # Warn if selected GPU is too small
            if selected_vram < min_vram_needed and min_vram_needed > 0:
                console.print(f"[yellow]Warning: Selected GPU has {selected_vram}GB but model needs ~{min_vram_needed:.0f}GB[/yellow]\n")

            # Show info if selected GPU is larger than minimum needed
            show_gpu_size_warning(
                console=console,
                selected_vram=selected_vram,
                min_vram_needed=min_vram_needed,
                viable_gpus=viable_gpus,
                selected_gpu=default_gpu,
            )
    else:
        default_gpu = recommended_gpu or "gpu_1x_a100_sxm4_80gb"
        selected_type = None
        console.print(f"[yellow]Using GPU: {default_gpu}[/yellow]\n")

    # Step 5: Default region
    console.print("[bold]Step 5: Select region[/bold]")
    if selected_type and selected_type.regions_available:
        region_choices = [questionary.Choice(title=r, value=r) for r in selected_type.regions_available]
        if not any(c.value == "us-west-1" for c in region_choices):
            region_choices.append(questionary.Choice(title="us-west-1", value="us-west-1"))

        default_region = questionary.select(
            "Default region:",
            choices=region_choices,
        ).ask()
    else:
        default_region = questionary.text(
            "Default region:",
            default="us-west-1",
        ).ask()
    if not default_region:
        raise typer.Exit(1)
    console.print()

    # Step 6: Filesystem name
    console.print("[bold]Step 6: Persistent filesystem[/bold]")
    console.print("[dim]Stores models, secrets, and project files across sessions.[/dim]")
    filesystem_name = questionary.text(
        "Filesystem name:",
        default="coding-stack",
    ).ask()
    if not filesystem_name:
        raise typer.Exit(1)
    console.print()

    # Step 7: Default lease hours (with cost estimates)
    console.print("[bold]Step 7: Default lease duration[/bold]")
    if selected_type:
        lease_choices = [
            questionary.Choice(title=f"2 hours (${selected_type.price_per_hour * 2:.2f})", value=2),
            questionary.Choice(title=f"4 hours (${selected_type.price_per_hour * 4:.2f}) - recommended", value=4),
            questionary.Choice(title=f"6 hours (${selected_type.price_per_hour * 6:.2f})", value=6),
            questionary.Choice(title=f"8 hours (${selected_type.price_per_hour * 8:.2f}) - maximum", value=8),
        ]
    else:
        lease_choices = [
            questionary.Choice(title="2 hours", value=2),
            questionary.Choice(title="4 hours - recommended", value=4),
            questionary.Choice(title="6 hours", value=6),
            questionary.Choice(title="8 hours - maximum", value=8),
        ]
    lease_hours = questionary.select(
        "Default lease duration:",
        choices=lease_choices,
        default=lease_choices[1],
    ).ask()
    if lease_hours is None:
        raise typer.Exit(1)
    console.print()

    # Step 8: SSH key path
    ssh_key_path = questionary.path(
        "SSH private key path:",
        default="~/.ssh/id_rsa",
    ).ask()
    if not ssh_key_path:
        raise typer.Exit(1)

    # Save configuration
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

    # Show summary
    console.print()
    console.print(Panel(
        f"[bold green]Configuration saved![/bold green]\n\n"
        f"API Key: {api_key[:8]}...{api_key[-4:]}\n"
        f"GPU: {default_gpu}\n"
        f"Region: {default_region}\n"
        f"Model: {default_model}\n"
        f"Lease: {lease_hours} hours\n"
        f"Filesystem: {filesystem_name}\n\n"
        f"Config file: {config_manager.config_file}",
        title="[cyan]Summary[/cyan]",
        border_style="green",
    ))


def show_cost_estimate(instance_type: InstanceType, hours: int, action: str = "launch") -> bool:
    """Show cost estimate and get confirmation."""
    estimated_cost = instance_type.estimate_cost(hours)

    console.print()
    console.print(Panel(
        f"[bold]Cost Estimate[/bold]\n\n"
        f"GPU: {instance_type.description}\n"
        f"Rate: {instance_type.format_price()}\n"
        f"Duration: {hours} hours\n\n"
        f"[bold yellow]Estimated cost: ${estimated_cost:.2f}[/bold yellow]",
        title=f"[cyan]{action.title()} Instance[/cyan]",
        border_style="cyan",
    ))
    console.print()

    confirm = questionary.confirm(
        f"Proceed with {action}?",
        default=True,
    ).ask()

    return confirm if confirm is not None else False


@app.command()
def start(
    model: Optional[str] = typer.Option(None, help="Model to load (overrides default)"),
    gpu: Optional[str] = typer.Option(None, help="GPU type (overrides default)"),
    region: Optional[str] = typer.Option(None, help="Region (overrides default)"),
    hours: Optional[int] = typer.Option(None, help="Lease hours (overrides default)"),
    name: Optional[str] = typer.Option(None, help="Instance name"),
    wait: bool = typer.Option(True, help="Wait for instance to be ready"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip cost confirmation"),
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

    console.print(f"[cyan]Preparing to launch instance...[/cyan]")
    console.print(f"  Model: {model}")
    console.print(f"  GPU: {gpu}")
    console.print(f"  Region: {region}")
    console.print(f"  Lease: {hours} hours")

    try:
        # Get pricing info for cost estimate
        instance_type = api.get_instance_type(gpu)
        if instance_type and not yes:
            if not show_cost_estimate(instance_type, hours, "launch"):
                console.print("[yellow]Launch cancelled.[/yellow]")
                raise typer.Exit(0)
        elif not instance_type:
            console.print(f"[yellow]Could not fetch pricing for {gpu}[/yellow]")
            if not yes:
                confirm = typer.confirm("Proceed without cost estimate?", default=True)
                if not confirm:
                    raise typer.Exit(0)

        # Get SSH keys
        ssh_keys = api.list_ssh_keys()
        if not ssh_keys:
            console.print("[red]Error: No SSH keys found in Lambda account[/red]")
            console.print("Add an SSH key at: https://cloud.lambdalabs.com/ssh-keys")
            raise typer.Exit(1)

        console.print(f"\n[cyan]Launching instance...[/cyan]")

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

        # Fetch pricing for all instance types (cache for efficiency)
        pricing_cache: Dict[str, InstanceType] = {}
        try:
            for itype in api.list_instance_types():
                pricing_cache[itype.name] = itype
        except LambdaAPIError:
            pass  # Continue without pricing if API fails

        # Create table
        table = Table(title="GPU Instances")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("IP", style="blue")
        table.add_column("GPU", style="yellow")
        table.add_column("Uptime", style="white")
        table.add_column("Time Left", style="white")
        table.add_column("Cost Now", style="yellow")
        table.add_column("Est. Total", style="yellow")

        for instance in running_instances:
            now = datetime.utcnow()

            # Calculate uptime
            uptime_text = "-"
            uptime_hours = 0.0
            try:
                created = datetime.fromisoformat(instance.created_at.replace('Z', '+00:00'))
                now_tz = now.replace(tzinfo=created.tzinfo)
                uptime = now_tz - created
                uptime_hours = uptime.total_seconds() / 3600
                hours_up = int(uptime_hours)
                mins_up = int((uptime.total_seconds() % 3600) // 60)
                uptime_text = f"{hours_up}h {mins_up}m"
            except (ValueError, AttributeError):
                pass

            # Calculate time left and total lease duration
            time_left_text = "-"
            total_lease_hours = 0.0
            is_expired = False
            if instance.lease_expires_at:
                try:
                    expires_at = datetime.fromisoformat(instance.lease_expires_at.replace('Z', '+00:00'))
                    created = datetime.fromisoformat(instance.created_at.replace('Z', '+00:00'))
                    now_tz = now.replace(tzinfo=expires_at.tzinfo)
                    time_left = expires_at - now_tz
                    total_lease = expires_at - created
                    total_lease_hours = total_lease.total_seconds() / 3600

                    hours_left = int(time_left.total_seconds() // 3600)
                    mins_left = int((time_left.total_seconds() % 3600) // 60)

                    if time_left.total_seconds() < 0:
                        time_left_text = "[red]EXPIRED[/red]"
                        is_expired = True
                    elif hours_left < 1:
                        time_left_text = f"[yellow]{mins_left}m[/yellow]"
                    else:
                        time_left_text = f"[green]{hours_left}h {mins_left}m[/green]"
                except (ValueError, AttributeError):
                    pass

            # Calculate costs
            current_cost_text = "-"
            total_cost_text = "-"
            instance_type = pricing_cache.get(instance.instance_type)
            if instance_type:
                current_cost = instance_type.price_per_hour * uptime_hours
                current_cost_text = f"${current_cost:.2f}"

                if total_lease_hours > 0:
                    total_cost = instance_type.price_per_hour * total_lease_hours
                    total_cost_text = f"${total_cost:.2f}"

                # Highlight in red if expired (cost is still accruing!)
                if is_expired:
                    current_cost_text = f"[red]{current_cost_text}[/red]"

            table.add_row(
                instance.id[:8],
                instance.name or "-",
                instance.status,
                instance.ip or "-",
                instance.instance_type,
                uptime_text,
                time_left_text,
                current_cost_text,
                total_cost_text,
            )

        console.print(table)

        # Show total cost summary if multiple instances
        if len(running_instances) > 1:
            total_current = 0.0
            for instance in running_instances:
                instance_type = pricing_cache.get(instance.instance_type)
                if instance_type:
                    try:
                        created = datetime.fromisoformat(instance.created_at.replace('Z', '+00:00'))
                        now_tz = datetime.utcnow().replace(tzinfo=created.tzinfo)
                        uptime_hours = (now_tz - created).total_seconds() / 3600
                        total_current += instance_type.price_per_hour * uptime_hours
                    except (ValueError, AttributeError):
                        pass
            if total_current > 0:
                console.print(f"\n[bold]Total current cost: [yellow]${total_current:.2f}[/yellow][/bold]")

    except LambdaAPIError as e:
        console.print(f"[red]Error getting status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def extend(
    hours: int = typer.Argument(..., help="Hours to extend lease"),
    instance_id: Optional[str] = typer.Option(None, help="Instance ID (uses active if not specified)"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip cost confirmation"),
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

    # Show cost estimate for extension
    if not yes:
        instance_type = api.get_instance_type(instance.instance_type)
        if instance_type:
            additional_cost = instance_type.estimate_cost(hours)
            console.print()
            console.print(Panel(
                f"[bold]Extension Cost Estimate[/bold]\n\n"
                f"Instance: {instance.id[:8]}\n"
                f"GPU: {instance_type.description}\n"
                f"Rate: {instance_type.format_price()}\n"
                f"Extension: {hours} hours\n\n"
                f"[bold yellow]Additional cost: ${additional_cost:.2f}[/bold yellow]",
                title="[cyan]Extend Lease[/cyan]",
                border_style="cyan",
            ))
            console.print()

            confirm = questionary.confirm(
                f"Extend lease by {hours} hours?",
                default=True,
            ).ask()

            if not confirm:
                console.print("[yellow]Extension cancelled.[/yellow]")
                raise typer.Exit(0)

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
