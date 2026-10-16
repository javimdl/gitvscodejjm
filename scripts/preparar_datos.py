"""Copia el corpus de la maqueta a JSON; no ejecuta el JavaScript del HTML.

Uso: uv run python scripts/preparar_datos.py
La ejecución explícita regenera datos/documentos.json desde maquetas.html.
"""

import ast
import json
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[1]


def preparar() -> Path:
    html = (RAIZ / "maquetas.html").read_text(encoding="utf-8")
    literal = html.split("const docs = ", 1)[1].split(";\n", 1)[0]
    # La maqueta contiene un array literal, con claves JS sin comillas.
    literal = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r"\1'\2':", literal)
    originales = ast.literal_eval(literal)
    documentos = []
    for doc in originales:
        documentos.append({
            "id": doc["id"], "titulo": doc["title"], "tipo": doc["type"],
            "anio": int(doc["year"]), "origen": doc["origin"],
            "procedencia": doc["originLabel"], "temas": doc["topics"],
            "alcance": doc["scope"], "ficticio": True,
            "fragmentos": [{"id": f["id"], "ubicacion": f["location"],
                            "tema": f["tag"], "texto": f["text"]}
                           for f in doc["fragments"]],
        })
    destino = RAIZ / "datos" / "documentos.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(documentos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino


if __name__ == "__main__":
    archivo = preparar()
    print(f"Preparados 7 registros ficticios en {archivo.relative_to(RAIZ)}")
