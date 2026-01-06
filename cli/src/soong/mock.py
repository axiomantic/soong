"""Mock Lambda API for demo and testing purposes.

This module provides a MockLambdaAPI class that simulates Lambda Labs API responses
without making actual API calls. Used by the hidden --mock CLI flag to enable
demo recordings and testing without incurring GPU costs.

Usage:
    soong --mock start -y   # Simulates launching an instance
    soong --mock status     # Shows mock instance status
    soong --mock stop -y    # Simulates terminating an instance

The mock persists state to a file so it survives across CLI invocations,
simulating realistic instance lifecycle transitions (booting -> active -> terminated).
This enables VHS demo recordings where each command is a separate process.
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field, asdict

from .lambda_api import Instance, InstanceType, FileSystem, LambdaAPIError


# Mock state file location (in temp directory for easy cleanup)
MOCK_STATE_FILE = Path("/tmp/soong-mock-state.json")


@dataclass
class MockState:
    """Persistent state for mock API across CLI invocations."""
    instances: List[dict] = field(default_factory=list)
    launch_count: int = 0
    boot_start_time: Optional[float] = None

    def get_instance(self, instance_id: str) -> Optional[dict]:
        """Get instance by ID from state."""
        for inst in self.instances:
            if inst["id"] == instance_id:
                return inst
        return None

    def update_instance_status(self, instance_id: str, status: str, ip: Optional[str] = None):
        """Update instance status in state."""
        for inst in self.instances:
            if inst["id"] == instance_id:
                inst["status"] = status
                if ip:
                    inst["ip"] = ip
                break
        self.save()

    def save(self):
        """Persist state to file."""
        data = {
            "instances": self.instances,
            "launch_count": self.launch_count,
            "boot_start_time": self.boot_start_time,
        }
        MOCK_STATE_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> "MockState":
        """Load state from file or create new."""
        if MOCK_STATE_FILE.exists():
            try:
                data = json.loads(MOCK_STATE_FILE.read_text())
                return cls(
                    instances=data.get("instances", []),
                    launch_count=data.get("launch_count", 0),
                    boot_start_time=data.get("boot_start_time"),
                )
            except (json.JSONDecodeError, KeyError):
                pass
        return cls()


# Module-level cache
_mock_state: Optional[MockState] = None


def get_mock_state() -> MockState:
    """Get or load the mock state."""
    global _mock_state
    if _mock_state is None:
        _mock_state = MockState.load()
    return _mock_state


def reset_mock_state():
    """Reset mock state (for testing and cleanup)."""
    global _mock_state
    _mock_state = None
    if MOCK_STATE_FILE.exists():
        MOCK_STATE_FILE.unlink()


# Mock instance types with realistic pricing
MOCK_INSTANCE_TYPES = [
    {
        "name": "gpu_1x_a10",
        "description": "1x A10 (24 GB)",
        "price_cents_per_hour": 60,
        "vcpus": 30,
        "memory_gib": 200,
        "storage_gib": 512,
        "regions_available": ["us-west-1", "us-east-1"],
    },
    {
        "name": "gpu_1x_rtx6000",
        "description": "1x RTX 6000 Ada (48 GB)",
        "price_cents_per_hour": 80,
        "vcpus": 14,
        "memory_gib": 46,
        "storage_gib": 512,
        "regions_available": ["us-west-1"],
    },
    {
        "name": "gpu_1x_a6000",
        "description": "1x A6000 (48 GB)",
        "price_cents_per_hour": 80,
        "vcpus": 14,
        "memory_gib": 46,
        "storage_gib": 512,
        "regions_available": ["us-west-1", "us-east-1"],
    },
    {
        "name": "gpu_1x_a100_sxm4_80gb",
        "description": "1x A100 SXM4 (80 GB)",
        "price_cents_per_hour": 129,
        "vcpus": 30,
        "memory_gib": 200,
        "storage_gib": 512,
        "regions_available": ["us-west-1"],
    },
    {
        "name": "gpu_8x_a100_80gb_sxm4",
        "description": "8x A100 SXM4 (80 GB)",
        "price_cents_per_hour": 1032,
        "vcpus": 240,
        "memory_gib": 1800,
        "storage_gib": 20000,
        "regions_available": [],
    },
]


class MockLambdaAPI:
    """Mock Lambda Labs API that simulates realistic responses.

    Maintains state to simulate instance lifecycle:
    - launch_instance() creates a "booting" instance
    - get_instance() returns "active" after simulated boot time
    - terminate_instance() marks instance as "terminated"

    This enables demo recordings to show realistic CLI behavior without
    incurring actual GPU costs.
    """

    # Simulated boot time in seconds (shortened for demo)
    MOCK_BOOT_TIME = 5.0

    def __init__(self, api_key: str):
        """Initialize mock API (api_key ignored but accepted for interface compatibility)."""
        self.api_key = api_key
        self.state = get_mock_state()

    def list_instances(self) -> List[Instance]:
        """List all mock instances."""
        instances = []
        state_modified = False
        for inst_data in self.state.instances:
            # Check if booting instance should transition to active
            if inst_data["status"] == "booting" and self.state.boot_start_time:
                elapsed = time.time() - self.state.boot_start_time
                if elapsed >= self.MOCK_BOOT_TIME:
                    inst_data["status"] = "active"
                    inst_data["ip"] = "203.0.113.42"  # Mock IP (TEST-NET-3)
                    state_modified = True

            instances.append(Instance(
                id=inst_data["id"],
                name=inst_data.get("name"),
                ip=inst_data.get("ip"),
                status=inst_data["status"],
                instance_type=inst_data["instance_type"],
                region=inst_data["region"],
                created_at=inst_data.get("created_at"),
                lease_expires_at=inst_data.get("lease_expires_at"),
            ))

        # Persist any status transitions
        if state_modified:
            self.state.save()

        return instances

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        instances = self.list_instances()
        for inst in instances:
            if inst.id == instance_id:
                return inst
        return None

    def launch_instance(
        self,
        region: str,
        instance_type: str,
        ssh_key_names: List[str],
        filesystem_names: Optional[List[str]] = None,
        name: Optional[str] = None,
    ) -> str:
        """Launch a mock instance. Accepts any GPU type and region for demo flexibility."""

        # Generate mock instance ID
        self.state.launch_count += 1
        instance_id = f"i-mock-{self.state.launch_count:04d}-demo"

        # Calculate lease expiry
        now = datetime.now(timezone.utc)
        lease_hours = 4  # Default lease
        lease_expires = now + timedelta(hours=lease_hours)

        # Create mock instance in booting state
        inst_data = {
            "id": instance_id,
            "name": name or f"mock-instance-{self.state.launch_count}",
            "ip": None,  # No IP until active
            "status": "booting",
            "instance_type": instance_type,
            "region": region,
            "created_at": now.isoformat(),
            "lease_expires_at": lease_expires.isoformat(),
        }

        self.state.instances.append(inst_data)
        self.state.boot_start_time = time.time()
        self.state.save()  # Persist state for subsequent CLI calls

        return instance_id

    def terminate_instance(self, instance_id: str):
        """Terminate a mock instance."""
        inst = self.state.get_instance(instance_id)
        if inst is None:
            raise LambdaAPIError(f"Instance not found: {instance_id}")

        self.state.update_instance_status(instance_id, "terminated")

    def list_ssh_keys(self) -> List[str]:
        """List mock SSH keys."""
        return ["demo-key", "backup-key"]

    def list_instance_types(self) -> List[InstanceType]:
        """List available mock instance types."""
        return [
            InstanceType(
                name=t["name"],
                description=t["description"],
                price_cents_per_hour=t["price_cents_per_hour"],
                vcpus=t["vcpus"],
                memory_gib=t["memory_gib"],
                storage_gib=t["storage_gib"],
                regions_available=t["regions_available"],
            )
            for t in MOCK_INSTANCE_TYPES
        ]

    def get_instance_type(self, name: str) -> Optional[InstanceType]:
        """Get a specific mock instance type. Returns fake data for unknown types."""
        for t in self.list_instance_types():
            if t.name == name:
                return t
        # Return fake instance type for any unknown GPU (demo flexibility)
        return InstanceType(
            name=name,
            description=name.replace("_", " ").replace("gpu ", "").title(),
            price_cents_per_hour=129,  # Default to ~$1.29/hr
            vcpus=30,
            memory_gib=200,
            storage_gib=512,
            regions_available=["us-west-1", "us-east-1"],
        )

    def list_file_systems(self) -> List[FileSystem]:
        """List mock filesystems."""
        return [
            FileSystem(
                id="fs-mock-001",
                name="coding-stack",
                region="us-west-1",
                mount_point="/lambda/nfs/coding-stack",
                is_in_use=False,
            ),
        ]
