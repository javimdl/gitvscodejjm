"""Contratos JSON de la API y de la salida estructurada del modelo."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

TextoPregunta = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
TextoMensaje = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Mensaje(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: TextoMensaje


class Pregunta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pregunta: TextoPregunta
    historial: list[Mensaje] = Field(default_factory=list, max_length=20)


class Fragmento(BaseModel):
    id: str
    ubicacion: str
    tema: str
    texto: str
    temas: list[str] = Field(default_factory=list)
    clase: Literal["texto", "pregunta", "practico"] = "texto"
    pagina_inicio: int | None = None
    pagina_fin: int | None = None


class Documento(BaseModel):
    id: str
    titulo: str
    tipo: str
    anio: int
    origen: str
    procedencia: str
    temas: list[str]
    alcance: str
    ficticio: bool = True
    fragmentos: list[Fragmento]
    url: str | None = None
    url_ficha: str | None = None
    fecha_consulta: str | None = None
    sha256: str | None = None
    convocatoria: str | None = None
    turno: str | None = None
    grupo_examen: str | None = None


class ListadoDocumentos(BaseModel):
    documentos: list[Documento]
    total: int


class Fuente(BaseModel):
    referencia: str
    documento_id: str
    titulo: str
    fragmento_id: str
    ubicacion: str
    fragmento: str
    similitud: float | None = None
    ficticio: bool = True
    url: str | None = None
    url_ficha: str | None = None
    convocatoria: str | None = None
    turno: str | None = None


class Respuesta(BaseModel):
    respuesta: str
    fuentes: list[Fuente]
    no_consta: bool
    modelo_utilizado: bool


class SalidaModelo(BaseModel):
    """El modelo elige referencias; los textos de las fuentes los aporta el servidor."""

    respuesta: str
    referencias: list[str]
    no_consta: bool
