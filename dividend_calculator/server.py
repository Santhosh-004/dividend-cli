"""FastAPI application for the Dividend CLI web UI.

Serves the REST API and (in production) the built SvelteKit static files.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

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

# Serve the pre-built SvelteKit frontend
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

def _resolve_frontend_path(root: Path, relative_path: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved / relative_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    return candidate


def _missing_frontend_response() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Dividend CLI UI Not Built</title>
    <style>
      body { font-family: sans-serif; margin: 2rem; line-height: 1.5; }
      code { background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>Frontend build not found</h1>
    <p>The web UI assets are missing.</p>
    <p>Start the app with <code>dividend-cli serve</code> or build the frontend from <code>frontend/</code>.</p>
  </body>
</html>
        """.strip(),
        status_code=503,
    )


def _serve_frontend_asset(relative_path: str, *, media_type: str | None = None) -> FileResponse:
    if not _FRONTEND_DIST.exists():
        raise HTTPException(status_code=503, detail="Frontend build not found")
    asset = _resolve_frontend_path(_FRONTEND_DIST, relative_path)
    if not asset.is_file():
        raise HTTPException(status_code=404, detail=f"{relative_path} not found")
    return FileResponse(str(asset), media_type=media_type)


@app.get("/static/{asset_path:path}", include_in_schema=False)
async def serve_static_asset(asset_path: str):
    return _serve_frontend_asset(asset_path)


@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon():
    return _serve_frontend_asset("favicon.svg", media_type="image/svg+xml")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    if not _FRONTEND_DIST.exists():
        return _missing_frontend_response()

    request_path = full_path.strip("/")
    if request_path:
        candidate = _resolve_frontend_path(_FRONTEND_DIST, request_path)
        if candidate.is_file():
            return FileResponse(str(candidate))
        if candidate.suffix:
            raise HTTPException(status_code=404, detail="Asset not found")

    index = _FRONTEND_DIST / "index.html"
    if not index.exists():
        return _missing_frontend_response()
    return FileResponse(str(index))
