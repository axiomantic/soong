"""Integration tests for Worker deployment (requires Cloudflare account)."""

import os

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("CLOUDFLARE_API_TOKEN"),
    reason="CLOUDFLARE_API_TOKEN not set",
)
class TestWorkerIntegration:
    """Integration tests requiring real Cloudflare credentials."""

    def test_worker_health_endpoint(self):
        """Test Worker /health endpoint returns expected structure."""
        # Skip if no worker URL configured
        worker_url = os.getenv("SOONG_WORKER_URL")
        if not worker_url:
            pytest.skip("SOONG_WORKER_URL not set")

        import requests

        response = requests.get(f"{worker_url}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_worker_events_endpoint(self):
        """Test Worker /events endpoint returns list."""
        worker_url = os.getenv("SOONG_WORKER_URL")
        if not worker_url:
            pytest.skip("SOONG_WORKER_URL not set")

        import requests

        response = requests.get(
            f"{worker_url}/events", params={"hours": 1}, timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)
