from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/lab", tags=["lab"])


@router.get("")
async def lab_overview(request: Request):
    return await request.app.state.lab_service.overview()
