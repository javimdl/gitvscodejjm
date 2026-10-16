"""API de documentos y conversación con RAG de Cauce."""

from contextlib import asynccontextmanager
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from .datos import RAIZ, agregar_analisis, cargar_documentos, normalizar
from .modelos import ListadoDocumentos, Pregunta, Respuesta
from .rag import RagNoDisponible, RespuestaNoValida, ServicioRag

load_dotenv(RAIZ / ".env")
logger = logging.getLogger(__name__)


def crear_app(servicio: ServicioRag | None = None) -> FastAPI:
    rag = servicio or ServicioRag(agregar_analisis(cargar_documentos()))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            await run_in_threadpool(rag.preparar_indice)
        except (RagNoDisponible, OSError) as error:
            # Documentos y negativas futuras siguen disponibles; los errores del
            # proveedor se reportan como 503, no como falta de datos del corpus.
            logger.warning("Índice no disponible al arrancar: %s", type(error).__name__)
        try:
            yield
        finally:
            rag.cerrar()

    app = FastAPI(title="Cauce · API RAG", version="0.1.0", lifespan=lifespan)
    app.state.rag = rag

    @app.get("/api/health", tags=["Estado"])
    def health() -> dict:
        return {"status": "ok", "service": "cauce-oposiciones", "rag": {
            "indice_disponible": rag.vectores is not None,
            "indice_reutilizado": rag.desde_cache,
            "fragmentos": len(rag.fragmentos),
            "modo_oficial": rag.modo_oficial,
        }}

    @app.get("/api/documentos", response_model=ListadoDocumentos, tags=["Documentos"])
    def documentos(q: str = Query(default="", max_length=200),
                   tipo: str | None = None, anio: int | None = None,
                   origen: str | None = None, ficticio: bool | None = None) -> ListadoDocumentos:
        consulta = normalizar(q.strip())
        encontrados = [d for d in rag.documentos
            if (tipo is None or normalizar(d.tipo) == normalizar(tipo))
            and (anio is None or d.anio == anio)
            and (origen is None or normalizar(d.origen) == normalizar(origen))
            and (ficticio is None or d.ficticio == ficticio)
            and (not consulta or consulta in normalizar(" ".join([
                d.id, d.titulo, d.procedencia, *d.temas, *[f.texto for f in d.fragmentos]])))]
        return ListadoDocumentos(documentos=encontrados, total=len(encontrados))

    @app.post("/api/preguntar", response_model=Respuesta, tags=["Conversación"])
    def preguntar(peticion: Pregunta) -> Respuesta:
        try:
            return rag.responder(peticion)
        except RagNoDisponible as error:
            raise HTTPException(status_code=503, detail={
                "codigo": "rag_no_disponible", "mensaje": str(error)}) from None
        except RespuestaNoValida as error:
            raise HTTPException(status_code=502, detail={
                "codigo": "respuesta_no_valida", "mensaje": str(error)}) from None

    @app.get("/api/maquetas", response_class=FileResponse, include_in_schema=False)
    def maquetas() -> FileResponse:
        return FileResponse(RAIZ / "maquetas.html", media_type="text/html")

    return app


app = crear_app()
