def test_provisioning_options_are_allowlisted(client):
    response = client.get("/api/provisioning/options")
    assert response.status_code == 200
    assert set(response.json()["floors"]) == {"access_01", "access_02", "access_03"}
    assert response.json()["suggested_hostnames"]["workstation"] == "WS02"
    assert response.json()["suggested_hostnames"]["laptop"] == "LTP01"


def test_workstation_draft_derives_floor_network_values(client):
    response = client.post(
        "/api/provisioning/workstations/draft",
        json={"floor": "access_02"},
    )
    assert response.status_code == 200
    assert response.json()["hostname"] == "WS02"
    assert response.json()["ip_address"] == "10.10.20.14"
    assert response.json()["switch"] == "SW02"
    assert response.json()["printer"] == "PRNT02"


def test_workstation_draft_rejects_arbitrary_floor(client):
    response = client.post(
        "/api/provisioning/workstations/draft",
        json={"floor": "internet"},
    )
    assert response.status_code == 422


def test_laptop_draft_uses_ltp_hostname(client):
    response = client.post(
        "/api/provisioning/workstations/draft",
        json={"device_type": "laptop", "floor": "access_03"},
    )
    assert response.status_code == 200
    assert response.json()["hostname"] == "LTP01"
    assert response.json()["device_type"] == "laptop"


def test_baseline_device_removal_is_blocked(client):
    response = client.delete("/api/provisioning/devices/WS01")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "protected_baseline_device"


def test_employee_can_be_explicitly_unassigned(client):
    response = client.post("/api/provisioning/employees/jordan.lee/unassign")
    assert response.status_code == 200
    assert response.json()["workstation"] == "WS01"


def test_employee_can_be_created_unassigned_in_employees_group(client):
    response = client.post(
        "/api/provisioning/employees",
        json={
            "workstation": None,
            "employee": {
                "given_name": "Taylor",
                "surname": "Morgan",
                "role": "Analyst",
                "username": "taylor.morgan",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["user"]["workstation"] is None
    assert response.json()["user"]["groups"] == ["Employees"]
    assert "left unassigned" in response.json()["message"]
