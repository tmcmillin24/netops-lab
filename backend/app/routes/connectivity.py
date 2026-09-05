from fastapi import APIRouter, Request

from backend.app.models import DiagnosticRequest, PingRequest

router = APIRouter(prefix="/api/connectivity", tags=["connectivity"])


@router.post("/ping")
async def ping(ping_request: PingRequest, request: Request):
    return await request.app.state.lab_service.ping(ping_request)


@router.post("/diagnostic")
async def diagnostic(diagnostic_request: DiagnosticRequest, request: Request):
    return await request.app.state.lab_service.diagnostic(diagnostic_request)


@router.get("/network-info/{hostname}")
async def network_info(hostname: str, request: Request):
    return await request.app.state.lab_service.network_info(hostname)


@router.get("/events")
async def recent_events(request: Request):
    return {"events": request.app.state.lab_service.events[:50]}
