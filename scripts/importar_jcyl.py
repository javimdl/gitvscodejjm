"""Uso: uv run python scripts/importar_jcyl.py"""

import json

from cauce_oposiciones.ingesta_jcyl import ImportadorJcyl


if __name__ == "__main__":
    informe = ImportadorJcyl().ejecutar()
    print(json.dumps({k: v for k, v in informe.items() if k != "incidencias"}, ensure_ascii=False, indent=2))
    print(f"Incidencias registradas: {len(informe['incidencias'])}")
