import asyncio

import httpx

from backend.app.errors import LabServiceError, UnknownDeviceError


class LabService:
    endpoint_ports = {"printer": 8080, "workstation": 8081}

    def __init__(self, inventory, runtime, timeout=2.0):
        self.inventory = inventory
        self.runtime = runtime
        self.timeout = timeout

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
        base = {
            "hostname": device["hostname"],
            "device_type": device["type"],
            "ip_address": device.get("ip_address"),
            "network": device.get("network"),
            "connected_switch": device.get("connected_to"),
            "assigned_printer": device.get("assigned_printer"),
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
            return {
                **base,
                "status": live["status"],
                "reachable": endpoint_reachable,
                "service_health": "available",
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

    async def overview(self):
        devices = await self.all_device_statuses()
        printers = [device for device in devices if device["device_type"] == "printer"]
        unavailable = [
            device
            for device in devices
            if device["status"] in {"offline", "unavailable"}
            or device.get("dependency_status") == "impacted"
        ]
        attention = [device for device in printers if device["status"] == "attention"]
        impacted = [device for device in devices if device.get("dependency_status") == "impacted"]
        jobs = sum(device.get("live", {}).get("queue", 0) for device in printers)
        return {
            "total_devices": len(devices),
            "online_devices": len(devices) - len(unavailable),
            "offline_devices": len(unavailable),
            "printers_requiring_attention": len(attention),
            "printer_alerts": [
                {
                    "hostname": device["hostname"],
                    "reason": device.get("live", {}).get("message", "Printer requires attention."),
                }
                for device in attention
            ],
            "impacted_devices": len(impacted),
            "active_print_jobs": jobs,
            "network_health": "healthy" if not unavailable else "degraded",
        }

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
        state = await asyncio.to_thread(
            self.runtime.set_network_state, device, action == "restore"
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
        return await self.request_endpoint(printer, "POST", paths[action])

    async def workstation_action(self, hostname, action):
        paths = {"offline": "/state/offline", "online": "/state/online"}
        if action not in paths:
            raise LabServiceError("unknown_action", f"Unsupported workstation action: {action}", 404)
        workstation = self.get_device_config(hostname, "workstation")
        return await self.request_endpoint(workstation, "POST", paths[action])

    async def ping(self, request):
        source = self.get_device_config(request.source)
        destination = self.get_device_config(request.destination)
        return await asyncio.to_thread(self.runtime.ping, source, destination)
