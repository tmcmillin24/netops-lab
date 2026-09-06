from backend.app.errors import LabServiceError


class FakeFileServerService:
    async def overview(self):
        return await self.status()

    async def status(self):
        return {"hostname": "FILE01", "status": "online", "smb_running": True, "share_count": 5}

    async def shares(self):
        return [{"name": "Public"}]

    async def share(self, name):
        if name != "Public":
            raise LabServiceError("unknown_share", "Unknown configured FILE01 share.", 404)
        return {"name": name}

    async def effective_access(self, name):
        await self.share(name)
        return {"share": {"name": name}, "groups": [{"name": "Employees", "access_level": "Read/Write", "members": ["jordan.lee"]}], "effective_users": [{"username": "jordan.lee"}], "available_users": []}

    async def user_access(self, username):
        return {"username": username, "shares": [{"name": "Public", "granted": True, "access_level": "Read/Write", "granting_groups": ["Employees"]}]}

    async def membership_action(self, name, request):
        await self.share(name)
        if request.group != "Employees":
            raise LabServiceError("group_not_authorized_for_share", "Group is not allowed.", 422)
        return await self.effective_access(name)

    async def access_check(self, request):
        return {"allowed": True, "username": request.username, "device": request.device, "share": request.share, "operation": request.operation}

    async def fault(self, action, share=None):
        if action not in {"offline", "online", "service-stop", "share-disable"}:
            raise LabServiceError("unknown_fileserver_action", "Unsupported FILE01 fault action.", 404)
        if share is not None:
            await self.share(share)
        return {"hostname": "FILE01", "status": "offline" if action == "offline" else "online", "smb_running": action != "service-stop", "last_event": "State updated."}

    async def remediate(self, action, share=None):
        if action not in {"online", "restart-service", "enable-share", "restore-write"}:
            raise LabServiceError("unknown_fileserver_remediation", "Unsupported remediation.", 404)
        if share is not None:
            await self.share(share)
        return {"success": True, "changed": True, "action": action, "target": share or "FILE01", "previous_state": "unhealthy", "new_state": "healthy", "message": "Recovered.", "resolved_at": "2026-09-06T00:00:00+00:00"}


def install_fake(client):
    client.app.state.fileserver_service = FakeFileServerService()


def test_fileserver_status_shares_and_access_routes(client):
    install_fake(client)
    assert client.get("/api/fileserver/status").json()["hostname"] == "FILE01"
    assert client.get("/api/fileserver/shares").json()["shares"] == [{"name": "Public"}]
    response = client.post("/api/fileserver/access-check", json={"username": "jordan.lee", "device": "WS01", "share": "Public", "operation": "read"})
    assert response.status_code == 200
    assert response.json()["allowed"] is True
    assert client.get("/api/fileserver/shares/Public/access").status_code == 200
    user_access = client.get("/api/fileserver/users/jordan.lee/access")
    assert user_access.status_code == 200
    assert user_access.json()["shares"][0]["granting_groups"] == ["Employees"]
    membership = client.post("/api/fileserver/shares/Public/memberships", json={"username": "jordan.lee", "group": "Employees", "action": "add"})
    assert membership.status_code == 200


def test_fileserver_api_rejects_paths_commands_and_unknown_actions(client):
    install_fake(client)
    path = client.post("/api/fileserver/access-check", json={"username": "jordan.lee", "device": "WS01", "share": "../../etc", "operation": "read"})
    command = client.post("/api/fileserver/access-check", json={"username": "jordan.lee", "device": "WS01", "share": "Public", "operation": "read", "command": "sh"})
    action = client.post("/api/fileserver/faults/run-command", json={})
    unrelated_group = client.post("/api/fileserver/shares/Public/memberships", json={"username": "jordan.lee", "group": "Finance", "action": "add"})
    assert path.status_code == command.status_code == 422
    assert action.status_code == 404
    assert unrelated_group.status_code == 422


def test_fileserver_remediation_routes_are_constrained(client):
    install_fake(client)
    assert client.post("/api/fileserver/actions/online").json()["action"] == "online"
    assert client.post("/api/fileserver/actions/restart-service").json()["action"] == "restart-service"
    assert client.post("/api/fileserver/shares/Public/enable").status_code == 200
    assert client.post("/api/fileserver/shares/Public/restore-write").status_code == 200
    assert client.post("/api/fileserver/shares/Unknown/enable").status_code == 404
    assert client.post("/api/fileserver/actions/run-command").status_code in {404, 405}


def test_fileserver_fault_routes_support_only_known_server_and_share_actions(client):
    install_fake(client)
    assert client.post("/api/fileserver/faults/offline", json={}).status_code == 200
    assert client.post("/api/fileserver/faults/online", json={}).status_code == 200
    assert client.post("/api/fileserver/faults/service-stop", json={}).status_code == 200
    assert client.post("/api/fileserver/faults/share-disable", json={"share": "Public"}).status_code == 200
    assert client.post("/api/fileserver/faults/share-disable", json={"share": "Unknown"}).status_code == 404
    assert client.post("/api/fileserver/faults/run-command", json={}).status_code == 404
