def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_lab_overview(client):
    response = client.get("/api/lab")
    assert response.status_code == 200
    assert response.json()["total_devices"] == 17


def test_device_inventory_and_known_lookup(client):
    inventory = client.get("/api/devices")
    device = client.get("/api/devices/WS01")
    assert inventory.status_code == 200
    assert {item["hostname"] for item in inventory.json()} == {"PRNT01", "WS01"}
    assert device.json()["status"] == "online"


def test_unknown_device_has_structured_error(client):
    response = client.get("/api/devices/WS99")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "unknown_device", "message": "Unknown current lab device: WS99"}}


def test_printer_list_status_and_jobs(client):
    printers = client.get("/api/printers")
    printer = client.get("/api/printers/PRNT01")
    jobs = client.get("/api/printers/PRNT01/jobs")
    assert printers.status_code == printer.status_code == jobs.status_code == 200
    assert printers.json()[0]["hostname"] == "PRNT01"
    assert jobs.json()["jobs"] == []


def test_printer_job_submission(client):
    response = client.post("/api/printers/PRNT01/jobs", json={"source": "WS01", "pages": 6})
    assert response.status_code == 201
    assert response.json()["jobs"][0]["device"] == "WS01"


def test_printer_operational_error_propagates(client):
    response = client.post("/api/printers/PRNT01/actions/fail")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "printer_offline"


def test_workstation_list_status_and_action(client):
    workstations = client.get("/api/workstations")
    workstation = client.get("/api/workstations/WS01")
    offline = client.post("/api/workstations/WS01/actions/offline")
    assert workstations.status_code == workstation.status_code == offline.status_code == 200
    assert workstation.json()["reachable"] is True
    assert offline.json()["status"] == "offline"


def test_known_device_ping(client):
    response = client.post("/api/connectivity/ping", json={"source": "WS01", "destination": "PRNT01"})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_unknown_ping_source_and_destination_rejected(client):
    source = client.post("/api/connectivity/ping", json={"source": "bad", "destination": "PRNT01"})
    destination = client.post("/api/connectivity/ping", json={"source": "WS01", "destination": "example.com"})
    assert source.status_code == destination.status_code == 404
    assert source.json()["error"]["code"] == "unknown_device"
    assert destination.json()["error"]["code"] == "unknown_device"


def test_arbitrary_command_field_is_rejected(client):
    response = client.post("/api/connectivity/ping", json={"source": "WS01", "destination": "PRNT01", "command": "sh -c anything"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
