"""FastAPI application for the Dividend CLI web UI.

Serves the REST API and (in production) the built SvelteKit static files.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import __version__
from .api.routes import router

app = FastAPI(
    title="Dividend CLI API",
    description="REST API for the Indian Stock Dividend Calculator",
    version=__version__,
)

# Allow the SvelteKit dev server to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routes under /api
app.include_router(router, prefix="/api")

# Serve the pre-built SvelteKit frontend (production mode only)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    # Serve SvelteKit's _app directory (immutable JS/CSS chunks)
    _app_dir = _FRONTEND_DIST / "_app"
    if _app_dir.exists():
        app.mount(
            "/_app",
            StaticFiles(directory=str(_app_dir)),
            name="_app",
        )

    # Serve any other top-level static files (robots.txt, favicons, etc.)
    app.mount(
        "/static",
        StaticFiles(directory=str(_FRONTEND_DIST)),
        name="static",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    async def serve_favicon():
        favicon = _FRONTEND_DIST / "favicon.svg"
        if not favicon.exists():
            raise HTTPException(status_code=404, detail="favicon.svg not found")
        return FileResponse(str(favicon), media_type="image/svg+xml")

    # Catch-all: serve index.html for all non-API routes (SvelteKit SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
