from dataclasses import dataclass
import threading


class WorkstationOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkstationConfig:
    name: str
    ip_address: str
    gateway: str
    connected_switch: str
    printer_name: str
    printer_ip: str

    @classmethod
    def from_inventory(cls, inventory, device_name):
        device = inventory.get_device(device_name, "workstation")
        printer = inventory.get_device(
            device["assigned_printer"],
            "printer"
        )
        network = next(
            network
            for network in inventory.data["networks"]
            if network["id"] == device["network"]
        )

        return cls(
            name=device["hostname"],
            ip_address=device["ip_address"],
            gateway=network["gateway"],
            connected_switch=device["connected_to"],
            printer_name=printer["hostname"],
            printer_ip=printer["ip_address"]
        )


class WorkstationState:

    def __init__(self, config):
        self.config = config
        self.online = True
        self.last_event = "Workstation initialized."
        self.last_event_type = "info"
        self.lock = threading.Lock()

    def set_offline(self):
        with self.lock:
            self.online = False
            self.last_event = f"{self.config.name} was taken offline."
            self.last_event_type = "error"

    def set_online(self):
        with self.lock:
            self.online = True
            self.last_event = f"{self.config.name} was brought online."
            self.last_event_type = "success"

    def require_online(self):
        with self.lock:
            if not self.online:
                raise WorkstationOperationError(
                    f"PRINT FAILED: {self.config.name} is offline."
                )

    def record_event(self, message, event_type):
        with self.lock:
            self.last_event = message
            self.last_event_type = event_type

    def operational_status(self):
        with self.lock:
            return {
                "status": "online" if self.online else "offline",
                "last_event": self.last_event,
                "last_event_type": self.last_event_type
            }
