from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from backend.app.errors import BackendError
from backend.app.routes import connectivity, devices, health, lab, printers, workstations
from backend.app.services.lab import LabService
from backend.app.services.runtime import DockerRuntime
from containers.common.inventory import Inventory

INVENTORY_PATH = Path(__file__).resolve().parents[2] / "configs/inventory.json"
LOCAL_FRONTEND_ORIGINS = ["http://127.0.0.1:8090", "http://localhost:8090"]


def create_app(lab_service=None):
    app = FastAPI(
        title="NetOps Lab API",
        version="0.4.0",
        description="Safe centralized API for the local NetOps Lab.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_FRONTEND_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.lab_service = lab_service or LabService(
        Inventory.load(INVENTORY_PATH),
        DockerRuntime(),
    )

    @app.exception_handler(BackendError)
    async def backend_error_handler(request: Request, error: BackendError):
        content = {"error": {"code": error.code, "message": error.message}}
        if error.details is not None:
            content["error"]["details"] = error.details
        return JSONResponse(status_code=error.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": error.errors(),
                }
            },
        )

    app.include_router(health.router)
    app.include_router(lab.router)
    app.include_router(devices.router)
    app.include_router(printers.router)
    app.include_router(workstations.router)
    app.include_router(connectivity.router)
    return app


app = create_app()
