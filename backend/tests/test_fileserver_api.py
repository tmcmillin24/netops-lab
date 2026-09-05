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
        if action != "service-stop":
            raise LabServiceError("unknown_fileserver_action", "Unsupported FILE01 fault action.", 404)
        return {"hostname": "FILE01", "smb_running": False}


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
