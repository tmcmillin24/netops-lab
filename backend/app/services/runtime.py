import json
import re
import subprocess

from backend.app.errors import LabServiceError


class DockerRuntime:
    container_prefix = "clab-netops-"
    network_interfaces = {
        "router_firewall": ("eth1",),
        "layer3_core_switch": ("eth1", "eth2", "eth3", "eth4", "eth5", "eth6", "br-services"),
        "access_switch": ("br0",),
        "domain_controller": ("eth1",),
        "file_server": ("eth1",),
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
            required_interfaces = tuple(
                interface for interface in interfaces if interface not in {"eth1", "eth5", "eth6"}
            )
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
                    f"Unable to set {device['hostname']} {desired}.",
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

    def traceroute(self, source_device, destination_device):
        source_ip = source_device.get("ip_address")
        destination_ip = destination_device.get("ip_address")
        if not source_ip or not destination_ip:
            raise LabServiceError(
                "diagnostic_ip_missing",
                "Traceroute requires known office-network source and destination IPs.",
                422,
            )
        command = [
            "docker", "exec", self._container_name(source_device),
            "traceroute", "-n", "-m", "8", "-w", "1", "-q", "1", destination_ip,
        ]
        result = self._run_diagnostic(command, timeout=12)
        output = (result.stdout or result.stderr).strip()
        hops = [line.strip() for line in output.splitlines()[1:] if line.strip()]
        success = any(destination_ip in hop and "*" not in hop for hop in hops)
        return {
            "diagnostic_type": "traceroute",
            "source": source_device["hostname"],
            "destination": destination_device["hostname"],
            "destination_ip": destination_ip,
            "success": success,
            "message": (
                f"Route to {destination_device['hostname']} completed."
                if success else f"Route to {destination_device['hostname']} did not complete."
            ),
            "hops": hops,
        }

    def dns_lookup(self, source_device, destination_device):
        lookup_name = self._container_name(destination_device)
        command = [
            "docker", "exec", self._container_name(source_device),
            "nslookup", lookup_name,
        ]
        result = self._run_diagnostic(command, timeout=5)
        output = (result.stdout or result.stderr).strip()
        addresses = re.findall(r"^Address:\s+([^\s]+)", output, re.MULTILINE)
        resolved = [address for address in addresses if not address.startswith("127.0.0.11")]
        success = result.returncode == 0 and bool(resolved)
        return {
            "diagnostic_type": "dns",
            "source": source_device["hostname"],
            "destination": destination_device["hostname"],
            "query": lookup_name,
            "success": success,
            "addresses": resolved,
            "output": output,
            "message": (
                f"{lookup_name} resolved on the Containerlab management network."
                if success else f"{lookup_name} could not be resolved."
            ),
        }

    def network_info(self, device):
        commands = {
            "routes": ["docker", "exec", self._container_name(device), "ip", "route", "show"],
            "neighbors": ["docker", "exec", self._container_name(device), "ip", "neigh", "show"],
        }
        data = {}
        for key, command in commands.items():
            result = self._run_diagnostic(command, timeout=3)
            if result.returncode != 0:
                raise LabServiceError(
                    "diagnostic_failed",
                    f"Network information is unavailable for {device['hostname']}.",
                    503,
                )
            data[key] = [line for line in result.stdout.splitlines() if line.strip()]
        return data

    def dc_command(self, arguments, timeout=8):
        command = ["docker", "exec", "clab-netops-dc01", *arguments]
        try:
            result = subprocess.run(
                command, capture_output=True, check=False, text=True, timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LabServiceError(
                "directory_unavailable",
                "DC01 could not complete the directory operation.",
                503,
            ) from error
        if result.returncode != 0:
            raise LabServiceError(
                "directory_operation_failed",
                "DC01 rejected the controlled directory operation.",
                409,
            )
        return result.stdout

    @staticmethod
    def _run_diagnostic(command, timeout):
        try:
            return subprocess.run(
                command, capture_output=True, check=False, text=True, timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LabServiceError(
                "diagnostic_failed", "The controlled diagnostic could not be executed.", 503,
            ) from error
