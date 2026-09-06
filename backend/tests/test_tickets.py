import asyncio

import pytest

from backend.app.errors import LabServiceError
from backend.app.services.tickets import TicketService


class FakeLab:
    def __init__(self):
        self.devices = {
            "WS01": {"hostname": "WS01", "device_type": "workstation", "status": "online", "assigned_user": "jordan.lee", "connected_switch": "SW01", "live": {}},
            "PRNT01": {"hostname": "PRNT01", "device_type": "printer", "status": "ready", "live": {"toner": 100}},
        }
        self.events = []

    async def all_device_statuses(self):
        return list(self.devices.values())

    async def status_for_hostname(self, hostname):
        if hostname not in self.devices:
            raise LabServiceError("unknown_device", "Unknown device.", 404)
        return self.devices[hostname]

    async def workstation_action(self, hostname, action):
        self.devices[hostname]["status"] = "offline" if action == "offline" else "online"

    async def printer_action(self, hostname, action):
        device = self.devices[hostname]
        if action == "offline":
            device["status"] = "offline"
        elif action == "ready":
            device["status"] = "ready" if device["live"]["toner"] else "attention"
        elif action == "empty-toner":
            device["live"]["toner"] = 0
            device["status"] = "attention"
        elif action == "refill-toner":
            device["live"]["toner"] = 100
            device["status"] = "ready"

    async def ping(self, request):
        return {"source": request.source, "destination": request.destination, "success": True}

    def record_event(self, hostname, message, event_type):
        self.events.append((hostname, message, event_type))


class FakeDirectory:
    def __init__(self):
        self.user = {"username": "jordan.lee", "display_name": "Jordan Lee", "enabled": True, "workstation": "WS01", "groups": ["Employees", "Finance"], "account_type": "employee"}

    async def users(self):
        return [self.user]

    async def get_user(self, username):
        return self.user

    async def membership_action(self, username, group, action):
        if action == "remove":
            self.user["groups"].remove(group)
        elif group not in self.user["groups"]:
            self.user["groups"].append(group)


class FakeFiles:
    def __init__(self):
        self.online = True
        self.smb = True
        self.shares = {"Finance": True, "Public": True}

    async def overview(self):
        return {"status": "online" if self.online else "offline", "smb_running": self.smb, "shares": [{"name": name, "enabled": enabled} for name, enabled in self.shares.items()]}

    async def share(self, name):
        return {"name": name, "enabled": self.shares[name]}

    async def fault(self, action, share=None):
        if action == "service-stop":
            self.smb = False
        elif action == "share-disable":
            self.shares[share] = False

    async def remediate(self, action, share=None):
        if action == "restart-service":
            self.smb = True
        elif action == "enable-share":
            self.shares[share] = True


def service(tmp_path):
    lab, directory, files = FakeLab(), FakeDirectory(), FakeFiles()
    return TicketService(lab, directory, files, tmp_path / "tickets.json"), lab, directory, files


def choose(scenario_id):
    return lambda candidates: next(item for item in candidates if item[0] == scenario_id)


def test_easy_ticket_applies_fault_verifies_recovery_and_persists(monkeypatch, tmp_path):
    tickets, lab, directory, files = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("workstation_offline"))

    ticket = asyncio.run(tickets.generate("easy"))
    assert ticket["ticket_id"] == "INC-1001"
    assert "scenario" not in ticket
    assert "offline" not in ticket["description"].lower()
    assert lab.devices["WS01"]["status"] == "offline"
    asyncio.run(tickets.start(ticket["ticket_id"], "Avery Admin"))
    with pytest.raises(LabServiceError) as raised:
        asyncio.run(tickets.resolve(ticket["ticket_id"], "Avery Admin", "Restored connectivity."))
    assert raised.value.code == "ticket_condition_active"

    asyncio.run(lab.workstation_action("WS01", "online"))
    resolved = asyncio.run(tickets.resolve(ticket["ticket_id"], "Avery Admin", "Restored connectivity."))
    assert resolved["status"] == "Resolved"
    assert resolved["resolved_at"]
    assert resolved["time_to_resolution_seconds"] >= 0
    assert resolved["resolution_notes"] == "Restored connectivity."
    reloaded = TicketService(lab, directory, files, tmp_path / "tickets.json")
    assert reloaded.list()[0]["status"] == "Resolved"


