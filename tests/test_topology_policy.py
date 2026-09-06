from pathlib import Path


def test_core_uses_default_deny_floor_forwarding_policy():
    topology = Path("lab/netops.clab.yml").read_text()

    assert "iptables -P FORWARD DROP" in topology
    for subnet in ("10.10.10.0/24", "10.10.20.0/24", "10.10.30.0/24"):
        assert f"iptables -A FORWARD -s {subnet} -d 10.10.254.1/32 -j ACCEPT" in topology
        assert f"iptables -A FORWARD -s {subnet} -d 10.10.40.10/32 -j ACCEPT" in topology
        assert f"iptables -A FORWARD -s {subnet} -d 10.10.40.20/32 -j ACCEPT" in topology
    assert "iptables -A FORWARD -s 10.10.254.1/32 -d 10.10.40.20/32 -j ACCEPT" in topology


def test_network_nodes_use_segmented_image():
    topology = Path("lab/netops.clab.yml").read_text()

    assert topology.count("image: netops-network:phase7") == 5


def test_dc01_services_segment_and_persistence_are_declared():
    topology = Path("lab/netops.clab.yml").read_text()
    assert 'endpoints: ["core01:eth5", "dc01:eth1"]' in topology
    assert "image: netops-dc01:phase8" in topology
    assert "privileged: false" in topology
    assert "SYS_ADMIN" in topology
    assert "${DC01_STATE_DIR}/config:/etc/samba" in topology
    assert "${DC01_STATE_DIR}/data:/var/lib/samba" in topology
    assert "ip addr add 10.10.40.10/24 dev eth1" in topology


def test_file01_shares_the_services_bridge():
    topology = Path("lab/netops.clab.yml").read_text()
    assert "image: netops-file01:phase9" in topology
    assert "ip addr add 10.10.40.20/24 dev eth1" in topology
    assert 'endpoints: ["core01:eth6", "file01:eth1"]' in topology
    assert "ip link add br-services type bridge" in topology
    assert "ip link set eth5 master br-services" in topology
    assert "ip link set eth6 master br-services" in topology


def test_server_images_support_real_ping_and_file01_restores_its_return_route():
    dc_image = Path("containers/domain-controller/Dockerfile").read_text()
    file_image = Path("containers/file-server/Dockerfile").read_text()
    file_api = Path("containers/file-server/fileserver_api.py").read_text()

    assert "iputils-ping" in dc_image
    assert "iputils-ping" in file_image
    assert '["ip", "route", "replace", "10.10.0.0/16", "via", "10.10.40.1", "dev", "eth1"]' in file_api


def test_dynamic_switch_ports_never_bridge_management_interface():
    topology = Path("lab/netops.clab.yml").read_text()
    assert topology.count("/sys/class/net/eth[1-9]*") == 3
    assert "/sys/class/net/eth*" not in topology
    assert "# DYNAMIC_WORKSTATION_NODES" in topology
    assert "# DYNAMIC_WORKSTATION_LINKS" in topology


def test_access_switches_have_per_floor_management_addresses():
    topology = Path("lab/netops.clab.yml").read_text()
    for subnet in ("10.10.10", "10.10.20", "10.10.30"):
        assert f"ip addr add {subnet}.2/24 dev br0" in topology
        assert f"ip route add 10.10.0.0/16 via {subnet}.1 dev br0" in topology


def test_six_laptops_are_reproducible_baseline_nodes():
    topology = Path("lab/netops.clab.yml").read_text()
    for number in range(1, 7):
        assert f"    ltp{number:02d}:" in topology
        assert f"DEVICE_NAME: LTP{number:02d}" in topology
    for switch, laptops in {"sw01": (1, 2), "sw02": (3, 4), "sw03": (5, 6)}.items():
        for offset, laptop in enumerate(laptops, start=6):
            assert f'endpoints: ["{switch}:eth{offset}", "ltp{laptop:02d}:eth1"]' in topology


def test_phase_eight_directory_baseline_has_role_separation():
    baseline = Path("configs/ad_baseline.json").read_text()
    assert '"Laptops,NetOpsLab"' in baseline
    for group in ("HR", "Procurement", "Helpdesk", "Remote-Users", "Monitoring-Readers"):
        assert f'"name": "{group}"' in baseline
    assert '"username": "avery.admin-adm"' in baseline
    assert '"username": "svc_monitor"' in baseline
