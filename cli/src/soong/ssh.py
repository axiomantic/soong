"""SSH tunnel management."""

import os
import signal
import subprocess
from typing import Optional, List, Dict
from pathlib import Path
from rich.console import Console

console = Console()


def scan_local_ssh_keys() -> Dict[str, Path]:
    """
    Scan ~/.ssh for public keys and extract their comments.

    Returns:
        Dict mapping key comment/name to private key path
    """
    ssh_dir = Path.home() / ".ssh"
    keys = {}

    if not ssh_dir.exists():
        return keys

    for pub_file in ssh_dir.glob("*.pub"):
        try:
            content = pub_file.read_text().strip()
            parts = content.split()
            if len(parts) >= 3:
                # Format: type base64 comment
                comment = parts[2]
                # Private key is same name without .pub
                private_key = pub_file.with_suffix("")
                if private_key.exists():
                    keys[comment] = private_key
        except Exception:
            continue

    return keys


def find_matching_key(lambda_key_names: List[str], current_key_path: Path) -> Optional[Path]:
    """
    Find a local SSH key that matches one of Lambda's registered key names.

    Args:
        lambda_key_names: List of key names from Lambda API
        current_key_path: Currently configured key path

    Returns:
        Path to matching private key, or None if current key matches or no match found
    """
    local_keys = scan_local_ssh_keys()

    # Check if current key already matches
    try:
        current_pub = current_key_path.with_suffix(".pub")
        if current_pub.exists():
            content = current_pub.read_text().strip()
            parts = content.split()
            if len(parts) >= 3:
                current_comment = parts[2]
                if current_comment in lambda_key_names:
                    return None  # Current key is correct
    except Exception:
        pass

    # Find a matching key
    for lambda_name in lambda_key_names:
        if lambda_name in local_keys:
            return local_keys[lambda_name]

    return None


class SSHTunnelManager:
    """Manage SSH tunnels to GPU instances."""

    def __init__(self, ssh_key_path: str, lambda_key_names: Optional[List[str]] = None):
        self.ssh_key_path = Path(ssh_key_path).expanduser()
        self.tunnel_pid_file = Path.home() / ".config" / "gpu-dashboard" / "tunnel.pid"
        self.lambda_key_names = lambda_key_names or []

    def _suggest_key_fix(self) -> None:
        """Suggest SSH key configuration fix based on Lambda's registered keys."""
        if not self.lambda_key_names:
            console.print("\n[yellow]Hint:[/yellow] Check that your SSH key is registered with Lambda Labs")
            console.print("  https://cloud.lambda.ai/ssh-keys")
            return

        matching_key = find_matching_key(self.lambda_key_names, self.ssh_key_path)

        if matching_key:
            console.print(f"\n[yellow]SSH key mismatch detected![/yellow]")
            console.print(f"  Lambda expects: [cyan]{', '.join(self.lambda_key_names)}[/cyan]")
            console.print(f"  Config uses:    [red]{self.ssh_key_path}[/red]")
            console.print(f"\n[green]Fix:[/green] Update your config to use:")
            console.print(f"  [cyan]{matching_key}[/cyan]")
            console.print(f"\nRun: [dim]soong configure[/dim] or edit ~/.config/gpu-dashboard/config.yaml")
        else:
            console.print(f"\n[yellow]SSH key issue:[/yellow]")
            console.print(f"  Lambda expects key named: [cyan]{', '.join(self.lambda_key_names)}[/cyan]")
            console.print(f"  No matching local key found in ~/.ssh/")
            console.print(f"\n[green]Options:[/green]")
            console.print(f"  1. Add your current key to Lambda: https://cloud.lambda.ai/ssh-keys")
            console.print(f"  2. Or download the correct private key to ~/.ssh/")

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
                stderr = result.stderr or ""
                console.print(f"[red]SSH tunnel failed: {stderr}[/red]")

                # Detect permission denied and suggest fix
                if "Permission denied" in stderr or "publickey" in stderr.lower():
                    self._suggest_key_fix()

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

            if result.returncode != 0:
                # Exit code 255 typically indicates SSH connection failure
                if result.returncode == 255:
                    console.print("[red]SSH connection failed[/red]")
                    self._suggest_key_fix()
                return False

            return True
        except KeyboardInterrupt:
            console.print("\n[yellow]SSH session interrupted by user[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]Error connecting via SSH: {e}[/red]")
            return False
