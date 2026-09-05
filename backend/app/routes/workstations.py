from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/workstations", tags=["workstations"])


@router.get("")
async def list_workstations(request: Request):
    service = request.app.state.lab_service
    workstations = [device for device in service.current_devices if device["type"] == "workstation"]
    return [await service.device_status(device) for device in workstations]


@router.get("/{hostname}")
async def get_workstation(hostname: str, request: Request):
    service = request.app.state.lab_service
    workstation = service.get_device_config(hostname, "workstation")
    return await service.device_status(workstation)


@router.post("/{hostname}/actions/{action}")
async def workstation_action(hostname: str, action: str, request: Request):
    return await request.app.state.lab_service.workstation_action(hostname, action)
