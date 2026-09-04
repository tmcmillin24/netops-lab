from dataclasses import dataclass
import random
import threading


MAX_PAPER = 175
INITIAL_TONER = 82


class PrinterOperationError(RuntimeError):

    def __init__(self, message, status_code=409, code="operation_failed"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class PrinterConfig:
    name: str
    ip_address: str
    connected_switch: str
    allowed_sources: frozenset

    @classmethod
    def from_inventory(cls, inventory, device_name):
        device = inventory.get_device(device_name, "printer")

        return cls(
            name=device["hostname"],
            ip_address=device["ip_address"],
            connected_switch=device["connected_to"],
            allowed_sources=frozenset(
                inventory.workstations_for_printer(device["hostname"])
            )
        )


def get_level(percent):
    if percent <= 0:
        return "empty"
    if percent <= 25:
        return "very low"
    if percent <= 50:
        return "low"
    if percent <= 75:
        return "notice"
    return "normal"


def get_toner_usage(pages):
    if pages <= 5:
        return 1
    if pages <= 10:
        return 2
    return 3


class PrinterState:

    def __init__(self, config, rng=None):
        self.config = config
        self.rng = rng or random.Random()
        self.status_name = "ready"
        self.toner = INITIAL_TONER
        self.paper = MAX_PAPER
        self.queue = []
        self.message = "Printer is ready."
        self.paper_level = "normal"
        self.toner_level = "normal"
        self.last_event = "Printer initialized."
        self.last_event_type = "info"
        self.next_job_id = 1001
        self.lock = threading.RLock()

    def _update_resource_levels(self):
        paper_percent = (self.paper / MAX_PAPER) * 100
        self.paper_level = get_level(paper_percent)
        self.toner_level = get_level(self.toner)

    def _update_state(self):
        self._update_resource_levels()

        if self.status_name == "offline":
            self.message = "Printer is offline."
            return

        if self.paper <= 0:
            self.paper = 0
            self.status_name = "attention"
            self.message = "Paper tray is empty."
            return

        if self.toner <= 0:
            self.toner = 0
            self.status_name = "attention"
            self.message = "Toner is empty."
            return

        if self.queue and self.queue[0]["status"] == "failed":
            job = self.queue[0]
            if self.paper < job["pages"]:
                self.status_name = "attention"
                self.message = "Insufficient paper."
                return
            if self.toner < job["toner_required"]:
                self.status_name = "attention"
                self.message = "Insufficient toner."
                return

        self.status_name = "ready"
        warnings = []

        paper_messages = {
            "notice": "Paper is getting low.",
            "low": "Paper level is low.",
            "very low": "Paper level is very low."
        }
        toner_messages = {
            "notice": "Toner is getting low.",
            "low": "Toner level is low.",
            "very low": "Toner level is very low."
        }

        if self.paper_level in paper_messages:
            warnings.append(paper_messages[self.paper_level])
        if self.toner_level in toner_messages:
            warnings.append(toner_messages[self.toner_level])

        self.message = " ".join(warnings) or "Printer is ready."

    def public_status(self):
        with self.lock:
            self._update_state()

            visible_jobs = [
                {
                    "id": job["id"],
                    "device": job["device"],
                    "pages": job["pages"],
                    "status": job["status"]
                }
                for job in self.queue
            ]

            return {
                "name": self.config.name,
                "ip_address": self.config.ip_address,
                "connected_switch": self.config.connected_switch,
                "status": self.status_name,
                "toner": self.toner,
                "paper": self.paper,
                "paper_capacity": MAX_PAPER,
                "queue": len(self.queue),
                "jobs": visible_jobs,
                "message": self.message,
                "paper_level": self.paper_level,
                "toner_level": self.toner_level,
                "last_event": self.last_event,
                "last_event_type": self.last_event_type
            }

    def has_jobs(self):
        with self.lock:
            return bool(self.queue)

    def set_offline(self):
        with self.lock:
            self.status_name = "offline"
            self.message = "Printer is offline."
            self.last_event = f"{self.config.name} was taken offline."
            self.last_event_type = "error"

    def set_ready(self):
        with self.lock:
            self.status_name = "ready"
            self._update_state()
            self.last_event = f"{self.config.name} was brought online."
            self.last_event_type = "success"

    def add_job(self, source, pages=None):
        with self.lock:
            if not isinstance(source, str):
                raise PrinterOperationError(
                    "Print source must be a workstation hostname.",
                    status_code=400,
                    code="invalid_source"
                )
            workstation = source.strip().upper()

            if workstation not in self.config.allowed_sources:
                raise PrinterOperationError(
                    f"{workstation} is not allowed to submit jobs "
                    f"to {self.config.name}.",
                    status_code=400,
                    code="invalid_source"
                )

            if self.status_name == "offline":
                self.last_event = (
                    f"PRINT FAILED: {self.config.name} is offline. "
                    "Job was not added to the queue."
                )
                self.last_event_type = "error"
                raise PrinterOperationError(
                    self.last_event,
                    code="printer_offline"
                )

            page_count = pages if pages is not None else self.rng.randint(1, 15)

            if (
                isinstance(page_count, bool)
                or not isinstance(page_count, int)
                or not 1 <= page_count <= 15
            ):
                raise PrinterOperationError(
                    "Page count must be an integer from 1 to 15.",
                    status_code=400,
                    code="invalid_page_count"
                )

            job = {
                "id": self.next_job_id,
                "device": workstation,
                "pages": page_count,
                "toner_required": get_toner_usage(page_count),
                "status": "queued"
            }
            self.queue.append(job)
            self.next_job_id += 1
            self.last_event = (
                f"Job #{job['id']} from {workstation} added to queue: "
                f"{page_count} {'page' if page_count == 1 else 'pages'}."
            )
            self.last_event_type = "success"

            return {
                "id": job["id"],
                "device": job["device"],
                "pages": job["pages"],
                "status": job["status"]
            }

    def complete_next_job(self):
        with self.lock:
            if self.status_name == "offline":
                self.last_event = (
                    f"PRINT FAILED: {self.config.name} is offline."
                )
                self.last_event_type = "error"
                raise PrinterOperationError(
                    self.last_event,
                    code="printer_offline"
                )

            if not self.queue:
                self.last_event = "PRINT FAILED: Print queue is empty."
                self.last_event_type = "error"
                raise PrinterOperationError(
                    self.last_event,
                    code="queue_empty"
                )

            job = self.queue[0]

            if self.paper < job["pages"]:
                job["status"] = "failed"
                self.status_name = "attention"
                self.message = "Insufficient paper."
                self.last_event = (
                    f"PRINT FAILED: Job #{job['id']} from {job['device']} "
                    f"requires {job['pages']} sheets, but only "
                    f"{self.paper} remain."
                )
                self.last_event_type = "error"
                raise PrinterOperationError(
                    self.last_event,
                    code="insufficient_paper"
                )

            if self.toner < job["toner_required"]:
                job["status"] = "failed"
                self.status_name = "attention"
                self.message = "Insufficient toner."
                self.last_event = (
                    f"PRINT FAILED: Job #{job['id']} from {job['device']} "
                    "cannot print because there is not enough toner."
                )
                self.last_event_type = "error"
                raise PrinterOperationError(
                    self.last_event,
                    code="insufficient_toner"
                )

            self.paper -= job["pages"]
            self.toner -= job["toner_required"]
            self.queue.pop(0)
            self._update_state()
            pages = job["pages"]
            self.last_event = (
                f"Job #{job['id']} from {job['device']} completed "
                f"successfully. {pages} "
                f"{'page' if pages == 1 else 'pages'} printed."
            )
            self.last_event_type = "success"

            return job

    def empty_paper(self):
        with self.lock:
            self.paper = 0
            self._update_state()
            self.last_event = "Paper tray was emptied."
            self.last_event_type = "error"

    def refill_paper(self):
        with self.lock:
            self.paper = MAX_PAPER
            if self.status_name != "offline":
                self.status_name = "ready"
            self._update_state()
            self.last_event = f"Paper tray refilled to {MAX_PAPER} sheets."
            self.last_event_type = "success"

    def empty_toner(self):
        with self.lock:
            self.toner = 0
            self._update_state()
            self.last_event = "Toner cartridge was emptied."
            self.last_event_type = "error"

    def replace_toner(self):
        with self.lock:
            self.toner = 100
            if self.status_name != "offline":
                self.status_name = "ready"
            self._update_state()
            self.last_event = "Toner cartridge replaced."
            self.last_event_type = "success"
