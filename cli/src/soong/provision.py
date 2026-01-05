"""Instance provisioning via Ansible."""

import subprocess
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.console import Group

console = Console()

# Ansible directory relative to this file
ANSIBLE_DIR = Path(__file__).parent.parent.parent.parent / "ansible"


@dataclass
class ProvisionConfig:
    """Configuration for instance provisioning."""
    instance_ip: str
    ssh_key_path: str
    lambda_api_key: str
    status_token: str
    model: str
    lease_hours: int
    idle_timeout_minutes: int = 30
    max_lease_hours: int = 8


class ProvisionDisplay:
    """Dynamic display for provisioning progress."""

    def __init__(self):
        self.status = "Connecting..."
        self.spinner = Spinner("dots")

    def __rich__(self):
        text = Text(f" {self.status}")
        return Group(self.spinner, text)


def wait_for_ssh(ip: str, ssh_key_path: str, timeout: int = 120) -> bool:
    """
    Wait for SSH to become available on the instance.

    Args:
        ip: Instance IP address
        ssh_key_path: Path to SSH private key
        timeout: Maximum seconds to wait

    Returns:
        True if SSH is available, False if timeout
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=5",
                    "-o", "BatchMode=yes",
                    "-i", ssh_key_path,
                    f"ubuntu@{ip}",
                    "echo ok",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and "ok" in result.stdout:
                return True
        except (subprocess.TimeoutExpired, Exception):
            pass
        time.sleep(5)
    return False


def run_ansible_playbook(config: ProvisionConfig) -> bool:
    """
    Run Ansible playbook to provision the instance.

    Args:
        config: Provisioning configuration

    Returns:
        True if provisioning succeeded
    """
    if not ANSIBLE_DIR.exists():
        console.print(f"[red]Ansible directory not found: {ANSIBLE_DIR}[/red]")
        return False

    # Create temporary inventory
    inventory_content = f"""[gpu_instance]
{config.instance_ip} ansible_user=ubuntu ansible_ssh_private_key_file={config.ssh_key_path} ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
"""
    inventory_file = ANSIBLE_DIR / "inventory_dynamic.ini"
    inventory_file.write_text(inventory_content)

    try:
        # Build ansible-playbook command
        cmd = [
            "ansible-playbook",
            "-i", str(inventory_file),
            str(ANSIBLE_DIR / "site.yml"),
            "-e", f"lambda_api_key={config.lambda_api_key}",
            "-e", f"status_token={config.status_token}",
            "-e", f"model={config.model}",
            "-e", f"lease_hours={config.lease_hours}",
            "-e", f"idle_timeout_minutes={config.idle_timeout_minutes}",
            "-e", f"max_lease_hours={config.max_lease_hours}",
            "--become",
        ]

        result = subprocess.run(
            cmd,
            cwd=str(ANSIBLE_DIR),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            console.print(f"[red]Ansible failed:[/red]\n{result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        console.print("[red]Ansible playbook timed out[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]ansible-playbook not found. Install Ansible:[/red]")
        console.print("  pip install ansible")
        return False
    finally:
        # Clean up temporary inventory
        if inventory_file.exists():
            inventory_file.unlink()


def wait_for_services(ip: str, ssh_key_path: str, timeout: int = 120) -> bool:
    """
    Wait for services to be ready on the instance.

    Args:
        ip: Instance IP address
        ssh_key_path: Path to SSH private key
        timeout: Maximum seconds to wait

    Returns:
        True if services are ready
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Check if status daemon is responding
            result = subprocess.run(
                [
                    "ssh",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=5",
                    "-i", ssh_key_path,
                    f"ubuntu@{ip}",
                    "curl -s http://localhost:8080/health",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and "healthy" in result.stdout.lower():
                return True
        except (subprocess.TimeoutExpired, Exception):
            pass
        time.sleep(5)
    return False


def provision_instance(config: ProvisionConfig) -> bool:
    """
    Fully provision an instance with all services.

    Args:
        config: Provisioning configuration

    Returns:
        True if provisioning succeeded
    """
    display = ProvisionDisplay()

    with Live(display, console=console, refresh_per_second=4) as live:
        # Step 1: Wait for SSH
        display.status = "Waiting for SSH..."
        if not wait_for_ssh(config.instance_ip, config.ssh_key_path):
            live.update(Text("[red]✗ SSH connection failed[/red]"))
            return False
        console.print("[green]✓[/green] SSH available")

        # Step 2: Run Ansible
        display.status = "Running Ansible playbook (this may take a few minutes)..."
        live.update(display)

    # Run Ansible outside of Live context to show output
    console.print("[cyan]Running Ansible provisioning...[/cyan]")
    if not run_ansible_playbook(config):
        console.print("[red]✗ Provisioning failed[/red]")
        return False
    console.print("[green]✓[/green] Provisioning complete")

    # Step 3: Wait for services
    display = ProvisionDisplay()
    with Live(display, console=console, refresh_per_second=4) as live:
        display.status = "Waiting for services to start..."
        if not wait_for_services(config.instance_ip, config.ssh_key_path):
            live.update(Text("[yellow]⚠ Services may still be starting[/yellow]"))
        else:
            live.update(Text("[green]✓ Services ready[/green]"))

    return True
