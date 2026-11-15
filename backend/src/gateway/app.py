from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.pipeline import router as chat_router
from .core.providers import Provider
from .features.cache.api import router as cache_router
from .features.compression.api import router as compression_router
from .features.insights.api import router as insights_router
from .features.routing.api import router as routing_router

app = FastAPI(title="IML Token Optimiser", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health():
    settings = get_settings()
    live = Provider(settings).is_live()
    return {
        "ok": True,
        "mode": "live" if live else "demo",
        "configured_mode": settings.mode,
        "live_ready": live,
        "cheap_model": settings.cheap_model,
        "strong_model": settings.strong_model,
        "message": "Ready for local use." if live else "Running in demo mode with authored fixtures and local utilities.",
    }


app.include_router(compression_router)
app.include_router(routing_router)
app.include_router(cache_router)
app.include_router(insights_router)
app.include_router(chat_router)
