import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from backend.app.errors import LabServiceError


class TicketService:
    def __init__(self, lab_service, ad_service, fileserver_service, state_path=None):
        state_dir = Path(os.getenv("NETOPS_STATE_DIR", Path.home() / "netops-lab-state"))
        self.state_path = Path(state_path or state_dir / "tickets.json")
        self.lab_service = lab_service
        self.ad_service = ad_service
        self.fileserver_service = fileserver_service
        self.state = self._load()

    def _load(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"next_number": 1001, "tickets": []}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n")
        temporary.replace(self.state_path)

    @staticmethod
    def _public(ticket):
        return {key: value for key, value in ticket.items() if key != "scenario"}

    def list(self, status=None):
        tickets = self.state["tickets"]
        if status:
            tickets = [ticket for ticket in tickets if ticket["status"].lower().replace(" ", "-") == status]
        return [self._public(ticket) for ticket in reversed(tickets)]

    def get(self, ticket_id):
        ticket = next((item for item in self.state["tickets"] if item["ticket_id"] == ticket_id.upper()), None)
        if not ticket:
            raise LabServiceError("unknown_ticket", "Unknown incident ticket.", 404)
        return ticket

    def _locked_resources(self):
        return {
            resource
            for ticket in self.state["tickets"]
            if ticket["status"] != "Resolved"
            for resource in ticket["scenario"]["resources"]
        }

    async def _candidates(self, difficulty):
        locked = self._locked_resources()
        devices = await self.lab_service.all_device_statuses()
        file_state = await self.fileserver_service.overview()
        users = await self.ad_service.users()
        candidates = []

        # Service requests describe a desired state and apply no initial fault.
        if difficulty == "easy":
            for user in users:
                for group in {"Finance", "Operations", "Engineering"}.difference(user["groups"]):
                    resource = f"membership:{user['username']}:{group}"
                    if user["enabled"] and user.get("workstation") and resource not in locked:
                        candidates.append(("grant_access", (user, group)))

        if difficulty == "medium":
            existing = {device["hostname"] for device in devices}
            for prefix, form_factor in (("WS", "workstation"), ("LTP", "laptop")):
                number = 1
                while f"{prefix}{number:02d}" in existing or f"device:{prefix}{number:02d}" in locked:
                    number += 1
                hostname = f"{prefix}{number:02d}"
                for floor, switch in (("Floor 1", "SW01"), ("Floor 2", "SW02"), ("Floor 3", "SW03")):
                    candidates.append(("provision_endpoint", {"hostname": hostname, "form_factor": form_factor, "floor": floor, "switch": switch}))

        if difficulty == "hard":
            existing_users = {user["username"] for user in users}
            onboarding_pool = [
                ("Taylor", "Morgan", "taylor.morgan", "Business Analyst"),
                ("Robin", "Hayes", "robin.hayes", "Operations Specialist"),
                ("Drew", "Carter", "drew.carter", "Project Coordinator"),
            ]
            unassigned = [
                device for device in devices
                if device["device_type"] in {"workstation", "laptop"}
                and not device.get("assigned_user")
            ]
            for device in unassigned:
                for first, last, username, role in onboarding_pool:
                    resources = {f"device:{device['hostname']}", f"user:{username}"}
                    if username not in existing_users and resources.isdisjoint(locked):
                        candidates.append(("onboard_employee", (device, first, last, username, role)))
            for user in users:
                resource = f"user:{user['username']}"
                if user.get("account_type") == "employee" and user["enabled"] and user.get("workstation") and resource not in locked:
                    candidates.append(("offboard_employee", user))

        if difficulty == "easy":
            for device in devices:
                resource = f"device:{device['hostname']}"
                if device["device_type"] == "workstation" and device["status"] == "online" and resource not in locked:
                    candidates.append(("workstation_offline", device))
                if device["device_type"] == "printer" and device["status"] == "ready" and resource not in locked:
                    candidates.append(("printer_offline", device))
            if file_state["status"] == "online" and file_state["smb_running"]:
                for share in file_state["shares"]:
                    resource = f"share:{share['name']}"
                    if share["enabled"] and resource not in locked:
                        candidates.append(("share_disabled", share))

        if difficulty == "medium":
            if file_state["status"] == "online" and file_state["smb_running"] and "service:FILE01:SMB" not in locked:
                candidates.append(("smb_stopped", file_state))
            for user in users:
                groups = {"Finance", "Operations", "Engineering"}.intersection(user["groups"])
                for group in groups:
                    resource = f"membership:{user['username']}:{group}"
                    if user["enabled"] and user.get("workstation") and resource not in locked:
                        candidates.append(("missing_group", (user, group)))

        if difficulty == "hard":
            if file_state["status"] == "online" and file_state["smb_running"] and "service:FILE01:SMB" not in locked:
                for share in file_state["shares"]:
                    resources = {"service:FILE01:SMB", f"share:{share['name']}"}
                    if share["enabled"] and resources.isdisjoint(locked):
                        candidates.append(("file_service_and_share", share))
            for device in devices:
                resource = f"device:{device['hostname']}"
                if (
                    device["device_type"] == "printer" and device["status"] == "ready"
                    and (device.get("live") or {}).get("toner", 0) > 0 and resource not in locked
                ):
                    candidates.append(("printer_offline_and_toner", device))
        return candidates

    async def generate(self, difficulty):
        candidates = await self._candidates(difficulty)
        if not candidates:
            raise LabServiceError(
                "no_compatible_scenario",
                "No compatible scenario is currently available. Recover existing faults or resolve open tickets first.",
                409,
            )
        scenario_id, target = random.choice(candidates)
        scenario = await self._apply_scenario(scenario_id, target)
        now = datetime.now(timezone.utc).isoformat()
        ticket = {
            "ticket_id": f"INC-{self.state['next_number']}",
            "summary": scenario["summary"],
            "description": scenario["description"],
            "ticket_type": scenario.get("ticket_type", "Incident"),
            "affected_user": scenario.get("affected_user"),
            "affected_object": scenario["affected_object"],
            "created_at": now,
            "status": "Open",
            "assigned_technician": "Unassigned",
            "resolution_notes": None,
            "resolved_at": None,
            "time_to_resolution_seconds": None,
            "scenario": {"scenario_id": scenario_id, "difficulty": difficulty, **scenario["hidden"]},
        }
        self.state["next_number"] += 1
        self.state["tickets"].append(ticket)
        self._save()
        self.lab_service.record_event(
            scenario.get("event_device", scenario["affected_object"]),
            f"{ticket['ticket_id']} generated: {ticket['summary']}", "warning",
        )
        return self._public(ticket)

    async def _apply_scenario(self, scenario_id, target):
        if scenario_id == "grant_access":
            user, group = target
            return {
                "ticket_type": "Service Request",
                "summary": f"Grant {user['display_name']} access to {group} resources",
                "description": f"Approved request: add {user['username']} to the {group} security group and verify access.",
                "affected_user": user["username"], "affected_object": group,
                "event_device": user["workstation"],
                "hidden": {"root_causes": ["Approved access request"], "checks": [{"type": "group_member", "username": user["username"], "group": group}], "resources": [f"membership:{user['username']}:{group}"]},
            }
        if scenario_id == "provision_endpoint":
            return {
                "ticket_type": "Service Request",
                "summary": f"Provision {target['hostname']} for {target['floor']}",
                "description": f"Add a {target['form_factor']} named {target['hostname']} on {target['floor']} ({target['switch']}) and verify it is online.",
                "affected_user": None, "affected_object": target["hostname"], "event_device": target["switch"],
                "hidden": {"root_causes": ["Approved endpoint provisioning request"], "checks": [{"type": "endpoint_exists", "hostname": target["hostname"], "switch": target["switch"]}], "resources": [f"device:{target['hostname']}"]},
            }
        if scenario_id == "onboard_employee":
            device, first, last, username, role = target
            group = {"SW01": "Finance", "SW02": "Operations", "SW03": "Engineering"}[device["connected_switch"]]
            return {
                "ticket_type": "Service Request",
                "summary": f"Onboard {first} {last} on {device['hostname']}",
                "description": f"Create {first} {last} ({username}) as a {role}, assign {device['hostname']}, and apply the {group} floor access group.",
                "affected_user": username, "affected_object": device["hostname"], "event_device": device["hostname"],
                "hidden": {"root_causes": ["Approved employee onboarding request"], "checks": [{"type": "employee_onboarded", "username": username, "hostname": device["hostname"], "group": group}], "resources": [f"user:{username}", f"device:{device['hostname']}"]},
            }
        if scenario_id == "offboard_employee":
            return {
                "ticket_type": "Service Request",
                "summary": f"Offboard {target['display_name']}",
                "description": f"Revoke {target['username']}'s access, release {target['workstation']}, place the account in Former-Employees, and disable it.",
                "affected_user": target["username"], "affected_object": target["workstation"], "event_device": target["workstation"],
                "hidden": {"root_causes": ["Approved employee offboarding request"], "checks": [{"type": "employee_offboarded", "username": target["username"]}], "resources": [f"user:{target['username']}", f"device:{target['workstation']}"]},
            }
        if scenario_id == "workstation_offline":
            await self.lab_service.workstation_action(target["hostname"], "offline")
            return {
                "summary": f"{target['hostname']} cannot connect to office resources",
                "description": "The employee reports that their computer suddenly lost access to network resources.",
                "affected_user": target.get("assigned_user"), "affected_object": target["hostname"],
                "event_device": target["hostname"],
                "hidden": {"root_causes": ["Workstation office interface offline"], "checks": [{"type": "device_online", "hostname": target["hostname"]}], "resources": [f"device:{target['hostname']}"]},
            }
        if scenario_id == "printer_offline":
            await self.lab_service.printer_action(target["hostname"], "offline")
            return {
                "summary": f"Employees cannot print to {target['hostname']}",
                "description": "Print attempts to the floor printer are not completing.",
                "affected_user": None, "affected_object": target["hostname"], "event_device": target["hostname"],
                "hidden": {"root_causes": ["Printer offline"], "checks": [{"type": "printer_ready", "hostname": target["hostname"]}], "resources": [f"device:{target['hostname']}"]},
            }
        if scenario_id == "share_disabled":
            await self.fileserver_service.fault("share-disable", target["name"])
            return {
                "summary": f"Employees cannot open the {target['name']} shared folder",
                "description": "Users report that the shared folder is unavailable even though other network resources respond.",
                "affected_user": None, "affected_object": f"FILE01 / {target['name']}", "event_device": "FILE01",
                "hidden": {"root_causes": ["File share disabled"], "checks": [{"type": "share_enabled", "share": target["name"]}], "resources": [f"share:{target['name']}"]},
            }
        if scenario_id == "smb_stopped":
            await self.fileserver_service.fault("service-stop")
            return {
                "summary": "Office shared folders are unavailable",
                "description": "Users can reach FILE01, but none of its shared folders will open.",
                "affected_user": None, "affected_object": "FILE01", "event_device": "FILE01",
                "hidden": {"root_causes": ["SMB service stopped"], "checks": [{"type": "smb_running"}], "resources": ["service:FILE01:SMB"]},
            }
        if scenario_id == "missing_group":
            user, group = target
            await self.ad_service.membership_action(user["username"], group, "remove")
            return {
                "summary": f"{user['display_name']} cannot access the {group} share",
                "description": f"The user can sign in and reach FILE01 from {user['workstation']}, but access to the department folder is denied.",
                "affected_user": user["username"], "affected_object": f"FILE01 / {group}", "event_device": user["workstation"],
                "hidden": {"root_causes": ["Required security-group membership missing"], "checks": [{"type": "group_member", "username": user["username"], "group": group}], "resources": [f"membership:{user['username']}:{group}"]},
            }
        if scenario_id == "file_service_and_share":
            await self.fileserver_service.fault("service-stop")
            try:
                await self.fileserver_service.fault("share-disable", target["name"])
            except Exception:
                await self.fileserver_service.remediate("restart-service")
                raise
            return {
                "summary": f"The {target['name']} shared folder remains unavailable",
                "description": "Multiple users report that file access is failing and the department folder cannot be opened.",
                "affected_user": None, "affected_object": f"FILE01 / {target['name']}", "event_device": "FILE01",
                "hidden": {"root_causes": ["SMB service stopped", "File share disabled"], "checks": [{"type": "smb_running"}, {"type": "share_enabled", "share": target["name"]}], "resources": ["service:FILE01:SMB", f"share:{target['name']}"]},
            }
        await self.lab_service.printer_action(target["hostname"], "empty-toner")
        await self.lab_service.printer_action(target["hostname"], "offline")
        return {
            "summary": f"Printing to {target['hostname']} fails after repeated attempts",
            "description": "The floor printer is unavailable and queued work cannot complete.",
            "affected_user": None, "affected_object": target["hostname"], "event_device": target["hostname"],
            "hidden": {"root_causes": ["Printer offline", "Toner empty"], "checks": [{"type": "printer_ready", "hostname": target["hostname"]}, {"type": "printer_toner", "hostname": target["hostname"]}], "resources": [f"device:{target['hostname']}"]},
        }

    async def start(self, ticket_id, technician):
        ticket = self.get(ticket_id)
        if not technician.strip():
            raise LabServiceError("technician_required", "Enter an assigned technician.", 422)
        if ticket["status"] == "Resolved":
            raise LabServiceError("ticket_already_resolved", "Resolved tickets cannot be restarted.", 409)
        ticket["status"] = "In Progress"
        ticket["assigned_technician"] = technician.strip()
        self._save()
        self.lab_service.record_event(ticket["affected_object"].split(" / ")[0], f"{ticket['ticket_id']} moved to In Progress.", "info")
        return self._public(ticket)

    async def _check(self, check):
        if check["type"] == "device_online":
            return (await self.lab_service.status_for_hostname(check["hostname"]))["status"] == "online"
        if check["type"] == "printer_ready":
            return (await self.lab_service.status_for_hostname(check["hostname"]))["status"] == "ready"
        if check["type"] == "printer_toner":
            status = await self.lab_service.status_for_hostname(check["hostname"])
            return (status.get("live") or {}).get("toner", 0) > 0
        if check["type"] == "smb_running":
            status = await self.fileserver_service.overview()
            return status["status"] == "online" and status["smb_running"]
        if check["type"] == "share_enabled":
            return (await self.fileserver_service.share(check["share"]))["enabled"]
        if check["type"] == "group_member":
            return check["group"] in (await self.ad_service.get_user(check["username"]))["groups"]
        if check["type"] == "endpoint_exists":
            try:
                status = await self.lab_service.status_for_hostname(check["hostname"])
            except LabServiceError:
                return False
            return status["status"] == "online" and status.get("connected_switch") == check["switch"]
        if check["type"] == "employee_onboarded":
            try:
                user = await self.ad_service.get_user(check["username"])
            except LabServiceError:
                return False
            return user["enabled"] and user.get("workstation") == check["hostname"] and {"Employees", check["group"]}.issubset(user["groups"])
        if check["type"] == "employee_offboarded":
            user = await self.ad_service.get_user(check["username"])
            return not user["enabled"] and not user.get("workstation") and "Former-Employees" in user["groups"]
        return False

    async def resolve(self, ticket_id, technician, notes):
        ticket = self.get(ticket_id)
        if ticket["status"] == "Resolved":
            return self._public(ticket)
        if ticket["status"] != "In Progress":
            raise LabServiceError("ticket_not_in_progress", "Start work before resolving this ticket.", 409)
        if not technician.strip() or not notes.strip():
            raise LabServiceError("resolution_details_required", "Technician and resolution notes are required.", 422)
        remaining = [check for check in ticket["scenario"]["checks"] if not await self._check(check)]
        if remaining:
            raise LabServiceError(
                "ticket_condition_active",
                "The underlying technical problem is still detected. Complete the recovery and verify again.",
                409, {"remaining_conditions": len(remaining)},
            )
        resolved_at = datetime.now(timezone.utc)
        created_at = datetime.fromisoformat(ticket["created_at"])
        ticket.update({
            "status": "Resolved", "assigned_technician": technician.strip(),
            "resolution_notes": notes.strip(), "resolved_at": resolved_at.isoformat(),
            "time_to_resolution_seconds": max(0, int((resolved_at - created_at).total_seconds())),
        })
        self._save()
        self.lab_service.record_event(ticket["affected_object"].split(" / ")[0], f"{ticket['ticket_id']} resolved.", "success")
        return self._public(ticket)

    async def verify(self, ticket_id):
        ticket = self.get(ticket_id)
        remaining = [
            check for check in ticket["scenario"]["checks"]
            if not await self._check(check)
        ]
        recovered = not remaining
        return {
            "ticket_id": ticket["ticket_id"],
            "recovered": recovered,
            "message": (
                "All expected recovery conditions are satisfied. The ticket can be resolved."
                if recovered else
                "The underlying technical problem is still detected. Continue troubleshooting."
            ),
            "remaining_conditions": len(remaining),
        }

    async def file_connectivity(self, ticket_id):
        ticket = self.get(ticket_id)
        if not ticket.get("affected_user") or not ticket["affected_object"].startswith("FILE01"):
            raise LabServiceError(
                "connectivity_check_not_applicable",
                "This ticket does not have a user-to-FILE01 connectivity path.",
                400,
            )
        user = await self.ad_service.get_user(ticket["affected_user"])
        if not user.get("workstation"):
            raise LabServiceError(
                "assigned_device_required",
                "The affected user does not have an assigned device.",
                409,
            )
        return await self.lab_service.ping(SimpleNamespace(
            source=user["workstation"], destination="FILE01"
        ))
