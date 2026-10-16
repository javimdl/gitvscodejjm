# Cauce · Aula de oposiciones TIC

Aplicación local para preparar la oposición de Técnico/a de Gestión Informática de Castilla y León. Incluye un asistente de estudio con respuestas fundamentadas, una biblioteca documental y sesiones de repaso.

## Datos

El catálogo reúne 16 PDF oficiales descargados del portal de Empleo Público de la Junta de Castilla y León, correspondientes a cinco convocatorias. También conserva por separado los ejemplos ficticios de las maquetas. El análisis de temas es orientativo; los exámenes anteriores no permiten predecir futuras preguntas.

## Instalación y arranque

Requisitos: Python 3.13, [uv](https://docs.astral.sh/uv/), Node.js y npm. Configura `OPENAI_API_KEY` en una copia local de `.env.example` guardada como `.env`.

```powershell
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Añade tu `OPENAI_API_KEY` al archivo `.env` local.

En `web/`, instala las dependencias:

```powershell
cd web
npm.cmd ci
```

Inicia cada servicio en una terminal distinta. Desde la raíz del proyecto, arranca el servidor:

```powershell
uv run python servidor.py
```

Desde `web/`, arranca la interfaz:

```powershell
npm.cmd run dev
```

Abre http://127.0.0.1:5173.

## Comprobación

Probé estas preguntas en una misma conversación:

- «¿Qué preguntas se repiten más?»
- «¿Cuáles son las más probables en función de las anteriores?»
- «¿Qué no debo no saber?»
- «¿Qué preguntas caerán en la siguiente convocatoria?»

La última se responde indicando que no consta en los datos.

## Entregable

[Descargar la memoria en PDF](./entregable.pdf)
