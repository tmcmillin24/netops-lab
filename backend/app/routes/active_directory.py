from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/directory", tags=["active-directory"])


@router.get("")
async def directory_overview(request: Request):
    return await request.app.state.ad_service.overview()


@router.get("/health")
async def directory_health(request: Request):
    return await request.app.state.ad_service.health()


@router.get("/account-health")
async def directory_account_health(request: Request):
    return await request.app.state.ad_service.account_health()


@router.get("/users")
async def list_users(request: Request):
    return await request.app.state.ad_service.users()


@router.get("/users/{username}")
async def get_user(username: str, request: Request):
    return await request.app.state.ad_service.get_user(username)


@router.delete("/users/{username}")
async def delete_user(username: str, request: Request):
    return await request.app.state.ad_service.delete_disabled_user(username)


@router.post("/users/{username}/actions/{action}")
async def user_action(username: str, action: str, request: Request):
    return await request.app.state.ad_service.user_action(username, action)


@router.post("/users/{username}/password-reset")
async def reset_password(username: str, request: Request):
    return await request.app.state.ad_service.reset_password(username)


@router.get("/groups")
async def list_groups(request: Request):
    return await request.app.state.ad_service.groups()


@router.post("/groups/{group_name}/members/{username}/{action}")
async def membership_action(group_name: str, username: str, action: str, request: Request):
    return await request.app.state.ad_service.membership_action(username, group_name, action)
