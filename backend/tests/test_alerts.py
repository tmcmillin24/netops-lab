from backend.app.services.alerts import AlertTracker


def workstation(status="online"):
    return {
        "hostname": "WS01", "device_type": "workstation", "status": status,
        "dependency_status": "normal", "live": {"message": f"WS01 is {status}."},
    }


def file_server(status="online", smb=True, finance=True):
    return {
        "hostname": "FILE01", "device_type": "file_server", "status": status,
        "service_health": "available" if smb and finance else "attention",
        "dependency_status": "normal",
        "live": {
            "message": f"FILE01 is {status}.", "smb_running": smb,
            "shares": [
                {"name": "Finance", "enabled": finance, "read_only": False},
                {"name": "Public", "enabled": True, "read_only": False},
            ],
        },
    }


def account_health(issues=None):
    issues = issues or []
    return {
        "status": "attention" if issues else "healthy",
        "affected_users": [
            {"username": "alex.kim", "display_name": "Alex Kim", "issues": issues}
        ] if issues else [],
    }


def test_alert_lifecycle_prevents_duplicates_and_preserves_resolution():
    tracker = AlertTracker()
    first = tracker.reconcile([workstation("offline")], account_health())
    second = tracker.reconcile([workstation("offline")], account_health())

    assert first["summary"]["active"] == 1
    assert second["summary"]["active"] == 1
    assert len(second["alerts"]) == 1
    alert_id = second["active_alerts"][0]["alert_id"]

    recovered = tracker.reconcile([workstation()], account_health())
    assert recovered["summary"]["active"] == 0
    assert recovered["resolved_alerts"][0]["alert_id"] == alert_id
    assert recovered["resolved_alerts"][0]["resolved_at"]

    recurred = tracker.reconcile([workstation("offline")], account_health())
    assert recurred["summary"]["active"] == 1
    assert recurred["active_alerts"][0]["alert_id"] != alert_id


def test_file_service_share_and_account_conditions_resolve_independently():
    tracker = AlertTracker()
    unhealthy = tracker.reconcile(
        [file_server(smb=False, finance=False)],
        account_health(["Locked", "Password expired"]),
    )

    assert unhealthy["summary"] == {
        "active": 4, "critical": 0, "warning": 4, "notice": 0,
        "account_attention": 1,
    }
    keys = {alert["condition_key"] for alert in unhealthy["active_alerts"]}
    assert keys == {
        "service:FILE01:smb", "share:FILE01:Finance:disabled",
        "account:alex.kim:locked", "account:alex.kim:password-expired",
    }

    healthy = tracker.reconcile([file_server()], account_health())
    assert healthy["summary"]["active"] == 0
    assert len(healthy["resolved_alerts"]) == 4


def test_server_offline_is_critical_without_cascaded_service_alerts():
    result = AlertTracker().reconcile([file_server(status="offline", smb=False, finance=False)])

    assert result["summary"]["critical"] == 1
    assert result["summary"]["warning"] == 0
    assert result["active_alerts"][0]["condition_key"] == "device:FILE01:availability"


def test_printer_attention_resolves_after_resource_recovery():
    tracker = AlertTracker()
    printer = {
        "hostname": "PRNT03", "device_type": "printer", "status": "attention",
        "dependency_status": "normal", "live": {"message": "PRNT03 is out of toner."},
    }
    active = tracker.reconcile([printer])
    assert active["summary"]["warning"] == 1
    assert active["active_alerts"][0]["source"] == "PRNT03"

    printer["status"] = "ready"
    printer["live"]["message"] = "PRNT03 toner refilled."
    resolved = tracker.reconcile([printer])
    assert resolved["summary"]["active"] == 0
    assert len(resolved["resolved_alerts"]) == 1
