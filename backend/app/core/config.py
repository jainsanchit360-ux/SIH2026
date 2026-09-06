"""Backend core configuration module linking settings from main src.config."""
from typing import List
from src.config.settings import get_settings

API_VERSION: str = "0.1.0-prototype"
CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

settings = get_settings()
