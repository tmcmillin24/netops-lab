import unittest

from containers.common.inventory import Inventory
from containers.printer.printer_service import (
    INITIAL_TONER,
    MAX_PAPER,
    PrinterConfig,
    PrinterOperationError,
    PrinterState,
    get_level,
    get_toner_usage,
)


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def randint(self, minimum, maximum):
        assert (minimum, maximum) == (1, 15)
        return self.value


class PrinterServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = Inventory.load("configs/inventory.json")

    def make_printer(self, name="PRNT01", random_pages=7):
        return PrinterState(
            PrinterConfig.from_inventory(self.inventory, name),
            rng=FixedRandom(random_pages),
        )

    def test_initial_state(self):
        status = self.make_printer().public_status()
        self.assertEqual((MAX_PAPER, INITIAL_TONER, "ready"), (status["paper"], status["toner"], status["status"]))

    def test_warning_thresholds(self):
        expected = {100: "normal", 76: "normal", 75: "notice", 51: "notice", 50: "low", 26: "low", 25: "very low", 1: "very low", 0: "empty"}
        for value, level in expected.items():
            self.assertEqual(level, get_level(value))

    def test_toner_usage_bands(self):
        for pages, usage in ((1, 1), (5, 1), (6, 2), (10, 2), (11, 3), (15, 3)):
            self.assertEqual(usage, get_toner_usage(pages))

    def test_random_job_range_and_source_identity(self):
        for pages in range(1, 16):
            printer = self.make_printer(random_pages=pages)
            job = printer.add_job("ws01")
            self.assertEqual((pages, "WS01"), (job["pages"], job["device"]))

    def test_successful_print_consumes_resources(self):
        printer = self.make_printer()
        printer.add_job("WS02", pages=6)
        completed = printer.complete_next_job()
        status = printer.public_status()
        self.assertEqual("WS02", completed["device"])
        self.assertEqual((169, 80, 0), (status["paper"], status["toner"], status["queue"]))

    def test_offline_rejects_new_job(self):
        printer = self.make_printer()
        printer.set_offline()
        with self.assertRaisesRegex(PrinterOperationError, "offline"):
            printer.add_job("WS01")
        self.assertEqual(0, printer.public_status()["queue"])

    def test_invalid_source_is_rejected(self):
        with self.assertRaisesRegex(PrinterOperationError, "not allowed"):
            self.make_printer().add_job("WS04")
        with self.assertRaisesRegex(PrinterOperationError, "hostname"):
            self.make_printer().add_job(None)

    def test_invalid_page_count_is_rejected(self):
        for pages in (0, 16, True, "4"):
            with self.assertRaisesRegex(PrinterOperationError, "1 to 15"):
                self.make_printer().add_job("WS01", pages=pages)

    def test_failed_job_remains_and_retries_after_paper_refill(self):
        printer = self.make_printer()
        printer.paper = 5
        printer.add_job("WS01", pages=6)
        with self.assertRaisesRegex(PrinterOperationError, "requires"):
            printer.complete_next_job()
        failed = printer.public_status()
        self.assertEqual((1, "failed", "attention"), (failed["queue"], failed["jobs"][0]["status"], failed["status"]))
        printer.refill_paper()
        printer.complete_next_job()
        self.assertEqual(0, printer.public_status()["queue"])

    def test_failed_job_retries_after_toner_replacement(self):
        printer = self.make_printer()
        printer.toner = 1
        printer.add_job("WS03", pages=15)
        with self.assertRaisesRegex(PrinterOperationError, "toner"):
            printer.complete_next_job()
        self.assertEqual("failed", printer.public_status()["jobs"][0]["status"])
        printer.replace_toner()
        printer.complete_next_job()
        self.assertEqual(97, printer.public_status()["toner"])

    def test_all_printers_derive_distinct_identity_and_sources(self):
        expected = {"PRNT01": "WS01", "PRNT02": "WS04", "PRNT03": "WS07"}
        for printer_name, source in expected.items():
            printer = self.make_printer(printer_name)
            self.assertEqual(printer_name, printer.public_status()["name"])
            printer.add_job(source, pages=1)


if __name__ == "__main__":
    unittest.main()
