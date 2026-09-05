import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["LAB_EXTENSIONS_PATH"] = str(
    Path(__file__).resolve().parents[2] / "configs/lab_extensions.json"
)

from backend.app.errors import LabServiceError, UnknownDeviceError
from backend.app.main import create_app
from backend.app.services import provisioning


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
        return {"total_devices": 17, "online_devices": 17, "offline_devices": 0, "printers_requiring_attention": 0, "printer_alerts": [], "impacted_devices": 0, "impacted_device_alerts": [], "active_print_jobs": 0, "network_health": "healthy", "recent_events": [], "devices": await self.all_device_statuses()}

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

    async def diagnostic(self, request):
        self.get_device_config(request.source)
        self.get_device_config(request.destination)
        return {"diagnostic_type": request.diagnostic_type, "source": request.source.upper(), "destination": request.destination.upper(), "success": True, "message": "completed"}

    async def network_info(self, hostname):
        device = self.get_device_config(hostname)
        return {"hostname": device["hostname"], "routes": ["default via 10.10.10.1"], "neighbors": []}

    events = []


class FakeActiveDirectoryService:
    user = {
        "username": "jordan.lee",
        "display_name": "Jordan Lee",
        "role": "Finance Analyst",
        "department": "Administration & Finance",
        "floor": "Floor 1",
        "workstation": "WS01",
        "enabled": True,
        "locked": False,
        "password_expired": False,
        "account_type": "employee",
        "privileged": False,
        "remote": False,
        "bad_password_count": 0,
        "groups": ["Employees", "Finance"],
    }
    user_configs = {"jordan.lee": {**user, "workstation": "WS01"}}

    def known_user(self, username):
        try:
            return self.user_configs[username.lower()]
        except KeyError as error:
            raise LabServiceError("unknown_directory_user", "Unknown managed directory user.", 404) from error

    async def health(self):
        return {"domain": "netopslab.test", "domain_controller": "DC01", "status": "healthy", "dns_status": "healthy", "user_count": 12, "group_count": 6}

    async def account_health(self):
        return {"status": "healthy", "total_accounts": 1, "affected_accounts": 0, "locked_accounts": 0, "password_expired_accounts": 0, "disabled_accounts": 0, "affected_users": [], "status_source": "live_active_directory"}

    def reload_baseline(self):
        return None

    def record_event(self, message, event_type="info"):
        return None

    async def overview(self):
        return {**await self.health(), "users": [self.user], "groups": [{"name": "Finance", "description": "Finance access", "members": ["jordan.lee"]}], "password_policy": {"complexity": True, "minimum_length": 10, "lockout_threshold": 3}}

    async def users(self):
        return [self.user]

    async def get_user(self, username):
        if username.lower() != "jordan.lee":
            raise LabServiceError("unknown_directory_user", "Unknown managed directory user.", 404)
        return self.user

    async def groups(self):
        return [{"name": "Finance", "description": "Finance access", "members": ["jordan.lee"]}]

    async def user_action(self, username, action):
        await self.get_user(username)
        if action not in {"enable", "disable", "unlock"}:
            raise LabServiceError("unknown_action", "Unsupported directory user action.", 404)
        return {**self.user, "enabled": action != "disable"}

    async def reset_password(self, username):
        await self.get_user(username)
        return {"username": username, "temporary_password": "temporary-value", "message": "Temporary lab password generated. It will not be shown again."}

    async def membership_action(self, username, group_name, action):
        await self.get_user(username)
        if group_name != "Finance":
            raise LabServiceError("unknown_directory_group", "Unknown managed directory group.", 404)
        return self.user

    async def set_department_group(self, username, group_name=None):
        await self.get_user(username)

    async def create_user(self, config):
        return {"temporary_password": "temporary-created-value"}

    async def delete_user(self, username):
        return None


@pytest.fixture
def service():
    return FakeLabService()


@pytest.fixture(autouse=True)
def isolated_provisioning_state(tmp_path, monkeypatch):
    extensions = tmp_path / "lab_extensions.json"
    extensions.write_text((Path(__file__).resolve().parents[2] / "configs/lab_extensions.json").read_text())
    monkeypatch.setattr(provisioning, "STATE_DIR", tmp_path)
    monkeypatch.setattr(provisioning, "EXTENSIONS", extensions)
    monkeypatch.setattr(provisioning, "GENERATED_TOPOLOGY", tmp_path / "netops.generated.clab.yml")


@pytest.fixture
def client(service):
    return TestClient(create_app(service, FakeActiveDirectoryService()))
