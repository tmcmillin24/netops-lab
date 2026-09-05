import asyncio
from unittest.mock import Mock

import pytest

from backend.app.errors import LabServiceError
from backend.app.services.lab import LabService
from containers.common.inventory import Inventory


def test_access_switch_restore_is_blocked_while_core_is_offline():
    runtime = Mock()
    runtime.network_interfaces = {
        "router_firewall": ("eth1",),
        "layer3_core_switch": ("eth1", "eth2", "eth3", "eth4"),
        "access_switch": ("br0",),
    }
    runtime.inspect.return_value = {"running": True, "management_ip": "172.20.20.2"}
    runtime.network_state.return_value = {
        "interfaces": {"eth1": "down", "eth2": "down", "eth3": "down", "eth4": "down"},
        "operational": False,
    }
    service = LabService(Inventory.load("configs/inventory.json"), runtime)

    with pytest.raises(LabServiceError) as raised:
        asyncio.run(service.infrastructure_action("SW01", "restore"))

    assert raised.value.code == "upstream_unavailable"
    assert raised.value.status_code == 409
    assert "Restore CORE01 first" in raised.value.message
    runtime.set_network_state.assert_not_called()


def test_directly_offline_workstation_is_counted_as_impacted():
    service = LabService(Inventory.load("configs/inventory.json"), Mock())

    async def device_statuses():
        return [
            {
                "hostname": "WS02",
                "device_type": "workstation",
                "status": "offline",
                "dependency_status": "normal",
                "live": {"message": "WS02 is offline."},
            },
            {
                "hostname": "SW01",
                "device_type": "access_switch",
                "status": "online",
                "dependency_status": "normal",
            },
        ]

    service.all_device_statuses = device_statuses
    overview = asyncio.run(service.overview())

    assert overview["offline_devices"] == 1
    assert overview["impacted_devices"] == 1
    assert overview["impacted_device_alerts"] == [
        {"hostname": "WS02", "reason": "WS02 is offline."}
    ]
    assert overview["devices"][0]["hostname"] == "WS02"
