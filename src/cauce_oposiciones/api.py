"""API inicial de Cauce y acceso a la maqueta original."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="Cauce · API", version="0.1.0")


@app.get("/api/health", tags=["Estado"])
def health() -> dict[str, str]:
    """Permite verificar la conexión entre Svelte, Vite y FastAPI."""
    return {"status": "ok", "service": "cauce-oposiciones"}


@app.get("/api/maquetas", response_class=FileResponse, include_in_schema=False)
def maquetas() -> FileResponse:
    """Muestra el HTML existente sin copiarlo ni modificarlo."""
    return FileResponse(PROJECT_ROOT / "maquetas.html", media_type="text/html")
