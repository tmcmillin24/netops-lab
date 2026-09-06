import asyncio
from datetime import datetime, timezone

import httpx

from backend.app.errors import LabServiceError, UnknownDeviceError
from backend.app.services.alerts import AlertTracker


class LabService:
    endpoint_ports = {"printer": 8080, "workstation": 8081, "file_server": 8092}

    def __init__(self, inventory, runtime, timeout=2.0):
        self.inventory = inventory
        self.runtime = runtime
        self.timeout = timeout
        self.events = []
        self.connectivity_results = {}
        self.observed_health = {}
        self.alert_tracker = AlertTracker()

    def record_event(self, hostname, message, event_type):
        self.events.insert(0, {
            "hostname": hostname,
            "message": message,
            "type": event_type,
            "severity": event_type,
            "event_type": "state_change",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        del self.events[50:]

    def affected_by_infrastructure(self, device):
        if device["type"] == "access_switch":
            return [
                item["hostname"]
                for item in self.current_devices
                if item.get("connected_to") == device["hostname"]
            ]
        if device["type"] == "layer3_core_switch":
            return [
                item["hostname"]
                for item in self.current_devices
                if item["hostname"] not in {"RTR01", "CORE01"}
            ]
        if device["type"] == "router_firewall":
            return [
                item["hostname"]
                for item in self.current_devices
                if item["hostname"] != "RTR01"
            ]
        return []

    @property
    def current_devices(self):
        return [
            device
            for device in self.inventory.devices.values()
            if device.get("phase") == "current"
        ]

    def get_device_config(self, hostname, expected_type=None):
        try:
            device = self.inventory.get_device(hostname, expected_type)
        except (ValueError, AttributeError):
            raise UnknownDeviceError(str(hostname))
        if device.get("phase") != "current":
            raise UnknownDeviceError(str(hostname))
        return device

    async def runtime_info(self, device):
        return await asyncio.to_thread(self.runtime.inspect, device)

    async def request_endpoint(self, device, method="GET", path="/status", json=None):
        runtime = await self.runtime_info(device)
        if not runtime["running"] or not runtime["management_ip"]:
            raise LabServiceError(
                "device_unavailable",
                f"{device['hostname']} container is not available.",
                503,
            )
        port = self.endpoint_ports[device["type"]]
        url = f"http://{runtime['management_ip']}:{port}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, json=json)
        except httpx.RequestError as error:
            raise LabServiceError(
                "device_service_unreachable",
                f"{device['hostname']} service is unreachable.",
                503,
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise LabServiceError(
                "device_response_invalid",
                f"{device['hostname']} returned an invalid response.",
                502,
            ) from error

        if response.is_error:
            raise LabServiceError(
                payload.get("error", "device_operation_failed"),
                payload.get("last_event") or payload.get("message") or f"{device['hostname']} rejected the operation.",
                response.status_code,
                payload,
            )
        return payload

    async def device_status(self, device):
        network = next(
            (
                network
                for network in self.inventory.data["networks"]
                if network["id"] == device.get("network")
            ),
            {},
        )
        base = {
            "hostname": device["hostname"],
            "device_type": device["type"],
            "ip_address": device.get("ip_address"),
            "network": device.get("network"),
            "connected_switch": device.get("connected_to"),
            "assigned_printer": device.get("assigned_printer"),
            "domain_joined": device.get("domain_joined"),
            "ad_computer_object": device.get("ad_computer_object"),
            "assigned_user": device.get("assigned_user"),
            "dynamic": bool(device.get("dynamic")),
            "form_factor": device.get("form_factor", "workstation" if device["type"] == "workstation" else None),
            "platform": device.get("platform"),
            "dns_domain": device.get("dns_domain"),
            "floor": network.get("floor"),
            "department": network.get("department"),
            "host_port": device.get("host_port"),
        }
        runtime = await self.runtime_info(device)
        base["container_running"] = runtime["running"]
        base["reachable"] = runtime["running"]

        if device["type"] not in self.endpoint_ports:
            network_state = await asyncio.to_thread(self.runtime.network_state, device)
            operational = runtime["running"] and bool(network_state and network_state["operational"])
            return {
                **base,
                "status": "online" if operational else "offline",
                "reachable": operational,
                "service_health": "not_applicable",
                "status_source": "linux_interface_state",
                "live": network_state,
            }
        if not runtime["running"]:
            return {
                **base,
                "status": "offline",
                "service_health": "unavailable",
                "status_source": "container_runtime",
            }
        try:
            live = await self.request_endpoint(device)
            endpoint_reachable = runtime["running"]
            if device["type"] == "workstation":
                endpoint_reachable = (
                    live.get("status") == "online"
                    and live.get("interface_state") == "up"
                )
            service_health = live.get("service_health", "available")
            return {
                **base,
                "status": live["status"],
                "reachable": endpoint_reachable,
                "service_health": service_health,
                "status_source": "device_service",
                "live": live,
            }
        except LabServiceError as error:
            return {
                **base,
                "status": "unavailable",
                "reachable": False,
                "service_health": "unavailable",
                "status_source": "device_service",
                "service_error": error.message,
            }

    async def all_device_statuses(self):
        devices = await asyncio.gather(*(self.device_status(device) for device in self.current_devices))
        by_name = {device["hostname"]: device for device in devices}
        for device in devices:
            dependencies = []
            if device["hostname"] == "CORE01":
                dependencies = ["RTR01"]
            elif device["device_type"] == "access_switch":
                dependencies = ["CORE01", "RTR01"]
            elif device["device_type"] == "domain_controller":
                dependencies = ["CORE01", "RTR01"]
            elif device["device_type"] == "file_server":
                dependencies = ["CORE01", "RTR01"]
            elif device["device_type"] in self.endpoint_ports:
                dependencies = [device["connected_switch"], "CORE01", "RTR01"]
            failed = [name for name in dependencies if by_name.get(name, {}).get("status") == "offline"]
            if failed:
                device["dependency_status"] = "impacted"
                device["impacted_by"] = failed
                device["impact_reason"] = f"Upstream connectivity affected by {', '.join(failed)}."
                if device.get("connected_switch") in failed:
                    device["reachable"] = False
            else:
                device["dependency_status"] = "normal"
                device["impacted_by"] = []
        return devices

    async def status_for_hostname(self, hostname):
        self.get_device_config(hostname)
        devices = await self.all_device_statuses()
        return next(device for device in devices if device["hostname"] == hostname.upper())

    async def overview(self, account_health=None):
        devices = await self.all_device_statuses()
        self.observe_health_changes(devices)
        printers = [device for device in devices if device["device_type"] == "printer"]
        unavailable = [
            device
            for device in devices
            if device["status"] in {"offline", "unavailable"}
            or device.get("dependency_status") == "impacted"
        ]
        attention = [device for device in printers if device["status"] == "attention"]
        unhealthy_services = [
            device for device in devices
            if device["device_type"] == "file_server"
            and device["status"] == "online"
            and device["service_health"] in {"attention", "unavailable"}
        ]
        # The dashboard's impacted list covers both dependency failures and a
        # device that has been taken directly offline. This keeps an isolated
        # workstation fault visible even when its upstream path is healthy.
        impacted = [
            device
            for device in devices
            if device in unavailable
        ]
        jobs = sum(device.get("live", {}).get("queue", 0) for device in printers)
        monitoring = self.alert_tracker.reconcile(devices, account_health)
        return {
            "total_devices": len(devices),
            "online_devices": len(devices) - len(unavailable),
            "offline_devices": len(unavailable),
            "printers_requiring_attention": len(attention),
            "services_requiring_attention": len(unhealthy_services),
            "file_service_alerts": [
                {
                    "hostname": device["hostname"],
                    "reason": device.get("live", {}).get("last_event", "File services require attention."),
                }
                for device in unhealthy_services
            ],
            "printer_alerts": [
                {
                    "hostname": device["hostname"],
                    "reason": device.get("live", {}).get("message", "Printer requires attention."),
                }
                for device in attention
            ],
            "impacted_devices": len(impacted),
            "impacted_device_alerts": [
                {
                    "hostname": device["hostname"],
                    "reason": (
                        device.get("impact_reason")
                        or device.get("live", {}).get("message")
                        or f"{device['hostname']} is offline."
                    ),
                }
                for device in impacted
            ],
            "active_print_jobs": jobs,
            "network_health": "healthy" if not unavailable and not unhealthy_services else "degraded",
            "operational_health": "degraded" if monitoring["summary"]["active"] else "healthy",
            "monitoring": monitoring,
            "account_health": account_health,
            "recent_events": self.events[:15],
            "devices": devices,
        }

    def observe_health_changes(self, devices):
        for device in devices:
            message = device.get("live", {}).get("message") or device.get("impact_reason")
            signature = (device["status"], device.get("dependency_status"), message)
            previous = self.observed_health.get(device["hostname"])
            self.observed_health[device["hostname"]] = signature
            if previous is None or previous == signature:
                continue
            unhealthy = (
                device["status"] in {"offline", "unavailable", "attention"}
                or device.get("dependency_status") == "impacted"
            )
            self.record_event(
                device["hostname"],
                message or (
                    f"{device['hostname']} requires attention."
                    if unhealthy else f"{device['hostname']} recovered."
                ),
                "warning" if unhealthy else "success",
            )

    async def infrastructure_action(self, hostname, action):
        if action not in {"disable", "restore"}:
            raise LabServiceError("unknown_action", f"Unsupported infrastructure action: {action}", 404)
        device = self.get_device_config(hostname)
        if device["type"] not in self.runtime.network_interfaces:
            raise LabServiceError(
                "unsupported_device_action",
                f"{device['hostname']} does not support infrastructure controls.",
                400,
            )
        if action == "restore" and device["type"] == "access_switch":
            core = self.get_device_config("CORE01", "layer3_core_switch")
            core_status = await self.device_status(core)
            if core_status["status"] != "online":
                raise LabServiceError(
                    "upstream_unavailable",
                    (
                        f"{device['hostname']} cannot be restored while CORE01 is offline. "
                        "Restore CORE01 first."
                    ),
                    409,
                    {"blocked_by": ["CORE01"]},
                )
        state = await asyncio.to_thread(
            self.runtime.set_network_state, device, action == "restore"
        )
        disabled = action == "disable"
        self.record_event(
            device["hostname"],
            f"{device['hostname']} network function was {'disabled' if disabled else 'restored'}.",
            "error" if disabled else "success",
        )
        for affected_hostname in self.affected_by_infrastructure(device):
            self.record_event(
                affected_hostname,
                (
                    f"Connectivity impacted by {device['hostname']}."
                    if disabled
                    else f"Connectivity recovered after {device['hostname']} was restored."
                ),
                "warning" if disabled else "success",
            )
        return {
            "hostname": device["hostname"],
            "status": "online" if state["operational"] else "offline",
            "interfaces": state["interfaces"],
        }

    async def submit_job(self, printer_name, request):
        printer = self.get_device_config(printer_name, "printer")
        workstation = self.get_device_config(request.source, "workstation")
        if workstation.get("assigned_printer") != printer["hostname"]:
            raise LabServiceError(
                "invalid_source",
                f"{workstation['hostname']} is not assigned to {printer['hostname']}.",
                400,
            )
        payload = {"source": workstation["hostname"]}
        if request.pages is not None:
            payload["pages"] = request.pages
        return await self.request_endpoint(printer, "POST", "/jobs", payload)

    async def printer_action(self, hostname, action):
        paths = {
            "complete": "/jobs/complete",
            "offline": "/state/offline",
            "ready": "/state/ready",
            "empty-paper": "/paper/empty",
            "refill-paper": "/paper/refill",
            "empty-toner": "/toner/empty",
            "refill-toner": "/toner/refill",
        }
        if action not in paths:
            raise LabServiceError("unknown_action", f"Unsupported printer action: {action}", 404)
        printer = self.get_device_config(hostname, "printer")
        result = await self.request_endpoint(printer, "POST", paths[action])
        self.record_event(
            printer["hostname"],
            result.get("last_event") or result.get("message") or f"Printer action {action} completed.",
            result.get("last_event_type", "info"),
        )
        return result

    async def workstation_action(self, hostname, action):
        paths = {"offline": "/state/offline", "online": "/state/online"}
        if action not in paths:
            raise LabServiceError("unknown_action", f"Unsupported workstation action: {action}", 404)
        workstation = self.get_device_config(hostname, "workstation")
        result = await self.request_endpoint(workstation, "POST", paths[action])
        self.record_event(
            workstation["hostname"],
            result.get("last_event") or f"Workstation action {action} completed.",
            result.get("last_event_type", "info"),
        )
        return result

    async def ping(self, request):
        source = self.get_device_config(request.source)
        destination = self.get_device_config(request.destination)
        result = await asyncio.to_thread(self.runtime.ping, source, destination)
        self.record_connectivity_result("ping", result)
        return result

    async def diagnostic(self, request):
        source = self.get_device_config(request.source)
        destination = self.get_device_config(request.destination)
        if request.diagnostic_type in {"ping", "reachability"}:
            result = await asyncio.to_thread(self.runtime.ping, source, destination)
            result["diagnostic_type"] = request.diagnostic_type
        elif request.diagnostic_type == "traceroute":
            result = await asyncio.to_thread(self.runtime.traceroute, source, destination)
        elif request.diagnostic_type == "dns":
            result = await asyncio.to_thread(self.runtime.dns_lookup, source, destination)
        else:
            status = await self.status_for_hostname(destination["hostname"])
            success = status["service_health"] in {"available", "not_applicable"}
            result = {
                "diagnostic_type": "service-health",
                "source": source["hostname"],
                "destination": destination["hostname"],
                "success": success,
                "service_health": status["service_health"],
                "device_status": status["status"],
                "message": (
                    f"{destination['hostname']} service health is {status['service_health']}."
                ),
            }
        self.record_connectivity_result(request.diagnostic_type, result)
        return result

    def record_connectivity_result(self, diagnostic_type, result):
        key = (diagnostic_type, result["source"], result["destination"])
        previous = self.connectivity_results.get(key)
        self.connectivity_results[key] = result["success"]
        if not result["success"]:
            self.record_event(
                result["source"], result["message"], "error"
            )
            self.events[0]["event_type"] = f"{diagnostic_type}_failed"
        elif previous is False:
            message = (
                f"Connectivity from {result['source']} to {result['destination']} was restored."
            )
            self.record_event(result["source"], message, "success")
            self.events[0]["event_type"] = "connectivity_restored"

    async def network_info(self, hostname):
        device = self.get_device_config(hostname)
        runtime = await self.runtime_info(device)
        if not runtime["running"]:
            raise LabServiceError(
                "device_unavailable", f"{device['hostname']} is unavailable.", 503,
            )
        data = await asyncio.to_thread(self.runtime.network_info, device)
        return {"hostname": device["hostname"], **data}
