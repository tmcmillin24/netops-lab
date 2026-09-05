from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse

from containers.common.inventory import Inventory, InventoryError
from containers.printer.printer_service import PrinterConfig, PrinterOperationError, PrinterState

HTML_PATH = Path("/app/containers/printer/index.html")


def process_print_queue(printer, changed):
    while True:
        changed.wait()
        changed.clear()
        while printer.has_jobs():
            time.sleep(2)
            try:
                printer.complete_next_job()
            except PrinterOperationError:
                break


class PrinterHandler(BaseHTTPRequestHandler):
    printer = None
    queue_changed = None

    def send_json(self, data, code=200):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError
            return payload
        except (ValueError, json.JSONDecodeError) as error:
            raise PrinterOperationError("Request body must contain valid JSON.", 400, "invalid_json") from error

    def fail(self, error):
        data = self.printer.public_status()
        data["error"] = error.code
        self.send_json(data, error.status_code)

    def action(self, callback, wake=False):
        try:
            callback()
            if wake and self.printer.has_jobs():
                self.queue_changed.set()
            self.send_json(self.printer.public_status())
        except PrinterOperationError as error:
            self.fail(error)

    def add_job(self, source, pages=None):
        try:
            self.printer.add_job(source, pages)
            self.queue_changed.set()
            self.send_json(self.printer.public_status(), 201)
        except PrinterOperationError as error:
            self.fail(error)

    def do_GET(self):
        request = urlparse(self.path)
        routes = {
            "/status/offline": (self.printer.set_offline, False),
            "/status/ready": (self.printer.set_ready, True),
            "/queue/complete": (self.printer.complete_next_job, True),
            "/paper/empty": (self.printer.empty_paper, False),
            "/paper/refill": (self.printer.refill_paper, True),
            "/toner/empty": (self.printer.empty_toner, False),
            "/toner/refill": (self.printer.replace_toner, True),
        }
        if request.path == "/status":
            self.send_json(self.printer.public_status())
        elif request.path == "/queue/add":
            self.add_job(parse_qs(request.query).get("source", [""])[0])
        elif request.path in routes:
            callback, wake = routes[request.path]
            self.action(callback, wake)
        elif request.path == "/":
            html = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        routes = {
            "/jobs/complete": (self.printer.complete_next_job, True),
            "/state/offline": (self.printer.set_offline, False),
            "/state/ready": (self.printer.set_ready, True),
            "/paper/empty": (self.printer.empty_paper, False),
            "/paper/refill": (self.printer.refill_paper, True),
            "/toner/empty": (self.printer.empty_toner, False),
            "/toner/refill": (self.printer.replace_toner, True),
        }
        if path == "/jobs":
            try:
                body = self.read_json()
                self.add_job(body.get("source", ""), body.get("pages"))
            except PrinterOperationError as error:
                self.fail(error)
        elif path in routes:
            callback, wake = routes[path]
            self.action(callback, wake)
        else:
            self.send_error(404)


def main():
    try:
        inventory = Inventory.load()
        config = PrinterConfig.from_inventory(inventory, os.getenv("DEVICE_NAME", "PRNT01"))
    except InventoryError as error:
        raise SystemExit(f"Printer configuration error: {error}") from error
    printer = PrinterState(config)
    changed = threading.Event()
    PrinterHandler.printer = printer
    PrinterHandler.queue_changed = changed
    threading.Thread(target=process_print_queue, args=(printer, changed), daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 8080), PrinterHandler)
    print(f"{config.name} web service running on port 8080", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
