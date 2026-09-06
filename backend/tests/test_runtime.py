import subprocess
from unittest.mock import patch

import pytest

from backend.app.errors import LabServiceError
from backend.app.services.runtime import DockerRuntime


def test_ping_uses_fixed_argument_list_without_shell():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="64 bytes from 10.10.10.21: time=0.123 ms", stderr=""
    )
    source = {"id": "ws01", "hostname": "WS01", "ip_address": "10.10.10.11"}
    destination = {"id": "prnt01", "hostname": "PRNT01", "ip_address": "10.10.10.21"}

    with patch("backend.app.services.runtime.subprocess.run", return_value=completed) as run:
        result = DockerRuntime().ping(source, destination)

    assert result["success"] is True
    assert result["latency_ms"] == 0.123
    assert run.call_args.args[0] == [
        "docker", "exec", "clab-netops-ws01", "ping", "-I", "10.10.10.11", "-c", "1", "-W", "1", "10.10.10.21"
    ]
    assert "shell" not in run.call_args.kwargs


def test_known_floor_device_ping_targets_file01_office_address():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="64 bytes from 10.10.40.20: time=0.210 ms", stderr=""
    )
    source = {"id": "ws04", "hostname": "WS04", "ip_address": "10.10.20.11"}
    destination = {"id": "file01", "hostname": "FILE01", "ip_address": "10.10.40.20"}

    with patch("backend.app.services.runtime.subprocess.run", return_value=completed) as run:
        result = DockerRuntime().ping(source, destination)

    assert result["success"] is True
    assert run.call_args.args[0] == [
        "docker", "exec", "clab-netops-ws04", "ping", "-I", "10.10.20.11", "-c", "1", "-W", "1", "10.10.40.20"
    ]


def test_file01_offline_ping_returns_real_failure():
    failed = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="1 packets transmitted, 0 packets received", stderr=""
    )
    source = {"id": "ws07", "hostname": "WS07", "ip_address": "10.10.30.11"}
    destination = {"id": "file01", "hostname": "FILE01", "ip_address": "10.10.40.20"}
    with patch("backend.app.services.runtime.subprocess.run", return_value=failed):
        result = DockerRuntime().ping(source, destination)
    assert result["success"] is False


def test_infrastructure_action_uses_allowlisted_interface_without_shell():
    action_completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    state_completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="0x1002\n", stderr="")
    device = {"id": "sw01", "hostname": "SW01", "type": "access_switch"}
    with patch(
        "backend.app.services.runtime.subprocess.run",
        side_effect=[action_completed, state_completed],
    ) as run:
        state = DockerRuntime().set_network_state(device, False)
    assert state["operational"] is False
    assert run.call_args_list[0].args[0] == [
        "docker", "exec", "clab-netops-sw01", "ip", "link", "set", "br0", "down"
    ]
    assert all("shell" not in call.kwargs for call in run.call_args_list)


def test_traceroute_uses_fixed_known_device_arguments():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout="traceroute to 10.10.10.21\n 1  10.10.10.21  0.1 ms\n", stderr="",
    )
    source = {"id": "ws01", "hostname": "WS01", "ip_address": "10.10.10.11"}
    destination = {"id": "prnt01", "hostname": "PRNT01", "ip_address": "10.10.10.21"}
    with patch("backend.app.services.runtime.subprocess.run", return_value=completed) as run:
        result = DockerRuntime().traceroute(source, destination)
    assert result["success"] is True
    assert run.call_args.args[0] == [
        "docker", "exec", "clab-netops-ws01", "traceroute", "-n", "-m", "8", "-w", "1", "-q", "1", "10.10.10.21"
    ]
    assert "shell" not in run.call_args.kwargs


def test_dns_uses_inventory_container_name_without_shell():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="Address: 127.0.0.11:53\nAddress: 172.20.20.14\n", stderr="",
    )
    source = {"id": "ws01", "hostname": "WS01"}
    destination = {"id": "prnt01", "hostname": "PRNT01"}
    with patch("backend.app.services.runtime.subprocess.run", return_value=completed) as run:
        result = DockerRuntime().dns_lookup(source, destination)
    assert result["addresses"] == ["172.20.20.14"]
    assert run.call_args.args[0] == [
        "docker", "exec", "clab-netops-ws01", "nslookup", "clab-netops-prnt01"
    ]
    assert "shell" not in run.call_args.kwargs


def test_network_info_failure_is_structured_and_does_not_expose_stderr():
    failed = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="sensitive runtime detail",
    )
    device = {"id": "ws01", "hostname": "WS01"}
    with patch("backend.app.services.runtime.subprocess.run", return_value=failed):
        with pytest.raises(LabServiceError) as captured:
            DockerRuntime().network_info(device)
    assert captured.value.code == "diagnostic_failed"
    assert "sensitive runtime detail" not in captured.value.message


def test_directory_command_uses_fixed_dc01_argument_list_without_shell():
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
    with patch("backend.app.services.runtime.subprocess.run", return_value=completed) as run:
        output = DockerRuntime().dc_command(["samba-tool", "user", "show", "jordan.lee"])
    assert output == "ok"
    assert run.call_args.args[0] == [
        "docker", "exec", "clab-netops-dc01", "samba-tool", "user", "show", "jordan.lee"
    ]
    assert "shell" not in run.call_args.kwargs
