from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.services.readiness import check_readiness

router = APIRouter(tags=["health"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    settings = _settings(request)
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/health/ready")
def ready(request: Request) -> JSONResponse:
    result = check_readiness(_settings(request))
    status_code = status.HTTP_200_OK if result["status"] == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=result)

