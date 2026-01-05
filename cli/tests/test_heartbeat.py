"""Tests for status daemon heartbeat functionality.

These tests verify the heartbeat push mechanism using pytest-httpserver
to precisely validate the requests sent to the Worker.

Since send_heartbeat() lives in a Jinja2 template, we test the logic
by implementing a testable version that mirrors the template behavior.
"""

import json
import pytest
import requests
from datetime import datetime
from pytest_httpserver import HTTPServer


class HeartbeatSender:
    """
    Testable implementation of send_heartbeat() from status_daemon.py.j2

    Mirrors the template logic exactly for testing purposes.
    """

    def __init__(
        self,
        worker_url: str,
        status_token: str,
        boot_time: datetime,
        get_instance_id: callable,
        get_model_loaded: callable,
        sglang_metrics_healthy: bool = True,
        n8n_metrics_healthy: bool = True,
    ):
        self.worker_url = worker_url
        self.status_token = status_token
        self.boot_time = boot_time
        self.get_instance_id = get_instance_id
        self.get_model_loaded = get_model_loaded
        self.sglang_metrics_healthy = sglang_metrics_healthy
        self.n8n_metrics_healthy = n8n_metrics_healthy
        self.last_error = None

    def send_heartbeat(self) -> bool:
        """
        Push heartbeat to Worker (mirrors status_daemon.py.j2 send_heartbeat).

        Returns True if successful, False otherwise.
        """
        if not self.worker_url:
            return False  # Worker not configured

        try:
            payload = {
                "instance_id": self.get_instance_id(),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "uptime_minutes": int((datetime.utcnow() - self.boot_time).total_seconds() / 60),
                "model_loaded": self.get_model_loaded(),
                "sglang_healthy": self.sglang_metrics_healthy,
                "n8n_healthy": self.n8n_metrics_healthy,
            }
            response = requests.post(
                f"{self.worker_url}/heartbeat",
                json=payload,
                headers={"Authorization": f"Bearer {self.status_token}"},
                timeout=5,
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            self.last_error = str(e)
            return False


class TestHeartbeatRequest:
    """Tests verifying exact request format sent to Worker."""

    def test_heartbeat_sends_correct_method_and_path(self, httpserver: HTTPServer):
        """Verify heartbeat uses POST to /heartbeat endpoint."""
        httpserver.expect_request(
            "/heartbeat",
            method="POST",
        ).respond_with_json({"success": True})

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="test-token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test123",
            get_model_loaded=lambda: "test-model",
        )

        result = sender.send_heartbeat()

        assert result is True
        httpserver.check_assertions()

    def test_heartbeat_sends_bearer_auth_header(self, httpserver: HTTPServer):
        """Verify heartbeat includes correct Authorization header."""
        httpserver.expect_request(
            "/heartbeat",
            method="POST",
            headers={"Authorization": "Bearer my-secret-token"},
        ).respond_with_json({"success": True})

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="my-secret-token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        result = sender.send_heartbeat()

        assert result is True
        httpserver.check_assertions()

    def test_heartbeat_sends_json_content_type(self, httpserver: HTTPServer):
        """Verify heartbeat sends JSON content type."""
        httpserver.expect_request(
            "/heartbeat",
            method="POST",
            headers={"Content-Type": "application/json"},
        ).respond_with_json({"success": True})

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        sender.send_heartbeat()
        httpserver.check_assertions()

    def test_heartbeat_payload_contains_instance_id(self, httpserver: HTTPServer):
        """Verify payload contains correct instance_id."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-abc123def456",
            get_model_loaded=lambda: "model",
        )

        sender.send_heartbeat()

        assert len(received_payloads) == 1
        assert received_payloads[0]["instance_id"] == "i-abc123def456"

    def test_heartbeat_payload_contains_model_loaded(self, httpserver: HTTPServer):
        """Verify payload contains correct model_loaded."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "deepseek-r1-70b",
        )

        sender.send_heartbeat()

        assert received_payloads[0]["model_loaded"] == "deepseek-r1-70b"

    def test_heartbeat_payload_contains_health_status(self, httpserver: HTTPServer):
        """Verify payload contains sglang_healthy and n8n_healthy flags."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
            sglang_metrics_healthy=True,
            n8n_metrics_healthy=False,
        )

        sender.send_heartbeat()

        assert received_payloads[0]["sglang_healthy"] is True
        assert received_payloads[0]["n8n_healthy"] is False

    def test_heartbeat_payload_contains_timestamp(self, httpserver: HTTPServer):
        """Verify payload contains valid ISO timestamp."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        sender.send_heartbeat()

        timestamp = received_payloads[0]["timestamp"]
        assert timestamp.endswith("Z")
        # Should be parseable as ISO timestamp
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_heartbeat_payload_contains_uptime_minutes(self, httpserver: HTTPServer):
        """Verify payload contains uptime_minutes calculated from boot time."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        # Boot time 90 minutes ago
        from datetime import timedelta
        boot_time = datetime.utcnow() - timedelta(minutes=90)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=boot_time,
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        sender.send_heartbeat()

        uptime = received_payloads[0]["uptime_minutes"]
        assert isinstance(uptime, int)
        assert 89 <= uptime <= 91  # Allow 1 minute tolerance

    def test_heartbeat_payload_complete_structure(self, httpserver: HTTPServer):
        """Verify payload contains all required fields with correct types."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-complete-test",
            get_model_loaded=lambda: "qwen2.5-coder-32b",
            sglang_metrics_healthy=True,
            n8n_metrics_healthy=True,
        )

        sender.send_heartbeat()

        payload = received_payloads[0]

        # Verify all fields present
        assert "instance_id" in payload
        assert "timestamp" in payload
        assert "uptime_minutes" in payload
        assert "model_loaded" in payload
        assert "sglang_healthy" in payload
        assert "n8n_healthy" in payload

        # Verify types
        assert isinstance(payload["instance_id"], str)
        assert isinstance(payload["timestamp"], str)
        assert isinstance(payload["uptime_minutes"], int)
        assert isinstance(payload["model_loaded"], str)
        assert isinstance(payload["sglang_healthy"], bool)
        assert isinstance(payload["n8n_healthy"], bool)


