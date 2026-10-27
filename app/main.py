import uuid
import re
import logging
from contextvars import ContextVar
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.utils.audit import create_table_if_not_exists
from app.api import query
from app.core.exceptions import QueryGuardException

# ContextVar for request-scoped request_id
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

class RequestIDLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get("")
        return True

# Configure logger with request_id filter
logger = logging.getLogger("queryguard")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [request_id=%(request_id)s] %(message)s"))
handler.addFilter(RequestIDLogFilter())
if not logger.handlers:
    logger.addHandler(handler)

app = FastAPI(
    title=settings.app_name,
    description="Privacy-First AI Database Gateway",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_REQUEST_ID_REGEX = re.compile(r'^[a-zA-Z0-9-]{1,64}$')

@app.middleware("http")
async def request_correlation_middleware(request: Request, call_next):
    inbound_id = request.headers.get("X-Request-ID")
    if inbound_id and VALID_REQUEST_ID_REGEX.match(inbound_id):
        req_id = inbound_id
    else:
        req_id = str(uuid.uuid4())

    request.state.request_id = req_id
    token = request_id_ctx.set(req_id)
    try:
        logger.info(f"Incoming request {request.method} {request.url.path}")
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_ctx.reset(token)

@app.exception_handler(QueryGuardException)
async def queryguard_exception_handler(request: Request, exc: QueryGuardException):
    req_id = getattr(request.state, "request_id", None) or request_id_ctx.get("")
    logger.error(f"QueryGuardException ({exc.code}): {exc.message}")
    content = {
        "code": exc.code,
        "message": exc.message,
        "request_id": req_id
    }
    response = JSONResponse(status_code=exc.status_code, content=content)
    response.headers["X-Request-ID"] = req_id
    return response

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", None) or request_id_ctx.get("")
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    content = {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred",
        "request_id": req_id
    }
    response = JSONResponse(status_code=500, content=content)
    response.headers["X-Request-ID"] = req_id
    return response



@app.on_event("startup")
async def startup_event():
    create_table_if_not_exists()

# Register routers
app.include_router(query.router, tags=["Query"])

class HealthResponse(BaseModel):
    status: str = Field(..., description="System health status", example="healthy")
    app: str = Field(..., description="Application name", example="QueryGuard")

class RootResponse(BaseModel):
    message: str = Field(..., description="API welcome message", example="QueryGuard API is running")

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check Endpoint",
    description="Returns service health status and application identifier."
)
async def health_check():
    return {"status": "healthy", "app": settings.app_name}

@app.get(
    "/",
    response_model=RootResponse,
    summary="Root API Endpoint",
    description="Returns API status confirmation."
)
async def root():
    return {"message": "QueryGuard API is running"}

@app.get("/test-unhandled-error", include_in_schema=False)
async def test_unhandled_error():
    raise RuntimeError("Simulated unhandled database driver failure")


