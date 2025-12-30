"""SSH tunnel management."""

import os
import signal
import subprocess
from typing import Optional, List
from pathlib import Path
from rich.console import Console

console = Console()


class SSHTunnelManager:
    """Manage SSH tunnels to GPU instances."""

    def __init__(self, ssh_key_path: str):
        self.ssh_key_path = Path(ssh_key_path).expanduser()
        self.tunnel_pid_file = Path.home() / ".config" / "gpu-dashboard" / "tunnel.pid"

    def start_tunnel(
        self,
        instance_ip: str,
        local_ports: List[int],
        remote_ports: List[int],
        username: str = "ubuntu",
    ) -> bool:
        """
        Start SSH tunnel with port forwarding.

        Args:
            instance_ip: Remote instance IP
            local_ports: List of local ports to forward from
            remote_ports: List of remote ports to forward to
            username: SSH username (default: ubuntu)

        Returns:
            True if tunnel started successfully
        """
        if len(local_ports) != len(remote_ports):
            console.print("[red]Error: local_ports and remote_ports must match[/red]")
            return False

        # Check if tunnel already running
        if self.is_tunnel_running():
            console.print("[yellow]Tunnel already running. Stop it first.[/yellow]")
            return False

        # Build SSH command with port forwarding
        forwarding_args = []
        for local, remote in zip(local_ports, remote_ports):
            forwarding_args.extend(["-L", f"{local}:localhost:{remote}"])

        ssh_command = [
            "ssh",
            "-N",  # No remote command
            "-f",  # Background
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=60",
            "-i", str(self.ssh_key_path),
            *forwarding_args,
            f"{username}@{instance_ip}",
        ]

        try:
            console.print(f"[cyan]Starting SSH tunnel to {instance_ip}...[/cyan]")
            result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                console.print(f"[red]SSH tunnel failed: {result.stderr}[/red]")
                return False

            # Find and store tunnel PID
            pid = self._find_tunnel_pid(instance_ip)
            if pid:
                self.tunnel_pid_file.parent.mkdir(parents=True, exist_ok=True)
                self.tunnel_pid_file.write_text(str(pid))
                console.print(f"[green]SSH tunnel started (PID: {pid})[/green]")

                for local, remote in zip(local_ports, remote_ports):
                    console.print(f"  localhost:{local} -> {instance_ip}:{remote}")

                return True
            else:
                console.print("[yellow]Tunnel may have started but PID not found[/yellow]")
                return True

        except subprocess.TimeoutExpired:
            console.print("[red]SSH tunnel command timed out[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error starting tunnel: {e}[/red]")
            return False

    def stop_tunnel(self) -> bool:
        """
        Stop running SSH tunnel.

        Returns:
            True if tunnel stopped successfully
        """
        if not self.tunnel_pid_file.exists():
            console.print("[yellow]No tunnel PID file found[/yellow]")
            return False

        try:
            pid = int(self.tunnel_pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            self.tunnel_pid_file.unlink()
            console.print(f"[green]Stopped tunnel (PID: {pid})[/green]")
            return True
        except ProcessLookupError:
            console.print("[yellow]Tunnel process not found (already stopped?)[/yellow]")
            self.tunnel_pid_file.unlink()
            return True
        except Exception as e:
            console.print(f"[red]Error stopping tunnel: {e}[/red]")
            return False

    def is_tunnel_running(self) -> bool:
        """
        Check if tunnel is currently running.

        Returns:
            True if tunnel is running
        """
        if not self.tunnel_pid_file.exists():
            return False

        try:
            pid = int(self.tunnel_pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ProcessLookupError, ValueError):
            # Clean up stale PID file
            self.tunnel_pid_file.unlink()
            return False

    def _find_tunnel_pid(self, instance_ip: str) -> Optional[int]:
        """
        Find PID of SSH tunnel process by matching IP.

        Args:
            instance_ip: Remote instance IP to match

        Returns:
            PID of tunnel process or None
        """
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"ssh.*{instance_ip}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split()[0])
        except Exception:
            pass
        return None

    def connect_ssh(
        self,
        instance_ip: str,
        username: str = "ubuntu",
    ) -> bool:
        """
        Open interactive SSH session to instance.

        Args:
            instance_ip: Remote instance IP
            username: SSH username (default: ubuntu)

        Returns:
            True if SSH session completed successfully
        """
        ssh_command = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-i", str(self.ssh_key_path),
            f"{username}@{instance_ip}",
        ]

        try:
            console.print(f"[cyan]Connecting to {instance_ip}...[/cyan]")
            result = subprocess.run(ssh_command)
            return result.returncode == 0
        except Exception as e:
            console.print(f"[red]Error connecting via SSH: {e}[/red]")
            return False
