from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.utils.audit import create_table_if_not_exists

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

@app.on_event("startup")
async def startup_event():
    create_table_if_not_exists()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name
    }

@app.get("/")
async def root():
    return {"message": "QueryGuard API is running"}
