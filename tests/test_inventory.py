import json
import unittest

from containers.common.inventory import Inventory, InventoryError


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = Inventory.load("configs/inventory.json", include_extensions=False)

    def test_inventory_has_complete_baseline(self):
        workstations = [device for device in self.inventory.devices.values() if device["type"] == "workstation"]
        printers = [device for device in self.inventory.devices.values() if device["type"] == "printer"]
        expected = {"RTR01", "CORE01", "SW01", "SW02", "SW03", "DC01", "FILE01"}
        expected.update(f"WS{i:02d}" for i in range(1, 10))
        expected.update(f"LTP{i:02d}" for i in range(1, 7))
        expected.update(f"PRNT{i:02d}" for i in range(1, 4))
        current = {
            hostname
            for hostname, device in self.inventory.devices.items()
            if device.get("phase") == "current"
        }
        self.assertEqual(expected, current)
        self.assertEqual(25, len(current))
        self.assertEqual("planned", self.inventory.devices["API01"]["phase"])
        self.assertEqual(15, len(workstations))
        self.assertEqual(3, len(printers))

    def test_access_switch_management_addresses_match_their_floors(self):
        self.assertEqual("10.10.10.2", self.inventory.devices["SW01"]["ip_address"])
        self.assertEqual("10.10.20.2", self.inventory.devices["SW02"]["ip_address"])
        self.assertEqual("10.10.30.2", self.inventory.devices["SW03"]["ip_address"])

    def test_phase_eight_domain_metadata_is_explicit(self):
        dc01 = self.inventory.devices["DC01"]
        self.assertEqual("10.10.40.10", dc01["ip_address"])
        self.assertEqual("netopslab.test", dc01["dns_domain"])
        for number in range(1, 10):
            workstation = self.inventory.devices[f"WS{number:02d}"]
            self.assertFalse(workstation["domain_joined"])
            self.assertEqual(f"WS{number:02d}$", workstation["ad_computer_object"])

    def test_phase_nine_file_server_is_on_services_network(self):
        file01 = self.inventory.devices["FILE01"]
        self.assertEqual("file_server", file01["type"])
        self.assertEqual("10.10.40.20", file01["ip_address"])
        self.assertEqual("services", file01["network"])
        self.assertEqual("CORE01", file01["connected_to"])

    def test_each_workstation_has_one_unique_active_directory_user(self):
        endpoint_names = [f"WS{number:02d}" for number in range(1, 10)]
        endpoint_names.extend(f"LTP{number:02d}" for number in range(1, 7))
        assigned_users = [self.inventory.devices[name]["assigned_user"] for name in endpoint_names]
        self.assertEqual(15, len(set(assigned_users)))
        self.assertNotIn(None, assigned_users)

        baseline = json.loads(open("configs/ad_baseline.json").read())
        active_employees = [
            user for user in baseline["users"]
            if not user.get("disabled") and user.get("account_type", "employee") == "employee"
        ]
        disabled_users = [user for user in baseline["users"] if user.get("disabled")]
        self.assertEqual(set(assigned_users), {user["username"] for user in active_employees})
        self.assertEqual(3, len(disabled_users))
        self.assertTrue(all(user["workstation"] is None for user in disabled_users))
        self.assertTrue(all(user["groups"] == ["Former-Employees"] for user in disabled_users))
        self.assertEqual(
            {"Employees", "Finance", "Operations", "Engineering", "HR", "Procurement", "Helpdesk", "Remote-Users", "IT-Admins", "Monitoring-Readers", "Former-Employees"},
            {group["name"] for group in baseline["groups"]},
        )

    def test_published_endpoint_ports_are_declared_in_inventory(self):
        expected = {"PRNT01": 8080, "WS01": 8081, "PRNT02": 8082, "PRNT03": 8083}
        actual = {
            hostname: device["host_port"]
            for hostname, device in self.inventory.devices.items()
            if "host_port" in device
        }
        self.assertEqual(expected, actual)

    def test_printer_assignments_match_access_groups(self):
        self.assertEqual({"WS01", "WS02", "WS03", "LTP01", "LTP02"}, set(self.inventory.workstations_for_printer("PRNT01")))
        self.assertEqual({"WS04", "WS05", "WS06", "LTP03", "LTP04"}, set(self.inventory.workstations_for_printer("PRNT02")))
        self.assertEqual({"WS07", "WS08", "WS09", "LTP05", "LTP06"}, set(self.inventory.workstations_for_printer("PRNT03")))

    def test_unknown_device_is_rejected(self):
        with self.assertRaises(InventoryError):
            self.inventory.get_device("WS99")

    def test_access_networks_have_unique_floor_departments(self):
        access_networks = [
            network
            for network in self.inventory.data["networks"]
            if network["id"].startswith("access_")
        ]
        self.assertEqual(["Floor 1", "Floor 2", "Floor 3"], [network["floor"] for network in access_networks])
        self.assertEqual(3, len({network["department"] for network in access_networks}))


if __name__ == "__main__":
    unittest.main()
