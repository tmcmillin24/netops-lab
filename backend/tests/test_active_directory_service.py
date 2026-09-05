import asyncio

from backend.app.services.active_directory import ActiveDirectoryService


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
