"""
Board Generator Studio — FastAPI backend for the web UI.
Serves REST API and (in production) static frontend.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import board as board_routes
from api.routes import config as config_routes
from api.routes import play as play_routes

app = FastAPI(
    title="Board Generator Studio API",
    description="REST API for procedural board generation and analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_routes.router, prefix="/api")
app.include_router(board_routes.router, prefix="/api")
app.include_router(play_routes.router, prefix="/api")

# Mount built frontend in production (optional). Must be last so /api takes precedence.
# When frozen (PyInstaller), app root is sys._MEIPASS; otherwise project root.
_base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
_dist = _base / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
