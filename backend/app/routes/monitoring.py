from fastapi import APIRouter, Request

from backend.app.errors import BackendError


router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("")
async def monitoring(request: Request):
    try:
        account_health = await request.app.state.ad_service.account_health()
    except BackendError:
        account_health = {
            "status": "unavailable", "affected_accounts": 0,
            "affected_users": [], "status_source": "live_active_directory",
        }
    overview = await request.app.state.lab_service.overview(
        account_health=account_health
    )
    return overview["monitoring"]