class TestHeartbeatErrorHandling:
    """Tests verifying error handling behavior."""

    def test_heartbeat_returns_false_when_worker_url_empty(self):
        """Verify heartbeat returns False when worker_url is empty."""
        sender = HeartbeatSender(
            worker_url="",
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        result = sender.send_heartbeat()

        assert result is False

    def test_heartbeat_returns_false_when_worker_url_none(self):
        """Verify heartbeat returns False when worker_url is None."""
        sender = HeartbeatSender(
            worker_url=None,
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        result = sender.send_heartbeat()

        assert result is False

    def test_heartbeat_handles_connection_error(self, httpserver: HTTPServer):
        """Verify heartbeat handles connection errors gracefully."""
        # Don't start the server - connection will fail
        sender = HeartbeatSender(
            worker_url="http://localhost:59999",  # Non-existent server
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        result = sender.send_heartbeat()

        assert result is False
        assert sender.last_error is not None

    def test_heartbeat_handles_http_error_response(self, httpserver: HTTPServer):
        """Verify heartbeat handles HTTP error responses."""
        httpserver.expect_request("/heartbeat", method="POST").respond_with_json(
            {"error": "unauthorized"}, status=401
        )

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="wrong-token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        result = sender.send_heartbeat()

        assert result is False
        httpserver.check_assertions()

    def test_heartbeat_handles_500_error(self, httpserver: HTTPServer):
        """Verify heartbeat handles server errors."""
        httpserver.expect_request("/heartbeat", method="POST").respond_with_json(
            {"error": "internal error"}, status=500
        )

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        result = sender.send_heartbeat()

        assert result is False


class TestHeartbeatIntegration:
    """Integration tests for heartbeat lifecycle."""

    def test_multiple_heartbeats_to_same_endpoint(self, httpserver: HTTPServer):
        """Verify multiple heartbeats can be sent."""
        call_count = [0]

        def count_requests(request):
            call_count[0] += 1
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(count_requests)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
        )

        # Send 3 heartbeats
        sender.send_heartbeat()
        sender.send_heartbeat()
        sender.send_heartbeat()

        assert call_count[0] == 3

    def test_heartbeat_with_changing_health_status(self, httpserver: HTTPServer):
        """Verify heartbeat reflects current health status."""
        received_payloads = []

        def capture_request(request):
            received_payloads.append(json.loads(request.data))
            return '{"success": true}'

        httpserver.expect_request("/heartbeat", method="POST").respond_with_handler(capture_request)

        sender = HeartbeatSender(
            worker_url=httpserver.url_for(""),
            status_token="token",
            boot_time=datetime.utcnow(),
            get_instance_id=lambda: "i-test",
            get_model_loaded=lambda: "model",
            sglang_metrics_healthy=True,
            n8n_metrics_healthy=True,
        )

        # First heartbeat - all healthy
        sender.send_heartbeat()

        # Health degrades
        sender.sglang_metrics_healthy = False
        sender.send_heartbeat()

        assert received_payloads[0]["sglang_healthy"] is True
        assert received_payloads[1]["sglang_healthy"] is False
