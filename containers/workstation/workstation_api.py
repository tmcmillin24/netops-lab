from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import fcntl
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from containers.common.inventory import Inventory, InventoryError
from containers.workstation.workstation_service import WorkstationConfig, WorkstationOperationError, WorkstationState

INTERFACE = "eth1"
HTML_PATH = Path("/app/containers/workstation/index.html")


def run_network_command(command, failure_message):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WorkstationOperationError(failure_message) from error
    if result.returncode != 0:
        raise WorkstationOperationError(result.stderr.strip() or failure_message)


def set_office_interface(config, enabled):
    desired_state = "up" if enabled else "down"
    run_network_command(
        ["ip", "link", "set", INTERFACE, desired_state],
        f"Unable to set {INTERFACE} {desired_state}.",
    )
    if enabled:
        run_network_command(
            [
                "ip", "route", "replace", "10.10.0.0/16", "via",
                config.gateway, "dev", INTERFACE,
            ],
            "Unable to restore the office-network route.",
        )


def read_text(path, default="unknown"):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def get_ipv4_address(interface):
    request = struct.pack("256s", interface[:15].encode())
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            response = fcntl.ioctl(sock.fileno(), 0x8915, request)
            return socket.inet_ntoa(response[20:24])
        except OSError:
            return "unassigned"


def get_network_counters(interface):
    try:
        lines = Path("/proc/net/dev").read_text().splitlines()
    except OSError:
        lines = []
    for line in lines:
        if ":" in line and line.split(":", 1)[0].strip() == interface:
            fields = line.split(":", 1)[1].split()
            return {"rx_bytes": int(fields[0]), "rx_packets": int(fields[1]), "tx_bytes": int(fields[8]), "tx_packets": int(fields[9])}
    return {"rx_bytes": 0, "rx_packets": 0, "tx_bytes": 0, "tx_packets": 0}


def get_printer_status(config):
    try:
        with urlopen(f"http://{config.printer_ip}:8080/status", timeout=2) as response:
            printer = json.loads(response.read().decode())
        return {"reachable": True, "name": printer["name"], "status": printer["status"], "queue": printer["queue"]}
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return {"reachable": False, "name": config.printer_name, "status": "unreachable", "queue": None}


def get_workstation_status(state):
    config = state.config
    uptime = float(read_text("/proc/uptime", "0").split()[0])
    operational = state.operational_status()
    if operational["status"] == "online":
        printer = get_printer_status(config)
    else:
        printer = {
            "reachable": False,
            "name": config.printer_name,
            "status": "unreachable",
            "queue": None,
        }
    return {
        "name": config.name, **operational, "interface": INTERFACE,
        "interface_state": read_text(f"/sys/class/net/{INTERFACE}/operstate"),
        "ip_address": get_ipv4_address(INTERFACE), "configured_ip_address": config.ip_address,
        "connected_switch": config.connected_switch,
        "mac_address": read_text(f"/sys/class/net/{INTERFACE}/address"),
        "uptime_seconds": int(uptime), "network": get_network_counters(INTERFACE),
        "printer": printer,
    }


def submit_print_job(state):
    config = state.config
    try:
        state.require_online()
        request = Request(f"http://{config.printer_ip}:8080/jobs", data=json.dumps({"source": config.name}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=3) as response:
            printer = json.loads(response.read().decode())
        job = printer["jobs"][-1]
        message = f"Job #{job['id']} sent to {config.printer_name}: {job['pages']} {'page' if job['pages'] == 1 else 'pages'} queued."
        state.record_event(message, "success")
        return {"success": True, "message": message, "job": {**job, "printer": printer["name"]}}, 200
    except WorkstationOperationError as error:
        message, code = str(error), 409
    except HTTPError as error:
        code = error.code
        try:
            message = json.loads(error.read().decode()).get("last_event", f"{config.printer_name} rejected the job.")
        except json.JSONDecodeError:
            message = f"{config.printer_name} rejected the print job."
    except (URLError, TimeoutError, json.JSONDecodeError, KeyError):
        message, code = f"PRINT FAILED: {config.name} could not reach {config.printer_name} at {config.printer_ip}:8080.", 503
    state.record_event(message, "error")
    return {"success": False, "message": message}, code


class WorkstationHandler(BaseHTTPRequestHandler):
    workstation = None

    def send_json(self, data, code=200):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/status":
            self.send_json(get_workstation_status(self.workstation))
        elif self.path == "/print":
            data, code = submit_print_job(self.workstation)
            self.send_json(data, code)
        elif self.path == "/":
            html = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/print-jobs":
            data, code = submit_print_job(self.workstation)
            self.send_json(data, code)
        elif self.path == "/state/offline":
            try:
                set_office_interface(self.workstation.config, False)
                self.workstation.set_offline()
                self.send_json(get_workstation_status(self.workstation))
            except WorkstationOperationError as error:
                self.send_json(
                    {"error": "interface_control_failed", "message": str(error)},
                    503,
                )
        elif self.path == "/state/online":
            try:
                set_office_interface(self.workstation.config, True)
                self.workstation.set_online()
                self.send_json(get_workstation_status(self.workstation))
            except WorkstationOperationError as error:
                self.send_json(
                    {"error": "interface_control_failed", "message": str(error)},
                    503,
                )
        else:
            self.send_error(404)


def main():
    try:
        if os.getenv("DEVICE_DYNAMIC") == "true":
            config = WorkstationConfig.from_environment()
        else:
            inventory = Inventory.load()
            config = WorkstationConfig.from_inventory(inventory, os.getenv("DEVICE_NAME", "WS01"))
    except InventoryError as error:
        raise SystemExit(f"Workstation configuration error: {error}") from error
    WorkstationHandler.workstation = WorkstationState(config)
    server = ThreadingHTTPServer(("0.0.0.0", 8081), WorkstationHandler)
    print(f"{config.name} web service running on port 8081", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
