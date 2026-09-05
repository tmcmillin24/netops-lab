import asyncio
import json
import os
import secrets
import subprocess
from pathlib import Path

from backend.app.errors import LabServiceError
from containers.common.inventory import Inventory


ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = Path(os.getenv("NETOPS_STATE_DIR", Path.home() / "netops-lab-state"))
EXTENSIONS = STATE_DIR / "lab_extensions.json"
TOPOLOGY = ROOT / "lab/netops.clab.yml"
GENERATED_TOPOLOGY = STATE_DIR / "netops.generated.clab.yml"

FLOORS = {
    "access_01": {"floor": "Floor 1", "department": "Administration & Finance", "subnet": "10.10.10", "gateway": "10.10.10.1", "switch": "SW01", "printer": "PRNT01", "group": "Finance"},
    "access_02": {"floor": "Floor 2", "department": "Operations & Support", "subnet": "10.10.20", "gateway": "10.10.20.1", "switch": "SW02", "printer": "PRNT02", "group": "Operations"},
    "access_03": {"floor": "Floor 3", "department": "Engineering", "subnet": "10.10.30", "gateway": "10.10.30.1", "switch": "SW03", "printer": "PRNT03", "group": "Engineering"},
}


class ProvisioningService:
    FLOORS = FLOORS
    def __init__(self, lab_service, ad_service):
        self.lab_service = lab_service
        self.ad_service = ad_service
        self.drafts = {}
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if not EXTENSIONS.exists():
            source = ROOT / "configs/lab_extensions.json"
            EXTENSIONS.write_text(source.read_text())

    def extensions(self):
        try:
            return json.loads(EXTENSIONS.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise LabServiceError(
                "provisioning_state_unavailable",
                "The writable provisioning state could not be loaded.",
                503,
            ) from error

    def save_extensions(self, extensions):
        temporary = EXTENSIONS.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(extensions, indent=2) + "\n")
            temporary.replace(EXTENSIONS)
        except OSError as error:
            raise LabServiceError(
                "provisioning_state_unavailable",
                "The writable provisioning state could not be saved.",
                503,
            ) from error

    def next_hostname(self, device_type="workstation"):
        devices = [*self.lab_service.current_devices, *self.extensions().get("workstations", [])]
        prefix = "LTP" if device_type == "laptop" else "WS"
        numbers = [int(device["hostname"][len(prefix):]) for device in devices if device["hostname"].startswith(prefix) and device["hostname"][len(prefix):].isdigit()]
        return f"{prefix}{max(numbers, default=0) + 1:02d}"

    def draft(self, request):
        floor = FLOORS[request.floor]
        hostname = request.hostname or self.next_hostname(request.device_type)
        expected_prefix = "LTP" if request.device_type == "laptop" else "WS"
        if not hostname.startswith(expected_prefix):
            raise LabServiceError("hostname_type_mismatch", f"{request.device_type.title()} hostnames must start with {expected_prefix}.", 422)
        extended_devices = self.extensions().get("workstations", [])
        known_devices = [*self.lab_service.current_devices, *extended_devices]
        if any(device["hostname"] == hostname for device in known_devices):
            raise LabServiceError("hostname_in_use", f"{hostname} already exists.", 409)
        used = {device.get("ip_address") for device in known_devices}
        host_number = next((number for number in range(14, 201) if f"{floor['subnet']}.{number}" not in used), None)
        if host_number is None:
            raise LabServiceError("subnet_full", "No workstation address is available on that floor.", 409)
        draft_id = secrets.token_urlsafe(18)
        draft = {"draft_id": draft_id, "device_type": request.device_type, "hostname": hostname, "ip_address": f"{floor['subnet']}.{host_number}", "network": request.floor, **floor}
        self.drafts[draft_id] = draft
        return draft

    async def apply(self, draft_id):
        try:
            draft = self.drafts[draft_id]
        except KeyError as error:
            raise LabServiceError("unknown_draft", "The workstation draft expired or does not exist.", 404) from error
        extensions = self.extensions()
        workstation = {"id": draft["hostname"].lower(), "hostname": draft["hostname"], "type": "workstation", "form_factor": draft["device_type"], "ip_address": draft["ip_address"], "network": draft["network"], "connected_to": draft["switch"], "assigned_printer": draft["printer"], "domain_joined": False, "ad_computer_object": f"{draft['hostname']}$", "assigned_user": None, "dynamic": True, "service_port": 8081, "phase": "current"}
        extensions["workstations"] = [
            item for item in extensions.get("workstations", [])
            if item["hostname"] != workstation["hostname"]
        ]
        extensions["workstations"].append(workstation)
        self.save_extensions(extensions)
        self.render_topology(extensions["workstations"])
        await self.ad_service.ensure_computer(draft["hostname"])
        await asyncio.to_thread(self.deploy)
        self.lab_service.inventory = Inventory.load()
        self.ad_service.reload_baseline()
        self.drafts.pop(draft_id, None)
        self.ad_service.record_event(
            f"{draft['hostname']} provisioned on {draft['floor']}.", "info"
        )
        return {"message": f"{draft['hostname']} provisioned on {draft['floor']}.", "workstation": workstation}

    async def employee_options(self):
        live_users = await self.ad_service.users()
        occupied = {
            user["workstation"] for user in live_users
            if user.get("workstation")
        }
        workstations = [
            {"hostname": device["hostname"], "floor": FLOORS[device["network"]]["floor"], "department": FLOORS[device["network"]]["department"]}
            for device in self.lab_service.current_devices
            if device["type"] == "workstation" and device["hostname"] not in occupied
        ]
        return {"workstations": workstations}

    async def create_employee(self, request):
        if request.employee.username.lower() in self.ad_service.user_configs:
            raise LabServiceError("username_in_use", "That directory username already exists.", 409)
        floor = None
        if request.workstation:
            options = await self.employee_options()
            available = {item["hostname"]: item for item in options["workstations"]}
            if request.workstation not in available:
                raise LabServiceError("workstation_unavailable", "That workstation is already assigned.", 409)
            workstation = self.lab_service.get_device_config(request.workstation, "workstation")
            floor = FLOORS[workstation["network"]]
        user = {
            **request.employee.model_dump(),
            "display_name": f"{request.employee.given_name} {request.employee.surname}",
            "department": floor["department"] if floor else "Unassigned",
            "floor": floor["floor"] if floor else "Unassigned",
            "workstation": request.workstation,
            "groups": ["Employees", floor["group"]] if floor else ["Employees"],
        }
        result = await self.ad_service.create_user(user)
        try:
            extensions = self.extensions()
            extensions["users"] = [
                item for item in extensions.get("users", [])
                if item["username"].lower() != user["username"].lower()
            ]
            extensions["users"].append(user)
            overrides = extensions.setdefault("user_workstation_overrides", {})
            overrides[user["username"]] = request.workstation
            if request.workstation:
                extensions.setdefault("assignment_overrides", {})[request.workstation] = user["username"]
            self.save_extensions(extensions)
        except LabServiceError:
            try:
                await self.ad_service.delete_user(user["username"])
            except LabServiceError:
                pass
            raise
        self.lab_service.inventory = Inventory.load()
        self.ad_service.reload_baseline()
        self.ad_service.record_event(
            f"{user['username']} employee account created.", "info"
        )
        message = (
            f"{user['display_name']} created and assigned to {request.workstation}."
            if request.workstation else
            f"{user['display_name']} created in Employees and left unassigned."
        )
        return {"message": message, "user": user, **result}

    async def assign_employee(self, username, workstation):
        user = await self.ad_service.get_user(username)
        if not user["enabled"]:
            raise LabServiceError("employee_disabled", "Enable the employee account before assigning a device.", 409)
        if user.get("workstation"):
            raise LabServiceError("employee_already_assigned", f"Unassign {user['workstation']} first.", 409)
        options = await self.employee_options()
        available = {item["hostname"] for item in options["workstations"]}
        if workstation not in available:
            raise LabServiceError("workstation_unavailable", "That workstation is already assigned.", 409)
        device = self.lab_service.get_device_config(workstation, "workstation")
        floor = FLOORS[device["network"]]
        await self.ad_service.set_department_group(user["username"], floor["group"])
        extensions = self.extensions()
        extensions.setdefault("assignment_overrides", {})[workstation] = user["username"]
        extensions.setdefault("user_workstation_overrides", {})[user["username"]] = workstation
        extensions.setdefault("user_profile_overrides", {})[user["username"]] = {
            "department": floor["department"], "floor": floor["floor"]
        }
        self.save_extensions(extensions)
        self.lab_service.inventory = Inventory.load()
        self.ad_service.reload_baseline()
        self.ad_service.record_event(
            f"{user['username']} assigned to {workstation}.", "info"
        )
        return {"message": f"{user['display_name']} assigned to {workstation} on {floor['floor']}.", "username": user["username"], "workstation": workstation}

    async def unassign_employee(self, username):
        user = await self.ad_service.get_user(username)
        workstation = user.get("workstation")
        if not workstation:
            raise LabServiceError("employee_unassigned", "That employee is not assigned to a device.", 409)
        extensions = self.extensions()
        assignments = extensions.setdefault("assignment_overrides", {})
        assignments[workstation] = None
        extensions.setdefault("user_workstation_overrides", {})[user["username"]] = None
        extensions.setdefault("user_profile_overrides", {})[user["username"]] = {
            "department": "Unassigned", "floor": "Unassigned"
        }
        await self.ad_service.set_department_group(user["username"])
        self.save_extensions(extensions)
        self.lab_service.inventory = Inventory.load()
        self.ad_service.reload_baseline()
        self.ad_service.record_event(
            f"{user['username']} unassigned from {workstation}.", "warning"
        )
        return {"message": f"{user['display_name']} unassigned from {workstation}. Disable the account if the employee is leaving.", "username": user["username"], "workstation": workstation}

    async def remove_device(self, hostname):
        name = hostname.upper()
        extensions = self.extensions()
        dynamic_devices = {item["hostname"].upper(): item for item in extensions.get("workstations", [])}
        if name not in dynamic_devices:
            raise LabServiceError("protected_baseline_device", "Only devices added through Network provisioning can be removed.", 409)
        device = self.lab_service.get_device_config(name, "workstation")
        if device.get("assigned_user"):
            raise LabServiceError("device_assigned", f"Unassign {device['assigned_user']} from {name} before removing it.", 409)
        extensions["workstations"] = [item for item in extensions["workstations"] if item["hostname"].upper() != name]
        extensions.setdefault("assignment_overrides", {}).pop(name, None)
        self.save_extensions(extensions)
        self.render_topology(extensions["workstations"])
        await asyncio.to_thread(self.deploy)
        try:
            await self.ad_service.delete_computer(name)
        except LabServiceError:
            pass
        self.lab_service.inventory = Inventory.load()
        self.ad_service.reload_baseline()
        self.ad_service.record_event(f"{name} removed from the lab.", "warning")
        return {"message": f"{name} removed from the lab.", "hostname": name}

    def render_topology(self, workstations):
        text = TOPOLOGY.read_text()
        node_marker = "    # DYNAMIC_WORKSTATION_NODES"
        link_marker = "    # DYNAMIC_WORKSTATION_LINKS"
        nodes = []
        links = []
        counts = {"SW01": 7, "SW02": 7, "SW03": 7}
        for item in workstations:
            counts[item["connected_to"]] += 1
            floor = FLOORS[item["network"]]
            nodes.append(f'''    {item["id"]}:\n      kind: linux\n      image: netops-workstation:phase3\n      env:\n        DEVICE_NAME: {item["hostname"]}\n        DEVICE_DYNAMIC: "true"\n        DEVICE_IP: {item["ip_address"]}\n        DEVICE_GATEWAY: {floor["gateway"]}\n        DEVICE_SWITCH: {item["connected_to"]}\n        DEVICE_PRINTER: {item["assigned_printer"]}\n        DEVICE_PRINTER_IP: {floor["subnet"]}.21\n      exec:\n        - ip addr add {item["ip_address"]}/24 dev eth1\n        - ip route add 10.10.0.0/16 via {floor["gateway"]} dev eth1\n''')
            links.append(f'    - endpoints: ["{item["connected_to"].lower()}:eth{counts[item["connected_to"]]}", "{item["id"]}:eth1"]')
        before_nodes, rest = text.split(node_marker, 1)
        _, after_nodes = rest.split("\n\n    prnt01:", 1)
        text = before_nodes + node_marker + "\n" + "\n".join(nodes) + "\n    prnt01:" + after_nodes
        before_links, _ = text.split(link_marker, 1)
        GENERATED_TOPOLOGY.write_text(before_links + link_marker + "\n" + "\n".join(links) + "\n")

    def deploy(self):
        subprocess.run([str(ROOT / "scripts/build-images.sh")], cwd=ROOT, check=True, timeout=300)
        subprocess.run([str(ROOT / "scripts/lab.sh"), "destroy"], cwd=ROOT, check=True, timeout=120)
        subprocess.run([str(ROOT / "scripts/lab.sh"), "deploy"], cwd=ROOT, check=True, timeout=180)
