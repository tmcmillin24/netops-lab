from fastapi import APIRouter, Request

from backend.app.models import PrintJobRequest

router = APIRouter(prefix="/api/printers", tags=["printers"])


@router.get("")
async def list_printers(request: Request):
    service = request.app.state.lab_service
    printers = [device for device in service.current_devices if device["type"] == "printer"]
    return [await service.device_status(device) for device in printers]


@router.get("/{hostname}")
async def get_printer(hostname: str, request: Request):
    service = request.app.state.lab_service
    printer = service.get_device_config(hostname, "printer")
    return await service.device_status(printer)


@router.get("/{hostname}/jobs")
async def list_jobs(hostname: str, request: Request):
    service = request.app.state.lab_service
    printer = service.get_device_config(hostname, "printer")
    status = await service.request_endpoint(printer)
    return {"hostname": printer["hostname"], "queue": status["queue"], "jobs": status["jobs"]}


@router.post("/{hostname}/jobs", status_code=201)
async def submit_job(hostname: str, job: PrintJobRequest, request: Request):
    return await request.app.state.lab_service.submit_job(hostname, job)


@router.post("/{hostname}/actions/{action}")
async def printer_action(hostname: str, action: str, request: Request):
    return await request.app.state.lab_service.printer_action(hostname, action)
