import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SHARES = json.loads(Path("/config/fileserver_shares.json").read_text())["shares"]


class FileServerState:
    def __init__(self):
        self.lock = threading.Lock()
        self.disabled_shares = set()
        self.read_only_shares = set()
        self.last_event = "FILE01 initialized with SMB file services."
        self.smb_process = None
        self.start_smb()

    def interface_online(self):
        try:
            flags = int(Path("/sys/class/net/eth1/flags").read_text().strip(), 0)
            return bool(flags & 1)
        except (OSError, ValueError):
            return False

    def smb_running(self):
        return self.smb_process is not None and self.smb_process.poll() is None

    def start_smb(self):
        if not self.smb_running():
            self.smb_process = subprocess.Popen(["smbd", "--foreground", "--no-process-group"])

    def stop_smb(self):
        if self.smb_running():
            self.smb_process.terminate()
            self.smb_process.wait(timeout=3)

    def status(self):
        online = self.interface_online()
        service = self.smb_running()
        shares = [
            {
                **share,
                "enabled": share["name"] not in self.disabled_shares,
                "read_only": share["name"] in self.read_only_shares,
            }
            for share in SHARES
        ]
        unhealthy = [share for share in shares if not share["enabled"] or share["read_only"]]
        return {
            "hostname": "FILE01",
            "ip_address": "10.10.40.20",
            "status": "online" if online else "offline",
            "service_health": "available" if online and service and not unhealthy else "unavailable" if not online or not service else "attention",
            "smb_running": service,
            "share_count": len(shares),
            "shares": shares,
            "last_event": self.last_event,
        }

    def action(self, action, share_name=None):
        known = {share["name"] for share in SHARES}
        if share_name is not None and share_name not in known:
            raise ValueError("Unknown configured share.")
        if action == "offline":
            subprocess.run(["ip", "link", "set", "eth1", "down"], check=True)
            self.last_event = "FILE01 office interface set offline."
        elif action == "online":
            subprocess.run(["ip", "link", "set", "eth1", "up"], check=True)
            subprocess.run(
                ["ip", "route", "replace", "10.10.0.0/16", "via", "10.10.40.1", "dev", "eth1"],
                check=True,
            )
            self.last_event = "FILE01 office interface restored."
        elif action == "service-stop":
            self.stop_smb()
            self.last_event = "SMB service stopped."
        elif action == "service-start":
            self.start_smb()
            self.last_event = "SMB service started."
        elif action == "share-disable" and share_name:
            self.disabled_shares.add(share_name)
            self.last_event = f"{share_name} share disabled."
        elif action == "share-enable" and share_name:
            self.disabled_shares.discard(share_name)
            self.last_event = f"{share_name} share enabled."
        elif action == "read-only" and share_name:
            self.read_only_shares.add(share_name)
            self.last_event = f"{share_name} share set read-only."
        elif action == "read-write" and share_name:
            self.read_only_shares.discard(share_name)
            self.last_event = f"{share_name} share write access restored."
        else:
            raise ValueError("Unsupported FILE01 fault action.")
        return self.status()


STATE = FileServerState()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in {"/", "/status", "/shares"}:
            status = STATE.status()
            self.send_json(status if self.path != "/shares" else {"shares": status["shares"]})
            return
        self.send_json({"error": "not_found", "message": "Unknown FILE01 route."}, 404)

    def do_POST(self):
        if not self.path.startswith("/faults/"):
            self.send_json({"error": "not_found", "message": "Unknown FILE01 route."}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = STATE.action(self.path.removeprefix("/faults/"), payload.get("share"))
            self.send_json(result)
        except (ValueError, subprocess.SubprocessError) as error:
            self.send_json({"error": "invalid_fault", "message": str(error)}, 422)

    def log_message(self, format_string, *arguments):
        return


ThreadingHTTPServer(("0.0.0.0", 8092), Handler).serve_forever()
