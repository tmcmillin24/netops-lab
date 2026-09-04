import unittest

from containers.common.inventory import Inventory
from containers.workstation.workstation_service import WorkstationConfig, WorkstationOperationError, WorkstationState


class WorkstationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = Inventory.load("configs/inventory.json")

    def test_all_workstations_derive_identity_and_printer(self):
        for number in range(1, 10):
            name = f"WS{number:02d}"
            state = WorkstationState(WorkstationConfig.from_inventory(self.inventory, name))
            self.assertEqual(name, state.config.name)
            self.assertEqual(f"PRNT{((number - 1) // 3) + 1:02d}", state.config.printer_name)

    def test_offline_state_blocks_printing_and_is_recoverable(self):
        state = WorkstationState(WorkstationConfig.from_inventory(self.inventory, "WS01"))
        state.set_offline()
        with self.assertRaisesRegex(WorkstationOperationError, "offline"):
            state.require_online()
        self.assertEqual("offline", state.operational_status()["status"])
        state.set_online()
        state.require_online()
        self.assertEqual("online", state.operational_status()["status"])


if __name__ == "__main__":
    unittest.main()
