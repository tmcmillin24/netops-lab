import pytest
from fastapi.testclient import TestClient

from backend.app.errors import LabServiceError, UnknownDeviceError
from backend.app.main import create_app


class FakeLabService:
    def __init__(self):
        self.current_devices = [
            {"hostname": "PRNT01", "type": "printer"},
            {"hostname": "WS01", "type": "workstation"},
        ]
        self.devices = {
            "PRNT01": {"hostname": "PRNT01", "type": "printer"},
            "WS01": {"hostname": "WS01", "type": "workstation"},
        }

    def get_device_config(self, hostname, expected_type=None):
        name = hostname.upper()
        if name not in self.devices:
            raise UnknownDeviceError(name)
        device = self.devices[name]
        if expected_type and device["type"] != expected_type:
            raise UnknownDeviceError(name)
        return device

    async def device_status(self, device):
        if device["type"] == "printer":
            return {"hostname": device["hostname"], "device_type": "printer", "status": "ready", "live": {"queue": 0, "jobs": []}}
        return {"hostname": device["hostname"], "device_type": "workstation", "status": "online", "reachable": True}

    async def all_device_statuses(self):
        return [await self.device_status(device) for device in self.current_devices]

    async def overview(self):
        return {"total_devices": 17, "online_devices": 17, "offline_devices": 0, "printers_requiring_attention": 0, "printer_alerts": [], "impacted_devices": 0, "active_print_jobs": 0, "network_health": "healthy"}

    async def status_for_hostname(self, hostname):
        return await self.device_status(self.get_device_config(hostname))

    async def infrastructure_action(self, hostname, action):
        device = self.get_device_config(hostname)
        if device["type"] not in {"router_firewall", "layer3_core_switch", "access_switch"}:
            raise LabServiceError("unsupported_device_action", "Unsupported device.", 400)
        return {"hostname": device["hostname"], "status": "offline" if action == "disable" else "online"}

    async def request_endpoint(self, device, method="GET", path="/status", json=None):
        return {"name": "PRNT01", "queue": 0, "jobs": [], "status": "ready"}

    async def submit_job(self, hostname, job):
        self.get_device_config(hostname, "printer")
        self.get_device_config(job.source, "workstation")
        return {"name": hostname.upper(), "queue": 1, "jobs": [{"id": 1001, "device": job.source.upper(), "pages": job.pages or 4, "status": "queued"}]}

    async def printer_action(self, hostname, action):
        self.get_device_config(hostname, "printer")
        if action == "fail":
            raise LabServiceError("printer_offline", "PRNT01 is offline.", 409)
        return {"name": hostname.upper(), "status": action}

    async def workstation_action(self, hostname, action):
        self.get_device_config(hostname, "workstation")
        return {"name": hostname.upper(), "status": action}

    async def ping(self, request):
        self.get_device_config(request.source)
        self.get_device_config(request.destination)
        return {"source": request.source.upper(), "destination": request.destination.upper(), "success": True, "latency_ms": 0.2, "message": "reachable"}


@pytest.fixture
def service():
    return FakeLabService()


@pytest.fixture
def client(service):
    return TestClient(create_app(service))
