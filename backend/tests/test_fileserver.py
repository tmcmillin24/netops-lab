import asyncio
from types import SimpleNamespace

import pytest

from backend.app.errors import LabServiceError
from backend.app.services.fileserver import FileServerService


SHARES = [
    {"name": "Public", "read_groups": ["Employees"], "write_groups": ["Employees"], "enabled": True, "read_only": False},
    {"name": "HR", "read_groups": ["HR"], "write_groups": ["HR"], "enabled": True, "read_only": False},
    {"name": "Finance", "read_groups": ["Finance"], "write_groups": ["Finance"], "enabled": True, "read_only": False},
    {"name": "Engineering", "read_groups": ["Engineering"], "write_groups": ["Engineering"], "enabled": True, "read_only": False},
    {"name": "IT-Tools", "read_groups": ["Helpdesk", "IT-Admins"], "write_groups": ["IT-Admins"], "enabled": True, "read_only": False},
]


class Lab:
    def __init__(self):
        self.status = {"hostname": "FILE01", "status": "online", "smb_running": True, "shares": SHARES}
        self.events = []

    def get_device_config(self, hostname, expected_type=None):
        devices = {"FILE01": {"hostname": "FILE01", "type": "file_server"}, "WS01": {"hostname": "WS01", "type": "workstation"}}
        if hostname.upper() not in devices or expected_type and devices[hostname.upper()]["type"] != expected_type:
            raise LabServiceError("unknown_device", "Unknown device.", 404)
        return devices[hostname.upper()]

    async def request_endpoint(self, device, method="GET", path="/status", json=None):
        if method == "POST":
            action = path.removeprefix("/faults/")
            share_name = (json or {}).get("share")
            if action == "online":
                self.status = {**self.status, "status": "online", "last_event": "FILE01 office interface restored."}
            elif action == "service-start":
                self.status = {**self.status, "smb_running": True, "last_event": "SMB service started."}
            elif action in {"share-enable", "read-write"}:
                self.status = {
                    **self.status,
                    "shares": [
                        {
                            **share,
                            **({"enabled": True} if action == "share-enable" else {"read_only": False}),
                        } if share["name"] == share_name else share
                        for share in self.status["shares"]
                    ],
                    "last_event": f"{share_name} share {'enabled' if action == 'share-enable' else 'write access restored'}.",
                }
        return self.status

    def record_event(self, *arguments):
        self.events.append(arguments)


class Directory:
    def __init__(self):
        self.memberships = {
            "Employees": ["jordan.lee"],
            "Finance": ["jordan.lee"],
            "HR": [],
            "Engineering": [],
            "Helpdesk": [],
            "IT-Admins": [],
        }

    def known_user(self, username):
        if username != "jordan.lee":
            raise LabServiceError("unknown_directory_user", "Unknown managed directory user.", 404)
        return {"username": username}

    def known_group(self, group):
        if group not in self.memberships:
            raise LabServiceError("unknown_directory_group", "Unknown managed directory group.", 404)
        return {"name": group}

    async def get_user(self, username):
        if username != "jordan.lee":
            raise LabServiceError("unknown_directory_user", "Unknown managed directory user.", 404)
        groups = [group for group, members in self.memberships.items() if username in members]
        return {"username": username, "display_name": "Jordan Lee", "role": "Finance Analyst", "workstation": "WS01", "enabled": True, "account_type": "employee", "groups": groups}

    async def users(self):
        return [await self.get_user("jordan.lee")]

    async def groups(self):
        return [{"name": name, "members": members} for name, members in self.memberships.items()]

    async def membership_action(self, username, group, action):
        self.known_user(username)
        self.known_group(group)
        if action == "add" and username not in self.memberships[group]:
            self.memberships[group].append(username)
        if action == "remove" and username in self.memberships[group]:
            self.memberships[group].remove(username)
        return await self.get_user(username)


def test_group_based_share_access_and_denial():
    service = FileServerService(Lab(), Directory())
    allowed = asyncio.run(service.access_check(SimpleNamespace(username="jordan.lee", device="WS01", share="Finance", operation="write")))
    denied = asyncio.run(service.access_check(SimpleNamespace(username="jordan.lee", device="WS01", share="HR", operation="read")))
    public = asyncio.run(service.access_check(SimpleNamespace(username="jordan.lee", device="WS01", share="Public", operation="read")))
    assert allowed["allowed"] is True
    assert public["allowed"] is True
    assert denied["allowed"] is False


def test_file_service_failure_states_deny_access():
    lab = Lab()
    service = FileServerService(lab, Directory())
    request = SimpleNamespace(username="jordan.lee", device="WS01", share="Finance", operation="write")
    lab.status = {**lab.status, "status": "offline"}
    assert asyncio.run(service.access_check(request))["reason"] == "FILE01 is offline."
    lab.status = {**lab.status, "status": "online", "smb_running": False}
    assert asyncio.run(service.access_check(request))["reason"] == "The SMB service is stopped."
    lab.status = {**lab.status, "smb_running": True, "shares": [{**share, "enabled": share["name"] != "Finance"} for share in SHARES]}
    assert "disabled" in asyncio.run(service.access_check(request))["reason"]
    lab.status = {**lab.status, "shares": [{**share, "read_only": share["name"] == "Finance"} for share in SHARES]}
    assert "read-only" in asyncio.run(service.access_check(request))["reason"]


