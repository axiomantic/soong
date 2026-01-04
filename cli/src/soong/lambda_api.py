"""Lambda Labs API client."""

import time
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class InstanceType:
    """Lambda instance type with pricing."""
    name: str
    description: str
    price_cents_per_hour: int
    vcpus: int
    memory_gib: int
    storage_gib: int
    regions_available: List[str]

    @classmethod
    def from_api_response(cls, name: str, data: Dict[str, Any]) -> "InstanceType":
        """Create InstanceType from API response."""
        instance_info = data.get("instance_type", {})
        specs = instance_info.get("specs", {})
        regions = [r["name"] for r in data.get("regions_with_capacity_available", [])]
        return cls(
            name=name,
            description=instance_info.get("description", name),
            price_cents_per_hour=instance_info.get("price_cents_per_hour", 0),
            vcpus=specs.get("vcpus", 0),
            memory_gib=specs.get("memory_gib", 0),
            storage_gib=specs.get("storage_gib", 0),
            regions_available=regions,
        )

    @property
    def price_per_hour(self) -> float:
        """Price in dollars per hour."""
        return self.price_cents_per_hour / 100.0

    def format_price(self) -> str:
        """Format price as string."""
        return f"${self.price_per_hour:.2f}/hr"

    def estimate_cost(self, hours: int) -> float:
        """Estimate total cost for given hours."""
        return self.price_per_hour * hours

    def format_for_selection(self) -> str:
        """Format for TUI selection display."""
        availability = "available" if self.regions_available else "no capacity"
        return f"{self.description} - {self.format_price()} ({availability})"


@dataclass
class Instance:
    """Lambda instance information."""
    id: str
    name: Optional[str]
    ip: Optional[str]
    status: str
    instance_type: str
    region: str
    created_at: Optional[str] = None
    lease_expires_at: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Instance":
        """Create Instance from API response.

        Handles API responses that may be missing optional fields, particularly
        during transitional states like 'booting' where fields like 'created_at'
        may not yet be populated.

        Required fields: id, status, instance_type (with 'name'), region (with 'name')
        Optional fields: name, ip, created_at, lease_expires_at
        """
        return cls(
            id=data["id"],
            name=data.get("name"),
            ip=data.get("ip"),
            status=data["status"],
            instance_type=data["instance_type"]["name"],
            region=data["region"]["name"],
            created_at=data.get("created_at"),
            lease_expires_at=data.get("lease_expires_at"),
        )

    def is_lease_expired(self) -> bool:
        """Check if the instance lease has expired."""
        if not self.lease_expires_at:
            return False

        try:
            expires_at = datetime.fromisoformat(self.lease_expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc).replace(tzinfo=expires_at.tzinfo) > expires_at
        except (ValueError, AttributeError):
            return False

    def lease_status_style(self) -> str:
        """
        Get rich style string for lease status.

        Returns:
            "red" if expired, "yellow" if expiring soon (< 1 hour), "green" otherwise
        """
        if not self.lease_expires_at:
            return "white"

        try:
            expires_at = datetime.fromisoformat(self.lease_expires_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc).replace(tzinfo=expires_at.tzinfo)
            time_left = expires_at - now

            if time_left.total_seconds() < 0:
                return "red"  # Expired
            elif time_left.total_seconds() < 3600:
                return "yellow"  # Expiring soon (< 1 hour)
            else:
                return "green"  # Safe
        except (ValueError, AttributeError):
            return "white"


@dataclass
class FileSystem:
    """Lambda filesystem information."""
    id: str
    name: str
    region: str
    mount_point: str
    is_in_use: bool

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "FileSystem":
        """Create FileSystem from Lambda API response."""
        try:
            required = ["id", "name", "region", "mount_point"]
            missing = [f for f in required if f not in data]
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            region = data["region"]
            if not isinstance(region, dict) or "name" not in region:
                raise ValueError("Invalid region structure: expected dict with 'name' field")

            return cls(
                id=data["id"],
                name=data["name"],
                region=region["name"],
                mount_point=data["mount_point"],
                is_in_use=data.get("is_in_use", False),
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"Failed to parse FileSystem from API response: {e}")


class LambdaAPIError(Exception):
    """Lambda API error."""
    pass


class LambdaAPI:
    """Lambda Labs API client with retry logic."""

    BASE_URL = "https://cloud.lambda.ai/api/v1"
    RETRY_MAX_ATTEMPTS = 3
    RETRY_BASE_DELAY = 1
    RETRY_BACKOFF_MULTIPLIER = 2

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _request_with_retry(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make API request with exponential backoff retry."""
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(1, self.RETRY_MAX_ATTEMPTS + 1):
            try:
                resp = self.session.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.exceptions.RequestException as e:
                if attempt == self.RETRY_MAX_ATTEMPTS:
                    raise LambdaAPIError(f"API request failed after {attempt} attempts: {e}")

                delay = self.RETRY_BASE_DELAY * (self.RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
                time.sleep(delay)

    def list_instances(self) -> List[Instance]:
        """List all instances."""
        resp = self._request_with_retry("GET", "instances")
        data = resp.json()
        return [Instance.from_api_response(item) for item in data.get("data", [])]

    def launch_instance(
        self,
        region: str,
        instance_type: str,
        ssh_key_names: List[str],
        filesystem_names: Optional[List[str]] = None,
        name: Optional[str] = None,
    ) -> str:
        """
        Launch a new instance.

        Returns instance ID.
        """
        payload = {
            "region_name": region,
            "instance_type_name": instance_type,
            "ssh_key_names": ssh_key_names,
        }

        if filesystem_names:
            payload["file_system_names"] = filesystem_names

        if name:
            payload["name"] = name

        resp = self._request_with_retry("POST", "instance-operations/launch", json=payload)
        data = resp.json()
        instance_ids = data.get("data", {}).get("instance_ids", [])

        if not instance_ids:
            raise LambdaAPIError("No instance ID returned from launch")

        return instance_ids[0]

    def terminate_instance(self, instance_id: str):
        """Terminate an instance."""
        payload = {"instance_ids": [instance_id]}
        self._request_with_retry("POST", "instance-operations/terminate", json=payload)

    def get_instance(self, instance_id: str) -> Optional[Instance]:
        """Get instance by ID."""
        instances = self.list_instances()
        for instance in instances:
            if instance.id == instance_id:
                return instance
        return None

    def list_ssh_keys(self) -> List[str]:
        """List SSH key names."""
        resp = self._request_with_retry("GET", "ssh-keys")
        data = resp.json()
        return [item["name"] for item in data.get("data", [])]

    def list_instance_types(self) -> List[InstanceType]:
        """List available instance types with pricing."""
        resp = self._request_with_retry("GET", "instance-types")
        data = resp.json().get("data", {})
        return [
            InstanceType.from_api_response(name, info)
            for name, info in data.items()
        ]

    def list_file_systems(self) -> List[FileSystem]:
        """List all filesystems."""
        resp = self._request_with_retry("GET", "file-systems")
        data = resp.json()
        return [FileSystem.from_api_response(item) for item in data.get("data", [])]

    def get_instance_type(self, name: str) -> Optional[InstanceType]:
        """Get a specific instance type by name."""
        types = self.list_instance_types()
        for t in types:
            if t.name == name:
                return t
        return None
