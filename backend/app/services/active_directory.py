import asyncio
import json
import os
import secrets
import string
from pathlib import Path

from backend.app.errors import LabServiceError


BASELINE_PATH = Path(__file__).resolve().parents[3] / "configs/ad_baseline.json"
LOCAL_EXTENSIONS_PATH = Path(__file__).resolve().parents[3] / "configs/lab_extensions.json"
STATE_EXTENSIONS_PATH = Path.home() / "netops-lab-state/lab_extensions.json"


def extensions_path():
    configured = os.getenv("LAB_EXTENSIONS_PATH")
    if configured:
        return Path(configured)
    return STATE_EXTENSIONS_PATH if STATE_EXTENSIONS_PATH.exists() else LOCAL_EXTENSIONS_PATH


def parse_attributes(output):
    attributes = {}
    for line in output.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        attributes.setdefault(key, []).append(value)
    return attributes


class ActiveDirectoryService:
    def __init__(self, runtime, baseline_path=BASELINE_PATH, event_recorder=None):
        self.runtime = runtime
        self.baseline_path = Path(baseline_path)
        self.event_recorder = event_recorder
        self.last_health_status = None
        self.reload_baseline()

    def record_event(self, message, event_type="info"):
        if self.event_recorder:
            self.event_recorder("DC01", message, event_type)

    def reload_baseline(self):
        self.baseline = json.loads(self.baseline_path.read_text())
        extension_file = extensions_path()
        if extension_file.exists():
            extensions = json.loads(extension_file.read_text())
            self.baseline["users"].extend(extensions.get("users", []))
            deleted_users = {name.lower() for name in extensions.get("deleted_users", [])}
            self.baseline["users"] = [
                user for user in self.baseline["users"]
                if user["username"].lower() not in deleted_users
            ]
            workstation_overrides = extensions.get("user_workstation_overrides", {})
            profile_overrides = extensions.get("user_profile_overrides", {})
            for user in self.baseline["users"]:
                if user["username"] in workstation_overrides:
                    user["workstation"] = workstation_overrides[user["username"]]
                for field, value in profile_overrides.get(user["username"], {}).items():
                    if field in {"department", "floor"}:
                        user[field] = value
        self.user_configs = {
            user["username"].lower(): user for user in self.baseline["users"]
        }
        self.group_configs = {
            group["name"].lower(): group for group in self.baseline["groups"]
        }

    async def create_user(self, config):
        self.known_group(config["groups"][-1])
        if config["username"].lower() in self.user_configs:
            raise LabServiceError("username_in_use", "That directory username already exists.", 409)
        alphabet = string.ascii_letters + string.digits + "!@#%"
        password = "N0!" + "".join(secrets.choice(alphabet) for _ in range(17))
        created = False
        try:
            await self.command(
                "samba-tool", "user", "create", config["username"], password,
                "--userou=OU=Users,OU=NetOpsLab",
                f"--given-name={config['given_name']}", f"--surname={config['surname']}",
            )
            created = True
            for group in config["groups"]:
                await self.command("samba-tool", "group", "addmembers", group, config["username"])
        except LabServiceError:
            if created:
                try:
                    await self.command("samba-tool", "user", "delete", config["username"])
                except LabServiceError:
                    pass
            raise
        return {"temporary_password": password}

    async def ensure_computer(self, hostname):
        try:
            await self.command("samba-tool", "computer", "show", hostname)
        except LabServiceError:
            computer_ou = "Laptops" if hostname.upper().startswith("LTP") else "Workstations"
            await self.command("samba-tool", "computer", "create", hostname, f"--computerou=OU={computer_ou},OU=NetOpsLab")

    async def delete_user(self, username):
        await self.command("samba-tool", "user", "delete", username)

    async def delete_disabled_user(self, username):
        config = self.known_user(username)
        user = await self.get_user(config["username"])
        if user["enabled"]:
            raise LabServiceError(
                "account_must_be_disabled",
                "Disable the account before deleting it.", 409,
            )
        if user.get("workstation"):
            raise LabServiceError(
                "account_device_assigned",
                "Unassign the account from its device before deleting it.", 409,
            )
        await self.delete_user(config["username"])
        extension_file = extensions_path()
        extensions = json.loads(extension_file.read_text()) if extension_file.exists() else {}
        extensions["users"] = [
            item for item in extensions.get("users", [])
            if item["username"].lower() != config["username"].lower()
        ]
        for key in ("user_workstation_overrides", "user_profile_overrides"):
            extensions.setdefault(key, {}).pop(config["username"], None)
        deleted = set(extensions.get("deleted_users", []))
        deleted.add(config["username"])
        extensions["deleted_users"] = sorted(deleted)
        extension_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = extension_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(extensions, indent=2) + "\n")
        temporary.replace(extension_file)
        self.reload_baseline()
        self.record_event(f"{config['username']} account permanently deleted.", "warning")
        return {"username": config["username"], "deleted": True}

    async def delete_computer(self, hostname):
        await self.command("samba-tool", "computer", "delete", hostname)

    def known_user(self, username):
        try:
            return self.user_configs[username.lower()]
        except (KeyError, AttributeError) as error:
            raise LabServiceError("unknown_directory_user", "Unknown managed directory user.", 404) from error

    def known_group(self, group_name):
        try:
            return self.group_configs[group_name.lower()]
        except (KeyError, AttributeError) as error:
            raise LabServiceError("unknown_directory_group", "Unknown managed directory group.", 404) from error

    async def command(self, *arguments, timeout=8):
        return await asyncio.to_thread(self.runtime.dc_command, list(arguments), timeout)

    async def health(self):
        try:
            await self.command("samba-tool", "domain", "level", "show")
            await self.command("host", "-t", "SRV", "_ldap._tcp.netopslab.test", "127.0.0.1")
            status = "healthy"
            dns_status = "healthy"
        except LabServiceError:
            status = "unavailable"
            dns_status = "unavailable"
        if self.last_health_status and status != self.last_health_status:
            self.record_event(
                "DC01 directory service recovered." if status == "healthy" else "DC01 directory service became unavailable.",
                "recovery" if status == "healthy" else "error",
            )
        self.last_health_status = status
        return {
            "domain": self.baseline["domain"]["dns_name"],
            "netbios_domain": self.baseline["domain"]["netbios_name"],
            "domain_controller": self.baseline["domain"]["domain_controller"],
            "dns_address": self.baseline["domain"]["dns_address"],
            "status": status,
            "dns_status": dns_status,
            "platform": "Samba Active Directory Domain Controller",
            "user_count": len(self.user_configs),
            "group_count": len(self.group_configs),
        }

    async def get_user(self, username):
        config = self.known_user(username)
        output = await self.command("samba-tool", "user", "show", config["username"])
        attributes = parse_attributes(output)
        control = int(attributes.get("userAccountControl", ["0"])[0])
        lockout = int(attributes.get("lockoutTime", ["0"])[0])
        memberships = [
            value.split(",", 1)[0].removeprefix("CN=")
            for value in attributes.get("memberOf", [])
            if value.startswith("CN=")
        ]
        return {
            "username": config["username"],
            "display_name": config["display_name"],
            "role": config["role"],
            "department": config["department"],
            "floor": config["floor"],
            "workstation": config["workstation"],
            "enabled": not bool(control & 2),
            "locked": lockout != 0,
            "bad_password_count": int(attributes.get("badPwdCount", ["0"])[0]),
            "groups": sorted(
                group for group in memberships if group.lower() in self.group_configs
            ),
            "password_expired": attributes.get("pwdLastSet", ["1"])[0] == "0",
            "account_type": config.get("account_type", "employee"),
            "privileged": bool(config.get("privileged")),
            "remote": bool(config.get("remote")),
        }

    async def users(self):
        return [await self.get_user(username) for username in self.user_configs]

    async def groups(self):
        groups = []
        for config in self.group_configs.values():
            output = await self.command("samba-tool", "group", "listmembers", config["name"])
            members = sorted(line.strip() for line in output.splitlines() if line.strip())
            groups.append({**config, "members": members})
        return groups

    async def password_policy(self):
        output = await self.command("samba-tool", "domain", "passwordsettings", "show")
        values = {}
        for line in output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip()] = value.strip()
        return {
            "complexity": values.get("Password complexity") == "on",
            "history_length": int(values.get("Password history length", 0)),
            "minimum_length": int(values.get("Minimum password length", 0)),
            "minimum_age_days": int(values.get("Minimum password age (days)", 0)),
            "maximum_age_days": int(values.get("Maximum password age (days)", 0)),
            "lockout_threshold": int(values.get("Account lockout threshold (attempts)", 0)),
            "lockout_duration_minutes": int(values.get("Account lockout duration (mins)", 0)),
            "lockout_reset_minutes": int(values.get("Reset account lockout after (mins)", 0)),
        }

    async def overview(self):
        health, users, groups, password_policy = await asyncio.gather(
            self.health(), self.users(), self.groups(), self.password_policy()
        )
        return {**health, "users": users, "groups": groups, "password_policy": password_policy}

    async def account_health(self):
        users = await asyncio.gather(*(
            self.get_user(username) for username in self.user_configs
        ))
        locked = sum(user["enabled"] and user["locked"] for user in users)
        password_expired = sum(
            user["enabled"] and user["password_expired"] for user in users
        )
        disabled = sum(not user["enabled"] for user in users)
        affected = sum(
            not user["enabled"] or user["locked"] or user["password_expired"]
            for user in users
        )
        affected_users = []
        for user in users:
            issues = []
            if not user["enabled"]:
                issues.append("Disabled")
            if user["locked"]:
                issues.append("Locked")
            if user["password_expired"]:
                issues.append("Password expired")
            if issues:
                affected_users.append({
                    "username": user["username"],
                    "display_name": user["display_name"],
                    "issues": issues,
                })
        return {
            "status": "attention" if affected else "healthy",
            "total_accounts": len(users),
            "affected_accounts": affected,
            "locked_accounts": locked,
            "password_expired_accounts": password_expired,
            "disabled_accounts": disabled,
            "affected_users": affected_users,
            "status_source": "live_active_directory",
        }

    async def user_action(self, username, action):
        config = self.known_user(username)
        commands = {
            "enable": ("samba-tool", "user", "enable", config["username"]),
            "disable": ("samba-tool", "user", "disable", config["username"]),
            "unlock": ("samba-tool", "user", "unlock", config["username"]),
        }
        if action not in commands:
            raise LabServiceError("unknown_action", "Unsupported directory user action.", 404)
        await self.command(*commands[action])
        action_label = {"enable": "enabled", "disable": "disabled", "unlock": "unlocked"}[action]
        self.record_event(
            f"{config['username']} account {action_label}.",
            "warning" if action == "disable" else "recovery",
        )
        return await self.get_user(config["username"])

    async def reset_password(self, username):
        config = self.known_user(username)
        alphabet = string.ascii_letters + string.digits + "!@#%"
        password = "N0!" + "".join(secrets.choice(alphabet) for _ in range(17))
        await self.command(
            "samba-tool", "user", "setpassword", config["username"],
            f"--newpassword={password}",
        )
        self.record_event(f"Password reset for {config['username']}.", "info")
        return {
            "username": config["username"],
            "temporary_password": password,
            "message": "Temporary lab password generated. It will not be shown again.",
        }

    async def membership_action(self, username, group_name, action):
        user = self.known_user(username)
        group = self.known_group(group_name)
        operation = {"add": "addmembers", "remove": "removemembers"}.get(action)
        if not operation:
            raise LabServiceError("unknown_action", "Unsupported membership action.", 404)
        await self.command(
            "samba-tool", "group", operation, group["name"], user["username"]
        )
        action_label = "added to" if action == "add" else "removed from"
        self.record_event(f"{user['username']} {action_label} {group['name']}.", "info")
        if action == "add" and group["name"] == "Former-Employees":
            await self.command("samba-tool", "user", "disable", user["username"])
            current = await self.get_user(user["username"])
            for managed_group in current["groups"]:
                if managed_group != "Former-Employees":
                    await self.command(
                        "samba-tool", "group", "removemembers",
                        managed_group, user["username"],
                    )
        return await self.get_user(user["username"])

    async def set_department_group(self, username, group_name=None):
        user = await self.get_user(username)
        department_groups = {"Finance", "Operations", "Engineering"}
        for current_group in department_groups.intersection(user["groups"]):
            if current_group != group_name:
                await self.command("samba-tool", "group", "removemembers", current_group, user["username"])
        if group_name and group_name not in user["groups"]:
            self.known_group(group_name)
            await self.command("samba-tool", "group", "addmembers", group_name, user["username"])
