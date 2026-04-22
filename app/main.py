from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.utils.audit import create_table_if_not_exists
from app.api import query

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_table_if_not_exists()
    yield

app = FastAPI(
    title=settings.app_name,
    description="Privacy-First AI Database Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(query.router, tags=["Query"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}

@app.get("/")
async def root():
    return {"message": "QueryGuard API is running"}
