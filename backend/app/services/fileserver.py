import asyncio

from backend.app.errors import LabServiceError


class FileServerService:
    def __init__(self, lab_service, ad_service):
        self.lab_service = lab_service
        self.ad_service = ad_service

    @property
    def device(self):
        return self.lab_service.get_device_config("FILE01", "file_server")

    async def status(self):
        return await self.lab_service.request_endpoint(self.device)

    async def overview(self):
        status = await self.status()
        access_results = await asyncio.gather(*(
            self.effective_access(share["name"]) for share in status["shares"]
        ))
        access = {result["share"]["name"]: result for result in access_results}
        return {
            **status,
            "shares": [
                {
                    **share,
                    "effective_user_count": len(access[share["name"]]["effective_users"]),
                    "access_groups": access[share["name"]]["groups"],
                }
                for share in status["shares"]
            ],
        }

    async def shares(self):
        return (await self.status())["shares"]

    async def share(self, share_name):
        shares = {share["name"].lower(): share for share in await self.shares()}
        try:
            return shares[share_name.lower()]
        except KeyError as error:
            raise LabServiceError("unknown_share", "Unknown configured FILE01 share.", 404) from error

    async def effective_access(self, share_name):
        share = await self.share(share_name)
        allowed_groups = list(dict.fromkeys([*share["read_groups"], *share["write_groups"]]))
        if hasattr(self.ad_service, "command"):
            outputs = await asyncio.gather(*(
                self.ad_service.command("samba-tool", "group", "listmembers", group_name)
                for group_name in allowed_groups
            ))
            groups = {
                group_name: {
                    "name": group_name,
                    "members": sorted(
                        line.strip() for line in output.splitlines() if line.strip()
                    ),
                }
                for group_name, output in zip(allowed_groups, outputs)
            }
            users = [
                {
                    **config,
                    "enabled": not config.get("disabled", False),
                    "account_type": config.get("account_type", "employee"),
                }
                for config in self.ad_service.user_configs.values()
            ]
        else:
            users, group_results = await asyncio.gather(
                self.ad_service.users(), self.ad_service.groups()
            )
            groups = {group["name"]: group for group in group_results}
        group_details = []
        effective = {}
        for group_name in allowed_groups:
            members = groups[group_name]["members"]
            access_level = "Read/Write" if group_name in share["write_groups"] else "Read"
            group_details.append({"name": group_name, "access_level": access_level, "members": members})
            for username in members:
                current = effective.get(username)
                if current != "Read/Write":
                    effective[username] = access_level
        manageable = [
            user for user in users
            if user["enabled"] and user.get("account_type") != "service"
        ]
        user_by_name = {user["username"]: user for user in users}
        effective_users = [
            {
                "username": username,
                "display_name": user_by_name.get(username, {}).get("display_name", username),
                "access_level": access_level,
                "groups": sorted(
                    group_name for group_name in allowed_groups
                    if username in groups[group_name]["members"]
                ),
            }
            for username, access_level in sorted(effective.items())
        ]
        return {
            "share": share,
            "groups": group_details,
            "effective_users": effective_users,
            "available_users": [
                {
                    "username": user["username"],
                    "display_name": user["display_name"],
                    "role": user["role"],
                }
                for user in manageable
                if user["username"] not in effective
            ],
            "authorization_source": "live_active_directory_groups",
        }

    async def user_access(self, username):
        user = self.ad_service.known_user(username)
        shares = await self.shares()
        access_results = await asyncio.gather(*(
            self.effective_access(share["name"]) for share in shares
        ))
        user_shares = []
        for access in access_results:
            effective_user = next((
                item for item in access["effective_users"]
                if item["username"] == username
            ), None)
            granting_groups = set(effective_user["groups"] if effective_user else [])
            user_shares.append({
                "name": access["share"]["name"],
                "granted": effective_user is not None,
                "access_level": effective_user["access_level"] if effective_user else None,
                "granting_groups": sorted(granting_groups),
                "groups": [
                    {
                        "name": group["name"],
                        "access_level": group["access_level"],
                        "member": group["name"] in granting_groups,
                    }
                    for group in access["groups"]
                ],
            })
        return {
            "username": username,
            "display_name": user.get("display_name", username),
            "shares": user_shares,
            "authorization_source": "live_active_directory_groups",
        }

    async def membership_action(self, share_name, request):
        share = await self.share(share_name)
        allowed_groups = set(share["read_groups"] + share["write_groups"])
        if request.group not in allowed_groups:
            raise LabServiceError(
                "group_not_authorized_for_share",
                f"{request.group} is not an access group for {share['name']}.",
                422,
            )
        self.ad_service.known_user(request.username)
        self.ad_service.known_group(request.group)
        await self.ad_service.membership_action(
            request.username, request.group, request.action
        )
        self.lab_service.record_event(
            "FILE01",
            f"{request.username} {'added to' if request.action == 'add' else 'removed from'} {request.group} for {share['name']} access.",
            "info",
        )
        return await self.effective_access(share["name"])

    async def access_check(self, request):
        user = await self.ad_service.get_user(request.username)
        device = self.lab_service.get_device_config(request.device, "workstation")
        if user.get("workstation") != device["hostname"]:
            raise LabServiceError(
                "device_user_mismatch",
                f"{user['username']} is not assigned to {device['hostname']}.",
                409,
            )
        status = await self.status()
        share = await self.share(request.share)
        reason = None
        if not user["enabled"]:
            reason = "The directory account is disabled."
        elif status["status"] != "online":
            reason = "FILE01 is offline."
        elif not status["smb_running"]:
            reason = "The SMB service is stopped."
        elif not share["enabled"]:
            reason = f"The {share['name']} share is disabled."
        else:
            required = share["write_groups"] if request.operation == "write" else share["read_groups"]
            if not set(user["groups"]).intersection(required):
                reason = f"Access requires membership in {', '.join(required)}."
            elif request.operation == "write" and share["read_only"]:
                reason = f"The {share['name']} share is currently read-only."
        allowed = reason is None
        result = {
            "allowed": allowed,
            "result": "access_granted" if allowed else "access_denied",
            "username": user["username"],
            "display_name": user["display_name"],
            "device": device["hostname"],
            "share": share["name"],
            "operation": request.operation,
            "reason": reason or f"{request.operation.title()} access granted by group membership.",
            "authorization_source": "live_active_directory_groups",
            "transport_check": "controlled_backend_model",
        }
        self.lab_service.record_event(
            "FILE01",
            f"{user['username']} {request.operation} {share['name']}: {'granted' if allowed else 'denied'}.",
            "info" if allowed else "warning",
        )
        return result

    async def fault(self, action, share_name=None):
        allowed = {
            "offline", "online", "service-stop", "service-start",
            "share-disable", "share-enable", "read-only", "read-write",
        }
        if action not in allowed:
            raise LabServiceError("unknown_fileserver_action", "Unsupported FILE01 fault action.", 404)
        if share_name is not None:
            await self.share(share_name)
        result = await self.lab_service.request_endpoint(
            self.device, "POST", f"/faults/{action}", {"share": share_name}
        )
        self.lab_service.record_event("FILE01", result["last_event"], "warning" if action in {"offline", "service-stop", "share-disable", "read-only"} else "success")
        return result
