import json
import os
from pathlib import Path


DEFAULT_CONTAINER_PATH = Path("/config/inventory.json")
DEFAULT_LOCAL_PATH = Path(__file__).resolve().parents[2] / "configs/inventory.json"


class InventoryError(ValueError):
    """Raised when device inventory is missing or inconsistent."""


class Inventory:

    def __init__(self, data):
        self.data = data
        self.devices = {
            device["hostname"].upper(): device
            for device in data["devices"]
        }

    @classmethod
    def load(cls, path=None, include_extensions=True):
        configured_path = path or os.getenv("INVENTORY_PATH")

        if configured_path:
            inventory_path = Path(configured_path)
        elif DEFAULT_CONTAINER_PATH.exists():
            inventory_path = DEFAULT_CONTAINER_PATH
        else:
            inventory_path = DEFAULT_LOCAL_PATH

        try:
            data = json.loads(inventory_path.read_text())
            state_extension = Path.home() / "netops-lab-state/lab_extensions.json"
            extension_path = Path(os.getenv("LAB_EXTENSIONS_PATH", state_extension if state_extension.exists() else inventory_path.with_name("lab_extensions.json")))
            if include_extensions and extension_path.exists():
                extensions = json.loads(extension_path.read_text())
                dynamic_workstations = extensions.get("workstations", [])
                for workstation in dynamic_workstations:
                    workstation["dynamic"] = True
                data["devices"].extend(dynamic_workstations)
                overrides = extensions.get("assignment_overrides", {})
                for device in data["devices"]:
                    if device["hostname"] in overrides:
                        device["assigned_user"] = overrides[device["hostname"]]
        except (OSError, json.JSONDecodeError, KeyError) as error:
            raise InventoryError(
                f"Unable to load device inventory: {inventory_path}"
            ) from error

        return cls(data)

    def get_device(self, hostname, expected_type=None):
        name = hostname.upper()

        try:
            device = self.devices[name]
        except KeyError as error:
            raise InventoryError(f"Unknown device: {name}") from error

        if expected_type and device["type"] != expected_type:
            raise InventoryError(
                f"{name} is not a {expected_type} device."
            )

        return device

    def workstations_for_printer(self, printer_name):
        target = printer_name.upper()

        return {
            device["hostname"].upper()
            for device in self.devices.values()
            if device["type"] == "workstation"
            and device.get("assigned_printer", "").upper() == target
        }
