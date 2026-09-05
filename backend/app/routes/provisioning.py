from fastapi import APIRouter, Request

from backend.app.models import ApplyDraftRequest, EmployeeAssignmentRequest, EmployeeCreateRequest, WorkstationDraftRequest


router = APIRouter(prefix="/api/provisioning", tags=["provisioning"])


@router.get("/options")
async def options(request: Request):
    service = request.app.state.provisioning_service
    return {"floors": service.FLOORS, "suggested_hostnames": {"workstation": service.next_hostname("workstation"), "laptop": service.next_hostname("laptop")}}


@router.post("/workstations/draft")
async def draft_workstation(payload: WorkstationDraftRequest, request: Request):
    return request.app.state.provisioning_service.draft(payload)


@router.post("/workstations/apply")
async def apply_workstation(payload: ApplyDraftRequest, request: Request):
    return await request.app.state.provisioning_service.apply(payload.draft_id)


@router.get("/employees/options")
async def employee_options(request: Request):
    return await request.app.state.provisioning_service.employee_options()


@router.post("/employees")
async def create_employee(payload: EmployeeCreateRequest, request: Request):
    return await request.app.state.provisioning_service.create_employee(payload)


@router.post("/employees/{username}/unassign")
async def unassign_employee(username: str, request: Request):
    return await request.app.state.provisioning_service.unassign_employee(username)


@router.post("/employees/{username}/assign")
async def assign_employee(username: str, payload: EmployeeAssignmentRequest, request: Request):
    return await request.app.state.provisioning_service.assign_employee(username, payload.workstation)


@router.delete("/devices/{hostname}")
async def remove_device(hostname: str, request: Request):
    return await request.app.state.provisioning_service.remove_device(hostname)
