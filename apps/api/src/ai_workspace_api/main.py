from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from ai_workspace_api import __version__
from ai_workspace_api.core.config import get_settings
from ai_workspace_api.core.errors import install_error_handlers
from ai_workspace_api.core.logging import configure_logging
from ai_workspace_api.core.telemetry import RequestIdMiddleware, install_metrics
from ai_workspace_api.infrastructure.rate_limit import limiter
from ai_workspace_api.modules.auth.router import router as auth_router
from ai_workspace_api.modules.chat.router import router as chat_router
from ai_workspace_api.modules.docs.router import router as docs_router
from ai_workspace_api.modules.health.router import router as health_router
from ai_workspace_api.modules.indexing.router import router as indexing_router
from ai_workspace_api.modules.pull_requests.router import router as pull_request_router
from ai_workspace_api.modules.realtime.router import router as realtime_router
from ai_workspace_api.modules.repositories.router import router as repositories_router
from ai_workspace_api.modules.search.router import router as search_router
from ai_workspace_api.modules.tasks.router import router as tasks_router
from ai_workspace_api.modules.users.router import router as users_router

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="AI Software Engineering Workspace API",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/v1/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-Request-Id"],
)

install_error_handlers(app)
install_metrics(app)

api_prefix = "/api/v1"
app.include_router(health_router)
app.include_router(auth_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(repositories_router, prefix=api_prefix)
app.include_router(indexing_router, prefix=api_prefix)
app.include_router(search_router, prefix=api_prefix)
app.include_router(chat_router, prefix=api_prefix)
app.include_router(pull_request_router, prefix=api_prefix)
app.include_router(tasks_router, prefix=api_prefix)
app.include_router(docs_router, prefix=api_prefix)
app.include_router(realtime_router)
