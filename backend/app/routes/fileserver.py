from fastapi import APIRouter, Request

from backend.app.models import FileAccessCheckRequest, FileServerFaultRequest, FileShareMembershipRequest


router = APIRouter(prefix="/api/fileserver", tags=["file-server"])


@router.get("")
async def fileserver(request: Request):
    return await request.app.state.fileserver_service.overview()


@router.get("/status")
async def fileserver_status(request: Request):
    return await request.app.state.fileserver_service.overview()


@router.get("/shares")
async def shares(request: Request):
    return {"shares": await request.app.state.fileserver_service.shares()}


@router.get("/shares/{share_name}")
async def share(share_name: str, request: Request):
    return await request.app.state.fileserver_service.share(share_name)


@router.get("/shares/{share_name}/access")
async def effective_share_access(share_name: str, request: Request):
    return await request.app.state.fileserver_service.effective_access(share_name)


@router.get("/users/{username}/access")
async def effective_user_access(username: str, request: Request):
    return await request.app.state.fileserver_service.user_access(username)


@router.post("/shares/{share_name}/memberships")
async def change_share_membership(
    share_name: str, payload: FileShareMembershipRequest, request: Request
):
    return await request.app.state.fileserver_service.membership_action(
        share_name, payload
    )


@router.post("/access-check")
async def access_check(payload: FileAccessCheckRequest, request: Request):
    return await request.app.state.fileserver_service.access_check(payload)


@router.post("/faults/{action}")
async def inject_fault(action: str, payload: FileServerFaultRequest, request: Request):
    return await request.app.state.fileserver_service.fault(action, payload.share)
