import unittest

from containers.common.inventory import Inventory, InventoryError


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = Inventory.load("configs/inventory.json")

    def test_inventory_has_all_phase_three_endpoints(self):
        workstations = [device for device in self.inventory.devices.values() if device["type"] == "workstation"]
        printers = [device for device in self.inventory.devices.values() if device["type"] == "printer"]
        self.assertEqual(9, len(workstations))
        self.assertEqual(3, len(printers))

    def test_printer_assignments_match_access_groups(self):
        self.assertEqual({"WS01", "WS02", "WS03"}, set(self.inventory.workstations_for_printer("PRNT01")))
        self.assertEqual({"WS04", "WS05", "WS06"}, set(self.inventory.workstations_for_printer("PRNT02")))
        self.assertEqual({"WS07", "WS08", "WS09"}, set(self.inventory.workstations_for_printer("PRNT03")))

    def test_unknown_device_is_rejected(self):
        with self.assertRaises(InventoryError):
            self.inventory.get_device("WS99")


if __name__ == "__main__":
    unittest.main()
