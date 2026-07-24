from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError

_STATUS_BY_EXCEPTION = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, http_status in _STATUS_BY_EXCEPTION.items():

        def make_handler(status_code: int):
            async def handler(request: Request, exc: Exception) -> JSONResponse:
                return JSONResponse(status_code=status_code, content={"detail": str(exc)})

            return handler

        app.add_exception_handler(exc_type, make_handler(http_status))
