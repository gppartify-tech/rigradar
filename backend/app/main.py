"""FastAPI application entry point.

Run locally:   uvicorn app.main:app --reload
API docs:      http://localhost:8000/docs
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import admin, auth, builds, catalog, chat, marketplace, notifications, users, wishlist
from app.services.uploads import upload_root

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    description=(
        "Price comparison for PC parts in Jordan (iGeek, CompuJordan, Oriental Store), "
        "price-drop alerts, an AI build assistant and a used-parts marketplace."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, users, catalog, wishlist, notifications, marketplace, builds, chat, admin):
    app.include_router(module.router)

# User uploads (marketplace photos, avatars). In production nginx can serve this folder directly.
app.mount("/uploads", StaticFiles(directory=upload_root()), name="uploads")


@app.get("/api/health", tags=["meta"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