def test_medium_ticket_applies_real_membership_fault(monkeypatch, tmp_path):
    tickets, _, directory, _ = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("missing_group"))
    ticket = asyncio.run(tickets.generate("medium"))

    assert ticket["affected_user"] == "jordan.lee"
    assert "Finance" not in directory.user["groups"]
    connectivity = asyncio.run(tickets.file_connectivity(ticket["ticket_id"]))
    assert connectivity == {"source": "WS01", "destination": "FILE01", "success": True}
    assert not asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]
    asyncio.run(tickets.start(ticket["ticket_id"], "Avery Admin"))
    asyncio.run(directory.membership_action("jordan.lee", "Finance", "add"))
    assert asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]
    assert asyncio.run(tickets.resolve(ticket["ticket_id"], "Avery Admin", "Restored Finance membership."))["status"] == "Resolved"


def test_hard_ticket_requires_every_condition(monkeypatch, tmp_path):
    tickets, _, _, files = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("file_service_and_share"))
    ticket = asyncio.run(tickets.generate("hard"))
    assert not files.smb and not files.shares["Finance"]
    asyncio.run(tickets.start(ticket["ticket_id"], "Avery Admin"))

    asyncio.run(files.remediate("restart-service"))
    with pytest.raises(LabServiceError):
        asyncio.run(tickets.resolve(ticket["ticket_id"], "Avery Admin", "Restarted SMB."))
    asyncio.run(files.remediate("enable-share", "Finance"))
    assert asyncio.run(tickets.resolve(ticket["ticket_id"], "Avery Admin", "Restored SMB and Finance."))["status"] == "Resolved"


def test_printer_scenario_and_sequential_ids(monkeypatch, tmp_path):
    tickets, lab, _, _ = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("printer_offline"))
    first = asyncio.run(tickets.generate("easy"))
    assert lab.devices["PRNT01"]["status"] == "offline"
    asyncio.run(lab.printer_action("PRNT01", "ready"))
    asyncio.run(tickets.start(first["ticket_id"], "Avery Admin"))
    asyncio.run(tickets.resolve(first["ticket_id"], "Avery Admin", "Printer restored."))
    second = asyncio.run(tickets.generate("easy"))
    assert (first["ticket_id"], second["ticket_id"]) == ("INC-1001", "INC-1002")


def test_access_request_changes_nothing_until_completed(monkeypatch, tmp_path):
    tickets, _, directory, _ = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("grant_access"))
    ticket = asyncio.run(tickets.generate("easy"))

    assert ticket["ticket_type"] == "Service Request"
    requested_group = tickets.get(ticket["ticket_id"])["scenario"]["checks"][0]["group"]
    assert requested_group not in directory.user["groups"]
    assert not asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]
    asyncio.run(directory.membership_action("jordan.lee", requested_group, "add"))
    assert asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]


def test_endpoint_provision_request_verifies_live_inventory(monkeypatch, tmp_path):
    tickets, lab, _, _ = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("provision_endpoint"))
    ticket = asyncio.run(tickets.generate("medium"))

    assert ticket["ticket_type"] == "Service Request"
    assert not asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]
    lab.devices[ticket["affected_object"]] = {
        "hostname": ticket["affected_object"], "device_type": "workstation",
        "status": "online", "connected_switch": "SW01", "assigned_user": None,
    }
    expected_switch = tickets.get(ticket["ticket_id"])["scenario"]["checks"][0]["switch"]
    lab.devices[ticket["affected_object"]]["connected_switch"] = expected_switch
    assert asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]


def test_offboarding_request_requires_disabled_unassigned_former_employee(monkeypatch, tmp_path):
    tickets, _, directory, _ = service(tmp_path)
    monkeypatch.setattr("backend.app.services.tickets.random.choice", choose("offboard_employee"))
    ticket = asyncio.run(tickets.generate("hard"))

    assert not asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]
    directory.user.update({"enabled": False, "workstation": None, "groups": ["Former-Employees"]})
    assert asyncio.run(tickets.verify(ticket["ticket_id"]))["recovered"]
