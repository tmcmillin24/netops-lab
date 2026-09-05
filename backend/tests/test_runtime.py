import subprocess
from unittest.mock import patch

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
