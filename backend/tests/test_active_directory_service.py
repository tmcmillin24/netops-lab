import asyncio
import json

from backend.app.services.active_directory import ActiveDirectoryService
from backend.app.errors import LabServiceError


def test_account_health_counts_live_states_without_double_counting_users():
    service = object.__new__(ActiveDirectoryService)
    service.user_configs = {name: {} for name in ("healthy", "locked", "expired", "disabled", "two_issues")}
    states = {
        "healthy": {"username": "healthy", "display_name": "Healthy User", "enabled": True, "locked": False, "password_expired": False},
        "locked": {"username": "locked", "display_name": "Locked User", "enabled": True, "locked": True, "password_expired": False},
        "expired": {"username": "expired", "display_name": "Expired User", "enabled": True, "locked": False, "password_expired": True},
        "disabled": {"username": "disabled", "display_name": "Disabled User", "enabled": False, "locked": False, "password_expired": False},
        "two_issues": {"username": "two_issues", "display_name": "Two Issues", "enabled": True, "locked": True, "password_expired": True},
    }

    async def get_user(username):
        return states[username]

    service.get_user = get_user
    result = asyncio.run(service.account_health())

    assert result["status"] == "attention"
    assert result["total_accounts"] == 5
    assert result["affected_accounts"] == 4
    assert result["locked_accounts"] == 2
    assert result["password_expired_accounts"] == 2
    assert result["disabled_accounts"] == 1
    assert len(result["affected_users"]) == 4
    assert next(user for user in result["affected_users"] if user["username"] == "two_issues")["issues"] == ["Locked", "Password expired"]
    assert result["status_source"] == "live_active_directory"


def test_disabled_unassigned_account_can_be_deleted_and_stays_removed(tmp_path, monkeypatch):
    extension_file = tmp_path / "lab_extensions.json"
    extension_file.write_text(json.dumps({"users": [], "deleted_users": []}))
    monkeypatch.setenv("LAB_EXTENSIONS_PATH", str(extension_file))
    service = ActiveDirectoryService(runtime=None)
    deleted = []

    async def get_user(username):
        return {"username": username, "enabled": False, "workstation": None}

    async def delete_user(username):
        deleted.append(username)

    service.get_user = get_user
    service.delete_user = delete_user
    result = asyncio.run(service.delete_disabled_user("taylor.brooks"))

    assert result == {"username": "taylor.brooks", "deleted": True}
    assert deleted == ["taylor.brooks"]
    assert "taylor.brooks" in json.loads(extension_file.read_text())["deleted_users"]
    try:
        service.known_user("taylor.brooks")
    except LabServiceError as error:
        assert error.code == "unknown_directory_user"
    else:
        raise AssertionError("Deleted baseline user was reloaded")
