import json
import re
import subprocess

from backend.app.errors import LabServiceError


class DockerRuntime:
    container_prefix = "clab-netops-"
    network_interfaces = {
        "router_firewall": ("eth1",),
        "layer3_core_switch": ("eth1", "eth2", "eth3", "eth4"),
        "access_switch": ("br0",),
    }

    def _container_name(self, device):
        return f"{self.container_prefix}{device['id']}"

    def inspect(self, device):
        command = ["docker", "inspect", self._container_name(device)]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LabServiceError(
                "runtime_unavailable",
                "Docker runtime could not be queried.",
                503,
            ) from error

        if result.returncode != 0:
            return {"running": False, "management_ip": None}

        try:
            details = json.loads(result.stdout)[0]
            management_ip = details["NetworkSettings"]["Networks"]["clab"]["IPAddress"]
            return {
                "running": bool(details["State"]["Running"]),
                "management_ip": management_ip or None,
            }
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise LabServiceError(
                "runtime_response_invalid",
                f"Docker returned invalid state for {device['hostname']}.",
                503,
            ) from error

    def network_state(self, device):
        interfaces = self.network_interfaces.get(device["type"])
        if not interfaces:
            return None
        states = {}
        for interface in interfaces:
            command = [
                "docker", "exec", self._container_name(device),
                "cat", f"/sys/class/net/{interface}/flags",
            ]
            try:
                result = subprocess.run(
                    command, capture_output=True, check=False, text=True, timeout=2,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise LabServiceError(
                    "runtime_unavailable", "Network state could not be queried.", 503,
                ) from error
            try:
                flags = int(result.stdout.strip(), 0) if result.returncode == 0 else 0
                states[interface] = "up" if flags & 1 else "down"
            except ValueError:
                states[interface] = "unknown"
        required_interfaces = interfaces
        if device["type"] == "layer3_core_switch":
            required_interfaces = ("eth2", "eth3", "eth4")
        return {
            "interfaces": states,
            "operational": all(
                states[interface] in {"up", "unknown"}
                for interface in required_interfaces
            ),
        }

    def set_network_state(self, device, enabled):
        interfaces = self.network_interfaces.get(device["type"])
        if not interfaces:
            raise LabServiceError(
                "unsupported_device_action",
                f"{device['hostname']} does not support infrastructure controls.",
                400,
            )
        desired = "up" if enabled else "down"
        for interface in interfaces:
            command = [
                "docker", "exec", self._container_name(device),
                "ip", "link", "set", interface, desired,
            ]
            try:
                result = subprocess.run(
                    command, capture_output=True, check=False, text=True, timeout=2,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise LabServiceError(
                    "infrastructure_action_failed",
                    f"Unable to set {device['hostname']} {desired}.",
                    503,
                ) from error
            if result.returncode != 0:
                raise LabServiceError(
                    "infrastructure_action_failed",
                    result.stderr.strip() or f"Unable to set {device['hostname']} {desired}.",
                    503,
                )
        return self.network_state(device)

    def ping(self, source_device, destination_device):
        source_ip = source_device.get("ip_address")
        if not source_ip:
            raise LabServiceError(
                "source_has_no_ip",
                f"{source_device['hostname']} has no office-network IP address.",
                422,
            )
        destination_ip = destination_device.get("ip_address")
        if not destination_ip:
            raise LabServiceError(
                "destination_has_no_ip",
                f"{destination_device['hostname']} has no office-network IP address.",
                422,
            )

        command = [
            "docker",
            "exec",
            self._container_name(source_device),
            "ping",
            "-I",
            source_ip,
            "-c",
            "1",
            "-W",
            "1",
            destination_ip,
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LabServiceError(
                "connectivity_test_failed",
                "The controlled ping test could not be executed.",
                503,
            ) from error

        output = (result.stdout or result.stderr).strip()
        latency_match = re.search(r"time[=<]([0-9.]+)\s*ms", output)
        success = result.returncode == 0
        return {
            "source": source_device["hostname"],
            "destination": destination_device["hostname"],
            "destination_ip": destination_ip,
            "success": success,
            "latency_ms": float(latency_match.group(1)) if latency_match else None,
            "message": (
                f"{destination_device['hostname']} is reachable from {source_device['hostname']}."
                if success
                else f"{destination_device['hostname']} is not reachable from {source_device['hostname']}."
            ),
            "output": output,
        }
