import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import dbsync
from .db import DB_PATH, init_db
from .routers import auth, molecule, saved

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    dbsync.start(DB_PATH)  # pulls the remote copy before tables are created
    init_db()
    yield
    dbsync.stop(DB_PATH)


app = FastAPI(title="IUPAC Structure Viewer", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(molecule.router)
app.include_router(auth.router)
app.include_router(saved.router)


@app.get("/api/health")
def health():
    return {"ok": True}


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
