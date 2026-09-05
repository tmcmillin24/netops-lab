from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
async def list_devices(request: Request):
    return await request.app.state.lab_service.all_device_statuses()


@router.get("/{hostname}")
async def get_device(hostname: str, request: Request):
    service = request.app.state.lab_service
    return await service.status_for_hostname(hostname)


@router.post("/{hostname}/actions/{action}")
async def infrastructure_action(hostname: str, action: str, request: Request):
    return await request.app.state.lab_service.infrastructure_action(hostname, action)
