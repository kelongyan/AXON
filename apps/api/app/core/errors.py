from fastapi import Request
from fastapi.responses import JSONResponse


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request.app.state.logger.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "Unexpected server error",
            }
        },
    )

