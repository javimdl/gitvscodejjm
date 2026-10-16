"""Carga del corpus y registros de análisis calculados, no predicciones."""

import json
from pathlib import Path
import unicodedata

from .modelos import Documento, Fragmento

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVO_DATOS = RAIZ / "datos" / "documentos.json"


def normalizar(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def cargar_documentos(archivo: Path = ARCHIVO_DATOS, *, incluir_oficiales: bool = True) -> list[Documento]:
    documentos = [Documento.model_validate(d) for d in json.loads(archivo.read_text(encoding="utf-8"))]
    oficiales = RAIZ / "datos" / "jcyl" / "documentos.json"
    if incluir_oficiales and archivo == ARCHIVO_DATOS and oficiales.exists():
        documentos.extend(Documento.model_validate(d) for d in json.loads(oficiales.read_text(encoding="utf-8")))
    ids = [d.id for d in documentos]
    referencias = [f"{d.id}:{f.id}" for d in documentos for f in d.fragmentos]
    if len(ids) != len(set(ids)) or len(referencias) != len(set(referencias)):
        raise ValueError("El corpus contiene identificadores duplicados.")
    if not documentos or not referencias:
        raise ValueError("El corpus está vacío.")
    return documentos


def agregar_analisis(documentos: list[Documento]) -> list[Documento]:
    """Completa el registro interno con cálculos sobre toda la muestra cargada.

    Así las preguntas globales no dependen de contar solo los primeros K resultados.
    """
    documentos = [d.model_copy(deep=True) for d in documentos]
    documentos = agregar_analisis_oficial(documentos)
    cuestionarios = [d for d in documentos if d.ficticio and d.tipo == "Cuestionario" and d.origen == "JCyL"]
    registro = next((d for d in documentos if d.id == "REG-01"), None)
    if not cuestionarios or registro is None:
        return documentos
    temas = sorted({f.tema for d in cuestionarios for f in d.fragmentos})
    recuentos = []
    for tema in temas:
        presentes = [d for d in cuestionarios if any(f.tema == tema for f in d.fragmentos)]
        refs = [f"{d.id}:{f.id}" for d in presentes for f in d.fragmentos if f.tema == tema]
        recuentos.append((tema, len(presentes), refs))
    recuentos.sort(key=lambda fila: (-fila[1], fila[0]))
    lineas = [f"{tema}: {n} de {len(cuestionarios)} cuestionarios ({', '.join(refs)})."
              for tema, n, refs in recuentos]
    estadisticas = ("Registro calculado: qué preguntas o conceptos se repiten más. "
                    "Se cuenta la presencia de cada tema por cuestionario, no enunciados idénticos. "
                    "Solo se incluyen cuestionarios JCyL; se excluyen otras administraciones, "
                    "plantillas, temarios y prácticos. " + " ".join(lineas))
    practicos = [f"{d.id}:{f.id} ({f.tema}): {f.texto}"
                 for d in documentos if d.ficticio and d.tipo == "Práctico" for f in d.fragmentos]
    guia = [f"{d.id}:{f.id}: {f.texto}"
            for d in documentos if d.ficticio and d.tipo == "Temario" for f in d.fragmentos]
    nuevos = [
        Fragmento(id="analisis-repeticion", ubicacion="Análisis calculado del corpus · recurrencia",
                  tema="Análisis histórico", texto=estadisticas),
        Fragmento(id="analisis-prioridades", ubicacion="Análisis calculado del corpus · prioridades",
                  tema="Prioridades de estudio", texto=(
                      "Cuáles son las más probables en función de las anteriores: no es posible "
                      "calcular probabilidades fiables ni predecir preguntas con esta pequeña muestra. "
                      "Para priorizar el estudio se combina recurrencia y aplicación práctica. "
                      + estadisticas + " Aplicación en los prácticos: " + " ".join(practicos))),
        Fragmento(id="analisis-esenciales", ubicacion="Síntesis de la guía de estudio · bases imprescindibles",
                  tema="Conocimientos esenciales", texto=(
                      "Qué no debo no saber: conocimientos imprescindibles para comenzar el repaso. "
                      "Síntesis de las bases presentes en la guía didáctica, sin sustituir el temario oficial. "
                      + " ".join(guia))),
    ]
    ids_nuevos = {f.id for f in nuevos}
    registro.fragmentos = [f for f in registro.fragmentos if f.id not in ids_nuevos] + nuevos
    return documentos


def agregar_analisis_oficial(documentos: list[Documento]) -> list[Documento]:
    """Cuenta temas por examen, separando preguntas de teoría y casos prácticos.

    Las variantes del mismo grupo no cuentan como exámenes independientes.
    Los temas son etiquetas heurísticas, no preguntas literalmente repetidas.
    """
    oficiales = [d for d in documentos if not d.ficticio and d.origen == "JCyL"]
    if not oficiales:
        return documentos
    grupos: dict[str, dict[str, str]] = {}
    preguntas = set()
    for d in oficiales:
        for f in d.fragmentos:
            if d.tipo != "Cuestionario" or f.clase != "pregunta":
                continue
            grupo = d.grupo_examen or d.id
            preguntas.add((grupo, f.id))
            temas = grupos.setdefault(grupo, {})
            for tema in f.temas:
                temas.setdefault(tema, f"{d.id}:{f.id}")
    temas = sorted({t for g in grupos.values() for t in g})
    filas = sorted([(t, [g[t] for g in grupos.values() if t in g]) for t in temas],
                   key=lambda fila: (-len(fila[1]), fila[0]))
    base = (f"Análisis local de {len(oficiales)} PDF oficiales de JCyL. "
            f"Se han segmentado {len(preguntas)} fragmentos de preguntas teóricas en {len(grupos)} grupos de examen. "
            "Se cuenta presencia de temas por grupo, no preguntas idénticas ni probabilidades. "
            "Las etiquetas se detectan por palabras clave y son orientativas. "
            "Se excluyen instrucciones, supuestos, plantillas y cuestionarios sin segmentación de test. "
            "No es el histórico completo. Los turnos libre y promoción interna se incluyen juntos; "
            "no se deben extrapolar estas frecuencias a un turno concreto. ")
    estadisticas = base + " ".join(
        f"{tema}: {len(refs)} de {len(grupos)} grupos ({', '.join(refs)})." for tema, refs in filas)
    practicos = [f"{d.id}:{f.id} ({', '.join(f.temas) or 'sin etiqueta'})"
                 for d in oficiales for f in d.fragmentos if f.clase == "practico"]
    # Seleccionar un fragmento por tema evita resúmenes enormes y conserva trazabilidad.
    guia = {}
    for d in sorted(oficiales, key=lambda doc: doc.anio, reverse=True):
        if d.tipo == "Temario":
            for f in d.fragmentos:
                for tema in f.temas:
                    guia.setdefault(tema, f"{d.id}:{f.id}")
    fragmentos = [
        Fragmento(id="c2", ubicacion="Cobertura del corpus oficial local", tema="Cobertura",
                  texto=base + "No consta el contenido de futuros exámenes. Los anteriores no permiten conocerlo."),
        Fragmento(id="analisis-repeticion", ubicacion="Cálculo local sobre los PDF oficiales", tema="Análisis histórico",
                  texto="Qué preguntas y temas se repiten más: " + estadisticas),
        Fragmento(id="analisis-prioridades", ubicacion="Orientación de estudio basada en la muestra oficial",
                  tema="Prioridades de estudio", texto=(
                      "Cuáles son las más probables en función de las anteriores: no hay probabilidades fiables. "
                      "Se pueden priorizar temas por presencia y aplicación práctica. " + estadisticas
                      + " Ejemplos de aplicación práctica: " + "; ".join(practicos[:6]))),
        Fragmento(id="analisis-esenciales", ubicacion="Referencias al programa oficial", tema="Conocimientos esenciales",
                  texto=("Qué no debo no saber: repasar las bases del programa oficial aplicable al turno y convocatoria. "
                         "Esta selección orientativa no sustituye el programa completo: "
                         + "; ".join(f"{tema} ({ref})" for tema, ref in guia.items()))),
    ]
    registro = Documento(id="REG-02", titulo="Análisis local del corpus oficial JCyL", tipo="Registro",
                         anio=max(d.anio for d in oficiales), origen="Cauce", procedencia="Cálculo local; no publicado por la Junta",
                         temas=["Análisis histórico", "Prioridades", "Cobertura"],
                         alcance="Síntesis calculada con referencias a los PDF oficiales; etiquetas orientativas.",
                         ficticio=False, fragmentos=fragmentos)
    return [d for d in documentos if d.id != registro.id] + [registro]
