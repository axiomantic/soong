"""SSH tunnel management."""

import os
import signal
import socket
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from rich.console import Console

console = Console()


def is_port_available(port: int) -> bool:
    """
    Check if a local port is available for binding.

    Args:
        port: Port number to check

    Returns:
        True if port is available, False if in use
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def find_available_port(start_port: int, max_attempts: int = 100) -> int:
    """
    Find an available port starting from start_port, incrementing by 1.

    Args:
        start_port: Port to start searching from
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found within max_attempts
    """
    for offset in range(max_attempts):
        port = start_port + offset
        if is_port_available(port):
            return port

    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts - 1}"
    )


@dataclass
class TunnelPorts:
    """Actual ports used for tunnel forwarding."""
    sglang: int
    n8n: int
    status: int


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
        auto_find_ports: bool = True,
    ) -> Optional[TunnelPorts]:
        """
        Start SSH tunnel with port forwarding.

        Args:
            instance_ip: Remote instance IP
            local_ports: List of local ports to forward from (defaults to try first)
            remote_ports: List of remote ports to forward to
            username: SSH username (default: ubuntu)
            auto_find_ports: If True, find available ports starting from local_ports

        Returns:
            TunnelPorts with actual ports used, or None if failed
        """
        if len(local_ports) != len(remote_ports):
            console.print("[red]Error: local_ports and remote_ports must match[/red]")
            return None

        # Check if tunnel already running
        if self.is_tunnel_running():
            console.print("[yellow]Tunnel already running. Stop it first.[/yellow]")
            return None

        # Find available ports if auto_find_ports is enabled
        actual_local_ports = []
        if auto_find_ports:
            for default_port in local_ports:
                try:
                    available_port = find_available_port(default_port)
                    actual_local_ports.append(available_port)
                    if available_port != default_port:
                        console.print(
                            f"[dim]Port {default_port} in use, using {available_port}[/dim]"
                        )
                except RuntimeError as e:
                    console.print(f"[red]Error finding available port: {e}[/red]")
                    return None
        else:
            actual_local_ports = local_ports

        # Build SSH command with port forwarding
        forwarding_args = []
        for local, remote in zip(actual_local_ports, remote_ports):
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

                return None

            # Build TunnelPorts result
            tunnel_ports = TunnelPorts(
                sglang=actual_local_ports[0],
                n8n=actual_local_ports[1],
                status=actual_local_ports[2],
            )

            # Find and store tunnel PID with port info
            pid = self._find_tunnel_pid(instance_ip)
            if pid:
                self.tunnel_pid_file.parent.mkdir(parents=True, exist_ok=True)
                # Store PID and ports as JSON for later retrieval
                import json
                tunnel_info = {
                    "pid": pid,
                    "ports": {
                        "sglang": tunnel_ports.sglang,
                        "n8n": tunnel_ports.n8n,
                        "status": tunnel_ports.status,
                    },
                }
                self.tunnel_pid_file.write_text(json.dumps(tunnel_info))
                console.print(f"[green]SSH tunnel started (PID: {pid})[/green]")

                for local, remote in zip(actual_local_ports, remote_ports):
                    console.print(f"  localhost:{local} -> {instance_ip}:{remote}")

                return tunnel_ports
            else:
                console.print("[yellow]Tunnel may have started but PID not found[/yellow]")
                return tunnel_ports

        except subprocess.TimeoutExpired:
            console.print("[red]SSH tunnel command timed out[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Error starting tunnel: {e}[/red]")
            return None

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
            import json
            content = self.tunnel_pid_file.read_text().strip()

            # Handle both old (plain int) and new (JSON) format
            try:
                tunnel_info = json.loads(content)
                pid = tunnel_info["pid"]
            except (json.JSONDecodeError, KeyError):
                # Fallback for old format
                pid = int(content)

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
            import json
            content = self.tunnel_pid_file.read_text().strip()

            # Handle both old (plain int) and new (JSON) format
            try:
                tunnel_info = json.loads(content)
                pid = tunnel_info["pid"]
            except (json.JSONDecodeError, KeyError):
                # Fallback for old format
                pid = int(content)

            os.kill(pid, 0)  # Check if process exists
            return True
        except (ProcessLookupError, ValueError):
            # Clean up stale PID file
            self.tunnel_pid_file.unlink()
            return False

    def get_tunnel_ports(self) -> Optional[TunnelPorts]:
        """
        Get the ports used by the current tunnel.

        Returns:
            TunnelPorts if tunnel is running, None otherwise
        """
        if not self.tunnel_pid_file.exists():
            return None

        try:
            import json
            content = self.tunnel_pid_file.read_text().strip()
            tunnel_info = json.loads(content)

            # Verify tunnel is still running
            pid = tunnel_info["pid"]
            os.kill(pid, 0)

            ports = tunnel_info.get("ports", {})
            return TunnelPorts(
                sglang=ports.get("sglang", 8000),
                n8n=ports.get("n8n", 5678),
                status=ports.get("status", 8080),
            )
        except (json.JSONDecodeError, KeyError, ProcessLookupError, ValueError):
            return None

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
