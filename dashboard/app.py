#!/usr/bin/env python3
"""
Local FastAPI Dashboard for GPU Instance Monitoring.

Provides a web interface to view and manage GPU instances.
Port: 8092
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
import yaml


app = FastAPI(title="GPU Instance Dashboard", version="1.0.0")

# Template directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


class ConfigManager:
    """Manage configuration."""

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "gpu-dashboard"
        self.config_file = self.config_dir / "config.yaml"

    def load(self) -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        if not self.config_file.exists():
            return None

        with open(self.config_file) as f:
            return yaml.safe_load(f)

    def get_lambda_api_key(self) -> str:
        """Get Lambda API key from config."""
        config = self.load()
        if not config:
            raise ValueError("Configuration not found. Run 'soong configure' first.")
        return config.get("lambda", {}).get("api_key", "")

    def get_status_token(self) -> str:
        """Get status daemon token from config."""
        config = self.load()
        if not config:
            raise ValueError("Configuration not found. Run 'soong configure' first.")
        return config.get("status_daemon", {}).get("token", "")


config_manager = ConfigManager()


async def get_lambda_instances() -> List[Dict[str, Any]]:
    """Get instances from Lambda API."""
    api_key = config_manager.get_lambda_api_key()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                "https://cloud.lambdalabs.com/api/v1/instances",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except httpx.HTTPError as e:
            print(f"Error fetching instances: {e}")
            return []


async def get_instance_status(instance_ip: str) -> Optional[Dict[str, Any]]:
    """Get status from instance's status daemon."""
    token = config_manager.get_status_token()

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"http://{instance_ip}:8080/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return None


async def extend_instance_lease(instance_ip: str, hours: int) -> Dict[str, Any]:
    """Extend instance lease."""
    token = config_manager.get_status_token()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"http://{instance_ip}:8080/extend",
            headers={"Authorization": f"Bearer {token}"},
            data={"hours": str(hours)},
        )
        resp.raise_for_status()
        return resp.json()


async def terminate_instance(instance_id: str) -> None:
    """Terminate instance via Lambda API."""
    api_key = config_manager.get_lambda_api_key()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://cloud.lambdalabs.com/api/v1/instance-operations/terminate",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"instance_ids": [instance_id]},
        )
        resp.raise_for_status()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render dashboard HTML."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request}
    )


@app.get("/api/instances")
async def list_instances():
    """List all GPU instances with enhanced status."""
    instances = await get_lambda_instances()

    # Enrich with status daemon data
    enriched = []
    for instance in instances:
        enriched_instance = {
            "id": instance.get("id"),
            "name": instance.get("name", ""),
            "ip": instance.get("ip"),
            "status": instance.get("status"),
            "instance_type": instance.get("instance_type", {}).get("name", ""),
            "region": instance.get("region", {}).get("name", ""),
            "created_at": instance.get("created_at", ""),
        }

        # Get status daemon info if instance is running
        if instance.get("ip") and instance.get("status") == "active":
            status_data = await get_instance_status(instance["ip"])
            if status_data:
                enriched_instance["daemon_status"] = status_data

        enriched.append(enriched_instance)

    return JSONResponse(content=enriched)


@app.post("/api/extend/{instance_id}")
async def extend_lease(instance_id: str, hours: int = 2):
    """Extend instance lease by specified hours."""
    # First get instance IP
    instances = await get_lambda_instances()
    instance = next((i for i in instances if i.get("id") == instance_id), None)

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    if not instance.get("ip"):
        raise HTTPException(status_code=400, detail="Instance has no IP address")

    # Extend lease
    result = await extend_instance_lease(instance["ip"], hours)
    return JSONResponse(content=result)


@app.post("/api/terminate/{instance_id}")
async def terminate_instance_endpoint(instance_id: str):
    """Terminate instance."""
    await terminate_instance(instance_id)
    return JSONResponse(content={"status": "terminated", "instance_id": instance_id})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    print("Starting GPU Instance Dashboard on http://localhost:8092")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8092,
        log_level="info",
    )
