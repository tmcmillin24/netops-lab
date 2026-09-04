from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import random
from pathlib import Path


MAX_PAPER = 175

printer_status = {
    "name": "PRNT01",
    "status": "ready",
    "toner": 82,
    "paper": MAX_PAPER,
    "queue": [],
    "message": "Printer is ready.",
    "paper_level": "normal",
    "toner_level": "normal",
    "last_event": "Printer initialized.",
    "last_event_type": "info"
}

next_job_id = 1001


def get_level(percent):
    if percent <= 0:
        return "empty"
    elif percent <= 25:
        return "very low"
    elif percent <= 50:
        return "low"
    elif percent <= 75:
        return "notice"
    else:
        return "normal"


def get_toner_usage(pages):
    if pages <= 5:
        return 1
    elif pages <= 10:
        return 2
    else:
        return 3


def update_resource_levels():
    paper_percent = (
        printer_status["paper"] / MAX_PAPER
    ) * 100

    printer_status["paper_level"] = get_level(
        paper_percent
    )

    printer_status["toner_level"] = get_level(
        printer_status["toner"]
    )


def update_printer_state():
    update_resource_levels()

    if printer_status["status"] == "offline":
        printer_status["message"] = "Printer is offline."
        return

    if printer_status["paper"] <= 0:
        printer_status["paper"] = 0
        printer_status["status"] = "attention"
        printer_status["message"] = "Paper tray is empty."
        return

    if printer_status["toner"] <= 0:
        printer_status["toner"] = 0
        printer_status["status"] = "attention"
        printer_status["message"] = "Toner is empty."
        return

    printer_status["status"] = "ready"

    warnings = []

    if printer_status["paper_level"] == "notice":
        warnings.append("Paper is getting low.")
    elif printer_status["paper_level"] == "low":
        warnings.append("Paper level is low.")
    elif printer_status["paper_level"] == "very low":
        warnings.append("Paper level is very low.")

    if printer_status["toner_level"] == "notice":
        warnings.append("Toner is getting low.")
    elif printer_status["toner_level"] == "low":
        warnings.append("Toner level is low.")
    elif printer_status["toner_level"] == "very low":
        warnings.append("Toner level is very low.")

    if warnings:
        printer_status["message"] = " ".join(warnings)
    else:
        printer_status["message"] = "Printer is ready."


def api_status():
    return {
        "name": printer_status["name"],
        "status": printer_status["status"],
        "toner": printer_status["toner"],
        "paper": printer_status["paper"],
        "paper_capacity": MAX_PAPER,
        "queue": len(printer_status["queue"]),
        "jobs": printer_status["queue"],
        "message": printer_status["message"],
        "paper_level": printer_status["paper_level"],
        "toner_level": printer_status["toner_level"],
        "last_event": printer_status["last_event"],
        "last_event_type": printer_status["last_event_type"]
    }


class PrinterHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        self.wfile.write(
            json.dumps(data).encode("utf-8")
        )

    def do_GET(self):
        global next_job_id

        if self.path == "/status":
            update_printer_state()
            self.send_json(api_status())

        elif self.path == "/status/offline":
            printer_status["status"] = "offline"
            printer_status["message"] = "Printer is offline."

            printer_status["last_event"] = (
                "PRNT01 was taken offline."
            )

            printer_status["last_event_type"] = "error"

            self.send_json(api_status())

        elif self.path == "/status/ready":
            printer_status["status"] = "ready"

            update_printer_state()

            printer_status["last_event"] = (
                "PRNT01 was brought online."
            )

            printer_status["last_event_type"] = "success"

            self.send_json(api_status())

        elif self.path == "/queue/add":

            if printer_status["status"] == "offline":

                printer_status["last_event"] = (
                    "PRINT FAILED: PRNT01 is offline. "
                    "Job was not added to the queue."
                )

                printer_status["last_event_type"] = "error"

                self.send_json(
                    api_status(),
                    status_code=409
                )

                return

            pages = random.randint(1, 15)

            toner_required = get_toner_usage(pages)

            job = {
                "id": next_job_id,
                "device": "WS01",
                "pages": pages,
                "toner_required": toner_required,
                "status": "queued"
            }

            printer_status["queue"].append(job)

            next_job_id += 1

            printer_status["last_event"] = (
                f"Job #{job['id']} from "
                f"{job['device']} added to queue: "
                f"{pages} pages."
            )

            printer_status["last_event_type"] = "success"

            self.send_json(api_status())

        elif self.path == "/queue/complete":

            if printer_status["status"] == "offline":

                printer_status["last_event"] = (
                    "PRINT FAILED: PRNT01 is offline."
                )

                printer_status["last_event_type"] = "error"

                self.send_json(
                    api_status(),
                    status_code=409
                )

                return

            if len(printer_status["queue"]) == 0:

                printer_status["last_event"] = (
                    "PRINT FAILED: Print queue is empty."
                )

                printer_status["last_event_type"] = "error"

                self.send_json(
                    api_status(),
                    status_code=409
                )

                return

            job = printer_status["queue"][0]

            pages = job["pages"]
            toner_required = job["toner_required"]

            if printer_status["paper"] < pages:

                job["status"] = "failed"

                printer_status["status"] = "attention"

                printer_status["message"] = (
                    "Insufficient paper."
                )

                printer_status["last_event"] = (
                    f"PRINT FAILED: Job #{job['id']} from "
                    f"{job['device']} requires {pages} sheets, "
                    f"but only {printer_status['paper']} remain."
                )

                printer_status["last_event_type"] = "error"

                self.send_json(
                    api_status(),
                    status_code=409
                )

                return

            if printer_status["toner"] < toner_required:

                job["status"] = "failed"

                printer_status["status"] = "attention"

                printer_status["message"] = (
                    "Insufficient toner."
                )

                printer_status["last_event"] = (
                    f"PRINT FAILED: Job #{job['id']} from "
                    f"{job['device']} cannot print because "
                    f"there is not enough toner."
                )

                printer_status["last_event_type"] = "error"

                self.send_json(
                    api_status(),
                    status_code=409
                )

                return

            printer_status["paper"] -= pages
            printer_status["toner"] -= toner_required

            printer_status["queue"].pop(0)

            update_printer_state()

            printer_status["last_event"] = (
                f"Job #{job['id']} from "
                f"{job['device']} completed successfully. "
                f"{pages} pages printed."
            )

            printer_status["last_event_type"] = "success"

            self.send_json(api_status())

        elif self.path == "/paper/empty":

            printer_status["paper"] = 0

            update_printer_state()

            printer_status["last_event"] = (
                "Paper tray was emptied."
            )

            printer_status["last_event_type"] = "error"

            self.send_json(api_status())

        elif self.path == "/paper/refill":

            printer_status["paper"] = MAX_PAPER

            if printer_status["status"] != "offline":
                printer_status["status"] = "ready"

            update_printer_state()

            printer_status["last_event"] = (
                f"Paper tray refilled to {MAX_PAPER} sheets."
            )

            printer_status["last_event_type"] = "success"

            self.send_json(api_status())

        elif self.path == "/toner/empty":

            printer_status["toner"] = 0

            update_printer_state()

            printer_status["last_event"] = (
                "Toner cartridge was emptied."
            )

            printer_status["last_event_type"] = "error"

            self.send_json(api_status())

        elif self.path == "/toner/refill":

            printer_status["toner"] = 100

            if printer_status["status"] != "offline":
                printer_status["status"] = "ready"

            update_printer_state()

            printer_status["last_event"] = (
                "Toner cartridge replaced."
            )

            printer_status["last_event_type"] = "success"

            self.send_json(api_status())

        elif self.path == "/":

            html = Path(
                "/printer/index.html"
            ).read_text()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html"
            )
            self.end_headers()

            self.wfile.write(
                html.encode("utf-8")
            )

        else:
            self.send_response(404)
            self.end_headers()


server = HTTPServer(
    ("0.0.0.0", 8080),
    PrinterHandler
)

print(
    "PRNT01 web service running on port 8080"
)

server.serve_forever()