"""FastAPI Main Application Entrypoint for ResQtech Backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings, API_VERSION, CORS_ORIGINS
from backend.app.api.endpoints import router as api_router

app = FastAPI(
    title=f"{settings.APP_NAME} Early Warning & Landslide Monitoring API",
    description=(
        "AI-Based Early Warning and Landslide Risk Monitoring System "
        "for North-Eastern Region (NER) of India.\n\n"
        "Provides offline intelligence for Phase 1–7 static susceptibility, "
        "dynamic environmental triggering pressure, and fused operational risk. "
        "Serves standards-compliant GeoJSON layers and demo what-if simulation capabilities for React + Leaflet frontend."
    ),
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration for Phase 9 React frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["Health & Status"])
def root():
    """Root entrypoint returning project metadata and status."""
    return {
        "project": settings.APP_NAME,
        "region": "North-Eastern Region (NER) India",
        "status": "Phase 8 - Backend Foundation Operational & Production Ready",
        "api_version": API_VERSION,
        "offline_mode": True,
        "is_live": False,
        "swagger_docs": "/docs",
        "redoc_docs": "/redoc",
        "health_check": "/health",
        "api_v1_prefix": "/api/v1",
    }


@app.get("/health", tags=["Health & Status"])
def health_check():
    """Top-level health check endpoint."""
    return {
        "status": "ok",
        "service": "ResQtech Early Warning API",
        "phase": "Phase 8 - Production Ready",
        "api_version": API_VERSION,
        "offline_mode": True,
    }
