"""Lambda Labs API client."""

import time
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Instance:
    """Lambda instance information."""
    id: str
    name: Optional[str]
    ip: Optional[str]
    status: str
    instance_type: str
    region: str
    created_at: str
    lease_expires_at: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Instance":
        """Create Instance from API response."""
        return cls(
            id=data["id"],
            name=data.get("name"),
            ip=data.get("ip"),
            status=data["status"],
            instance_type=data["instance_type"]["name"],
            region=data["region"]["name"],
            created_at=data["created_at"],
            lease_expires_at=data.get("lease_expires_at"),
        )

    def is_lease_expired(self) -> bool:
        """Check if the instance lease has expired."""
        if not self.lease_expires_at:
            return False

        try:
            expires_at = datetime.fromisoformat(self.lease_expires_at.replace('Z', '+00:00'))
            return datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at
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
            now = datetime.utcnow().replace(tzinfo=expires_at.tzinfo)
            time_left = expires_at - now

            if time_left.total_seconds() < 0:
                return "red"  # Expired
            elif time_left.total_seconds() < 3600:
                return "yellow"  # Expiring soon (< 1 hour)
            else:
                return "green"  # Safe
        except (ValueError, AttributeError):
            return "white"


class LambdaAPIError(Exception):
    """Lambda API error."""
    pass


class LambdaAPI:
    """Lambda Labs API client with retry logic."""

    BASE_URL = "https://cloud.lambdalabs.com/api/v1"
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

    def list_instance_types(self) -> Dict[str, Any]:
        """List available instance types."""
        resp = self._request_with_retry("GET", "instance-types")
        return resp.json().get("data", {})
