"""Instance lifecycle management."""

import subprocess
import time
from typing import Optional
from rich.console import Console
from rich.live import Live
from rich.text import Text

from .lambda_api import LambdaAPI, Instance, LambdaAPIError

console = Console(force_terminal=True)


def check_service_health(ip: str, ssh_key_path: str, timeout: int = 5) -> bool:
    """
    Check if services are healthy via SSH.

    Args:
        ip: Instance IP address
        ssh_key_path: Path to SSH private key
        timeout: SSH command timeout

    Returns:
        True if status daemon /health returns OK
    """
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
                "curl -sf http://localhost:8080/health",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False


class StatusDisplay:
    """Dynamic status display that updates elapsed time on each render."""

    SPINNER_CHARS = "|/-\\"

    def __init__(self, start_time: float):
        self.start_time = start_time
        self.status = "booting"
        self.frame = 0
        self._time_func = time.time  # Capture reference before any mocking

    def __rich__(self):
        elapsed = int(self._time_func() - self.start_time)
        spinner_char = self.SPINNER_CHARS[self.frame % len(self.SPINNER_CHARS)]
        self.frame += 1
        return Text(f"{spinner_char} Status: {self.status} (elapsed: {elapsed}s)")


class InstanceManager:
    """Manage Lambda instance lifecycle."""

    def __init__(self, api: LambdaAPI):
        self.api = api

    def wait_for_ready(
        self, instance_id: str, timeout_seconds: int = 600
    ) -> Optional[Instance]:
        """
        Wait for instance to reach 'active' status and have an IP.

        Args:
            instance_id: Instance ID to wait for
            timeout_seconds: Maximum time to wait (default 10 minutes)

        Returns:
            Instance object when ready, or None if timeout
        """
        start_time = time.time()
        poll_interval = 10  # seconds between API calls
        status_display = StatusDisplay(start_time)

        with Live(status_display, console=console, refresh_per_second=4) as live:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time

                if elapsed > timeout_seconds:
                    console.print(
                        f"[red]Timeout waiting for instance after {elapsed:.0f}s[/red]"
                    )
                    return None

                try:
                    instance = self.api.get_instance(instance_id)
                    if instance is None:
                        console.print("[red]Instance not found[/red]")
                        return None

                    if instance.status == "active" and instance.ip:
                        live.update(Text("[green]✓ Instance ready![/green]"))
                        return instance
                    elif instance.status in ["terminated", "unhealthy"]:
                        console.print(f"[red]Instance in {instance.status} state[/red]")
                        return None

                    status_display.status = instance.status

                except LambdaAPIError as e:
                    console.print(f"[yellow]API error: {e}[/yellow]")

                time.sleep(poll_interval)

    def wait_for_services(
        self,
        ip: str,
        ssh_key_path: str,
        timeout_seconds: int = 300,
    ) -> bool:
        """
        Wait for services to be healthy on the instance.

        Args:
            ip: Instance IP address
            ssh_key_path: Path to SSH private key
            timeout_seconds: Maximum time to wait (default 5 minutes)

        Returns:
            True if services are healthy, False on timeout
        """
        start_time = time.time()
        poll_interval = 10
        status_display = StatusDisplay(start_time)
        status_display.status = "waiting for services"

        with Live(status_display, console=console, refresh_per_second=4) as live:
            while True:
                elapsed = time.time() - start_time

                if elapsed > timeout_seconds:
                    console.print(
                        f"[red]Timeout waiting for services after {elapsed:.0f}s[/red]"
                    )
                    return False

                if check_service_health(ip, ssh_key_path):
                    live.update(Text("[green]✓ Services healthy![/green]"))
                    return True

                status_display.status = f"waiting for services ({int(elapsed)}s)"
                time.sleep(poll_interval)

    def get_active_instance(self) -> Optional[Instance]:
        """
        Get the first active instance (assumes single-instance usage).

        Returns:
            Active instance or None
        """
        try:
            instances = self.api.list_instances()
            for instance in instances:
                if instance.status == "active":
                    return instance
            return None
        except LambdaAPIError as e:
            console.print(f"[red]Error listing instances: {e}[/red]")
            return None

    def wait_for_terminated(
        self, instance_id: str, timeout_seconds: int = 120
    ) -> bool:
        """
        Wait for instance to be terminated.

        Args:
            instance_id: Instance ID to wait for
            timeout_seconds: Maximum time to wait (default 2 minutes)

        Returns:
            True if terminated, False on timeout
        """
        start_time = time.time()
        poll_interval = 5
        status_display = StatusDisplay(start_time)
        status_display.status = "terminating"

        with Live(status_display, console=console, refresh_per_second=4) as live:
            while True:
                elapsed = time.time() - start_time

                if elapsed > timeout_seconds:
                    console.print(
                        f"[yellow]Timeout waiting for termination after {elapsed:.0f}s[/yellow]"
                    )
                    return False

                try:
                    instance = self.api.get_instance(instance_id)
                    if instance is None or instance.status == "terminated":
                        live.update(Text("[green]✓ Instance terminated[/green]"))
                        return True

                    status_display.status = f"terminating ({instance.status})"

                except LambdaAPIError:
                    # Instance not found likely means terminated
                    live.update(Text("[green]✓ Instance terminated[/green]"))
                    return True

                time.sleep(poll_interval)

    def poll_status(self, instance_id: str) -> Optional[Instance]:
        """
        Poll instance status once.

        Args:
            instance_id: Instance ID to check

        Returns:
            Current instance state or None
        """
        try:
            return self.api.get_instance(instance_id)
        except LambdaAPIError as e:
            console.print(f"[red]Error getting instance: {e}[/red]")
            return None
