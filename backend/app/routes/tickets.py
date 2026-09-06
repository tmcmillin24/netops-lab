from fastapi import APIRouter, Request

from backend.app.models import TicketBatchGenerateRequest, TicketGenerateRequest, TicketResolveRequest, TicketStartRequest


router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("")
async def tickets(request: Request, status: str | None = None):
    normalized = status.lower().replace(" ", "-") if status else None
    if normalized not in {None, "open", "in-progress", "resolved"}:
        normalized = None
    return {"tickets": request.app.state.ticket_service.list(normalized)}


@router.get("/{ticket_id}")
async def ticket(ticket_id: str, request: Request):
    return request.app.state.ticket_service._public(
        request.app.state.ticket_service.get(ticket_id)
    )


@router.post("/generate", status_code=201)
async def generate(payload: TicketGenerateRequest, request: Request):
    return await request.app.state.ticket_service.generate(payload.difficulty)


@router.post("/generate-batch", status_code=201)
async def generate_batch(payload: TicketBatchGenerateRequest, request: Request):
    tickets = []
    for _ in range(payload.count):
        tickets.append(await request.app.state.ticket_service.generate(payload.difficulty))
    return {"tickets": tickets}


@router.post("/{ticket_id}/start")
async def start(ticket_id: str, payload: TicketStartRequest, request: Request):
    return await request.app.state.ticket_service.start(ticket_id, payload.technician)


@router.post("/{ticket_id}/resolve")
async def resolve(ticket_id: str, payload: TicketResolveRequest, request: Request):
    return await request.app.state.ticket_service.resolve(
        ticket_id, payload.technician, payload.resolution_notes
    )


@router.post("/{ticket_id}/verify")
async def verify(ticket_id: str, request: Request):
    return await request.app.state.ticket_service.verify(ticket_id)


@router.post("/{ticket_id}/file-connectivity")
async def file_connectivity(ticket_id: str, request: Request):
    return await request.app.state.ticket_service.file_connectivity(ticket_id)
