from datetime import datetime, timezone


class AlertTracker:
    """Reconcile live health conditions into a small in-memory alert history."""

    def __init__(self, history_limit=100):
        self.history_limit = history_limit
        self.alerts = []
        self.active_by_condition = {}
        self.next_id = 1

    @staticmethod
    def _condition(key, source, source_type, severity, summary, related=None):
        return {
            "condition_key": key,
            "source": source,
            "source_type": source_type,
            "severity": severity,
            "summary": summary,
            "related": related or {},
        }

    def conditions_from_state(self, devices, account_health=None):
        conditions = []
        for device in devices:
            hostname = device["hostname"]
            device_type = device["device_type"]
            status = device.get("status")
            dependency = device.get("dependency_status")
            live = device.get("live") or {}
            if status in {"offline", "unavailable"}:
                critical_types = {
                    "router_firewall", "layer3_core_switch",
                    "domain_controller", "file_server",
                }
                conditions.append(self._condition(
                    f"device:{hostname}:availability", hostname, device_type,
                    "critical" if device_type in critical_types else "warning",
                    live.get("message") or device.get("service_error") or f"{hostname} is {status}.",
                    {"device": hostname},
                ))
            elif dependency == "impacted":
                conditions.append(self._condition(
                    f"device:{hostname}:dependency", hostname, device_type,
                    "warning", device.get("impact_reason") or f"{hostname} has an upstream connectivity impact.",
                    {"device": hostname, "impacted_by": device.get("impacted_by", [])},
                ))

            if device_type == "printer" and status == "attention":
                conditions.append(self._condition(
                    f"printer:{hostname}:attention", hostname, "printer", "warning",
                    live.get("message") or f"{hostname} requires resource attention.",
                    {"device": hostname},
                ))

            if device_type == "file_server" and status == "online":
                if not live.get("smb_running", True):
                    conditions.append(self._condition(
                        "service:FILE01:smb", "FILE01", "service", "warning",
                        "FILE01 file service is unavailable.", {"device": "FILE01", "service": "SMB"},
                    ))
                for share in live.get("shares", []):
                    name = share.get("name")
                    if not share.get("enabled", True):
                        conditions.append(self._condition(
                            f"share:FILE01:{name}:disabled", "FILE01", "share", "warning",
                            f"FILE01 {name} share is disabled.", {"device": "FILE01", "share": name},
                        ))
                    elif share.get("read_only"):
                        conditions.append(self._condition(
                            f"share:FILE01:{name}:read-only", "FILE01", "share", "notice",
                            f"FILE01 {name} share is read-only.", {"device": "FILE01", "share": name},
                        ))

        if account_health:
            if account_health.get("status") == "unavailable":
                conditions.append(self._condition(
                    "service:DC01:account-health", "DC01", "service", "critical",
                    "Active Directory account health is unavailable.", {"device": "DC01"},
                ))
            for user in account_health.get("affected_users", []):
                for issue in user.get("issues", []):
                    issue_key = issue.lower().replace(" ", "-")
                    conditions.append(self._condition(
                        f"account:{user['username']}:{issue_key}", user["username"], "directory_account",
                        "warning", f"{user['display_name']}: {issue}.",
                        {"username": user["username"], "issue": issue},
                    ))
        return conditions

    def reconcile(self, devices, account_health=None):
        now = datetime.now(timezone.utc).isoformat()
        conditions = {
            item["condition_key"]: item
            for item in self.conditions_from_state(devices, account_health)
        }
        for key, alert in list(self.active_by_condition.items()):
            if key not in conditions:
                alert["status"] = "resolved"
                alert["resolved_at"] = now
                del self.active_by_condition[key]

        for key, condition in conditions.items():
            existing = self.active_by_condition.get(key)
            if existing:
                existing.update({
                    "severity": condition["severity"],
                    "summary": condition["summary"],
                    "related": condition["related"],
                })
                continue
            alert = {
                "alert_id": f"ALT-{self.next_id:04d}",
                **condition,
                "status": "active",
                "detected_at": now,
                "resolved_at": None,
            }
            self.next_id += 1
            self.alerts.insert(0, alert)
            self.active_by_condition[key] = alert

        del self.alerts[self.history_limit:]
        active = [alert for alert in self.alerts if alert["status"] == "active"]
        resolved = [alert for alert in self.alerts if alert["status"] == "resolved"]
        return {
            "summary": {
                "active": len(active),
                "critical": sum(alert["severity"] == "critical" for alert in active),
                "warning": sum(alert["severity"] == "warning" for alert in active),
                "notice": sum(alert["severity"] == "notice" for alert in active),
                "account_attention": len({
                    alert["related"].get("username")
                    for alert in active
                    if alert["source_type"] == "directory_account"
                }),
            },
            "active_alerts": active,
            "resolved_alerts": resolved,
            "alerts": self.alerts,
        }
