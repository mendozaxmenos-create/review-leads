from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth_gate import (
    dashboard_token_ok,
    locked_dashboard_html,
    path_needs_dashboard_token,
)
from app.config import settings
from app.db.store import get_store
from app.routers import admin, campaigns, demo, geocode, history, outreach, projects, search, twilio_webhooks

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store().init()
    yield


app = FastAPI(
    title="Review Leads",
    description="Busca reseñas de Google en una zona y clasifica leads potenciales con IA",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def dashboard_access_middleware(request: Request, call_next):
    """Protege /campaign, /admin y sus APIs si hay DASHBOARD_ACCESS_TOKEN. /demo queda abierto."""
    if path_needs_dashboard_token(request.url.path) and not dashboard_token_ok(request):
        if request.url.path in ("/campaign", "/admin"):
            return locked_dashboard_html()
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Dashboard protegido. Abrí /campaign?k=TU_TOKEN o /admin?k=TU_TOKEN",
            },
        )
    return await call_next(request)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(projects.router)
app.include_router(search.router)
app.include_router(campaigns.router)
app.include_router(demo.router)
app.include_router(outreach.router)
app.include_router(twilio_webhooks.router)
app.include_router(history.router)
app.include_router(admin.router)
app.include_router(geocode.router)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
async def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/campaign")
async def campaign_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "campaign.html")


@app.get("/demo")
async def demo_page() -> FileResponse:
    """Demo pública para leads — sin token."""
    return FileResponse(STATIC_DIR / "demo.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