def test_unknown_user_share_path_and_device_are_rejected():
    service = FileServerService(Lab(), Directory())
    with pytest.raises(LabServiceError):
        asyncio.run(service.access_check(SimpleNamespace(username="unknown", device="WS01", share="Finance", operation="read")))
    with pytest.raises(LabServiceError):
        asyncio.run(service.share("../../etc"))
    with pytest.raises(LabServiceError):
        asyncio.run(service.access_check(SimpleNamespace(username="jordan.lee", device="FILE01", share="Finance", operation="read")))


def test_effective_access_and_membership_changes_stay_group_driven():
    directory = Directory()
    service = FileServerService(Lab(), directory)
    before = asyncio.run(service.effective_access("HR"))
    assert before["effective_users"] == []
    request = SimpleNamespace(username="jordan.lee", group="HR", action="add")
    after_add = asyncio.run(service.membership_action("HR", request))
    assert after_add["effective_users"][0]["username"] == "jordan.lee"
    assert asyncio.run(service.access_check(SimpleNamespace(username="jordan.lee", device="WS01", share="HR", operation="read")))["allowed"] is True
    request.action = "remove"
    after_remove = asyncio.run(service.membership_action("HR", request))
    assert after_remove["effective_users"] == []
    assert asyncio.run(service.access_check(SimpleNamespace(username="jordan.lee", device="WS01", share="HR", operation="read")))["allowed"] is False
    assert not hasattr(service, "share_users")


def test_user_access_aggregates_effective_shares_and_granting_groups():
    directory = Directory()
    service = FileServerService(Lab(), directory)
    before = asyncio.run(service.user_access("jordan.lee"))
    shares = {share["name"]: share for share in before["shares"]}
    assert shares["Public"]["access_level"] == "Read/Write"
    assert shares["Public"]["granting_groups"] == ["Employees"]
    assert shares["Finance"]["granted"] is True
    assert shares["HR"]["granted"] is False

    asyncio.run(service.membership_action(
        "HR", SimpleNamespace(username="jordan.lee", group="HR", action="add")
    ))
    after = asyncio.run(service.user_access("jordan.lee"))
    hr = next(share for share in after["shares"] if share["name"] == "HR")
    assert hr["granted"] is True
    assert hr["granting_groups"] == ["HR"]
    assert not hasattr(service, "share_users")


def test_user_access_uses_highest_level_when_multiple_groups_grant_a_share():
    directory = Directory()
    directory.memberships["Helpdesk"].append("jordan.lee")
    directory.memberships["IT-Admins"].append("jordan.lee")
    service = FileServerService(Lab(), directory)
    access = asyncio.run(service.user_access("jordan.lee"))
    tools = next(share for share in access["shares"] if share["name"] == "IT-Tools")
    assert tools["access_level"] == "Read/Write"
    assert tools["granting_groups"] == ["Helpdesk", "IT-Admins"]


def test_non_share_group_is_rejected():
    service = FileServerService(Lab(), Directory())
    with pytest.raises(LabServiceError) as error:
        asyncio.run(service.membership_action("Finance", SimpleNamespace(username="jordan.lee", group="HR", action="add")))
    assert error.value.code == "group_not_authorized_for_share"


def test_fileserver_and_smb_recovery_are_structured_and_idempotent():
    lab = Lab()
    lab.status = {**lab.status, "status": "offline", "smb_running": False}
    service = FileServerService(lab, Directory())

    online = asyncio.run(service.remediate("online"))
    restarted = asyncio.run(service.remediate("restart-service"))
    unchanged = asyncio.run(service.remediate("restart-service"))

    assert online["previous_state"] == "offline"
    assert online["new_state"] == "online"
    assert restarted["changed"] is True
    assert unchanged["changed"] is False
    assert lab.events[-1][2] == "success"


def test_share_enable_and_write_recovery_preserve_other_shares():
    lab = Lab()
    lab.status = {
        **lab.status,
        "shares": [
            {**share, "enabled": share["name"] != "Finance", "read_only": share["name"] == "Engineering"}
            for share in SHARES
        ],
    }
    service = FileServerService(lab, Directory())

    enabled = asyncio.run(service.remediate("enable-share", "Finance"))
    write = asyncio.run(service.remediate("restore-write", "Engineering"))

    shares = {share["name"]: share for share in lab.status["shares"]}
    assert enabled["target"] == "Finance"
    assert write["target"] == "Engineering"
    assert shares["Finance"]["enabled"] is True
    assert shares["Engineering"]["read_only"] is False
    assert shares["HR"]["enabled"] is True


def test_remediation_rejects_unknown_actions_and_shares():
    service = FileServerService(Lab(), Directory())
    with pytest.raises(LabServiceError):
        asyncio.run(service.remediate("run-command"))
    with pytest.raises(LabServiceError):
        asyncio.run(service.remediate("enable-share", "Unknown"))
