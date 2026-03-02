"""RedlineAI - FastAPI Application Entry Point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.comparison import router as comparison_router
from app.api.export import router as export_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Intelligent Document Comparison & Risk Analysis Platform",
)

# CORS middleware — allows the production Vercel frontend and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://contract-redliner-app.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
app.include_router(comparison_router, prefix="/api/comparison", tags=["comparison"])
app.include_router(export_router, prefix="/api/export", tags=["export"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": settings.app_version}
