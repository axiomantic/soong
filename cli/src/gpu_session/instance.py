"""Instance lifecycle management."""

import time
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .lambda_api import LambdaAPI, Instance, LambdaAPIError

console = Console()


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
        poll_interval = 10  # seconds

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Waiting for instance to become ready...", total=None
            )

            while True:
                elapsed = time.time() - start_time
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
                        progress.update(
                            task, description="[green]Instance ready![/green]"
                        )
                        return instance
                    elif instance.status in ["terminated", "unhealthy"]:
                        console.print(f"[red]Instance in {instance.status} state[/red]")
                        return None

                    progress.update(
                        task,
                        description=f"Status: {instance.status} (elapsed: {elapsed:.0f}s)",
                    )

                except LambdaAPIError as e:
                    console.print(f"[yellow]API error: {e}[/yellow]")

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
