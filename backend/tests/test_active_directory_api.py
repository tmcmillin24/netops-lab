def test_directory_overview_uses_live_service(client):
    response = client.get("/api/directory")
    assert response.status_code == 200
    assert response.json()["domain"] == "netopslab.test"
    assert response.json()["users"][0]["username"] == "jordan.lee"
    assert response.json()["users"][0]["workstation"] == "WS01"
    assert response.json()["password_policy"]["minimum_length"] == 10
    assert response.json()["users"][0]["account_type"] == "employee"


def test_directory_user_and_group_routes(client):
    account_health = client.get("/api/directory/account-health")
    assert account_health.status_code == 200
    assert account_health.json()["status_source"] == "live_active_directory"
    assert client.get("/api/directory/users").status_code == 200
    assert client.get("/api/directory/users/jordan.lee").status_code == 200
    assert client.get("/api/directory/groups").status_code == 200


def test_directory_account_actions_are_allowlisted(client):
    disabled = client.post("/api/directory/users/jordan.lee/actions/disable")
    invalid = client.post("/api/directory/users/jordan.lee/actions/delete")
    unknown = client.get("/api/directory/users/unknown.user")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert invalid.status_code == 404
    assert unknown.status_code == 404


def test_password_reset_and_membership_routes(client):
    reset = client.post("/api/directory/users/jordan.lee/password-reset")
    membership = client.post("/api/directory/groups/Finance/members/jordan.lee/add")
    assert reset.status_code == 200
    assert reset.json()["temporary_password"] == "temporary-value"
    assert membership.status_code == 200
