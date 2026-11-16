from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    config,
    datasets,
    deployments,
    evaluation,
    generation,
    playground,
    projects,
    questions,
    samples,
    seeds,
    training,
)
from app.core.config import ROOT_DIR, get_settings
from app.core.database import init_db
from app.core.errors import ApiError, install_error_handlers
from app.services.job_worker import start_job_worker

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    init_db()
    start_job_worker()
    yield


app = FastAPI(
    title="AutoLaya API",
    version="0.1.0",
    description="Local-first domain decision data loop for Laya",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_error_handlers(app)

api = APIRouter()
for module in (
    config,
    projects,
    questions,
    seeds,
    samples,
    datasets,
    generation,
    training,
    evaluation,
    playground,
    deployments,
):
    api.include_router(module.router)
app.include_router(api, prefix=settings.api_prefix)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "autolaya", "version": "0.1.0"}


frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.exists():
    assets = frontend_dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise ApiError(404, "NOT_FOUND", "Not found")
        candidate = (frontend_dist / full_path).resolve()
        if full_path and candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        index = frontend_dist / "index.html"
        if not index.exists():
            raise ApiError(404, "NOT_FOUND", "Frontend build not found")
        return FileResponse(index)
