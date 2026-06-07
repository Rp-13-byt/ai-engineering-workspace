from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from uuid import uuid4


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        return response


def install_metrics(app: FastAPI) -> None:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
