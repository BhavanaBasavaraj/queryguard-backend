from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Privacy-First AI Database Gateway",
    version="1.0.0"
)

# CORS - allows frontend (React) to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name
    }

@app.get("/")
async def root():
    return {"message": "QueryGuard API is running"}
