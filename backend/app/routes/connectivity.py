from fastapi import APIRouter, Request

from backend.app.models import PingRequest

router = APIRouter(prefix="/api/connectivity", tags=["connectivity"])


@router.post("/ping")
async def ping(ping_request: PingRequest, request: Request):
    return await request.app.state.lab_service.ping(ping_request)
