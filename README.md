# Cauce · Aula de oposiciones TIC

Base local para preparar la oposición de Técnico/a de Gestión Informática de la Junta de Castilla y León.

## Estructura

- `maquetas.html`: las seis pantallas originales, con datos ficticios.
- `src/cauce_oposiciones/api.py`: API FastAPI inicial.
- `web/`: interfaz Svelte con TypeScript, creada con la plantilla oficial de Vite.
- `pyproject.toml` y `uv.lock`: dependencias Python gestionadas con uv.
- `web/package-lock.json`: versiones fijadas de las dependencias npm.

La aplicación está preparada para desarrollar sus funciones. La pantalla inicial comprueba la conexión a la API; las funciones de estudio continúan representadas en la maqueta. Todavía no se realizan llamadas a OpenAI, consultas a la Junta ni operaciones de base de datos.

## Requisitos

Node.js y npm, uv y Git. uv gestiona Python 3.13 mediante `.python-version`.
En PowerShell se usa `npm.cmd` para evitar depender de la política de ejecución de scripts `.ps1`.

## Instalar las dependencias

Desde la carpeta del proyecto:

```powershell
uv sync --locked
cd web
npm.cmd ci
cd ..
```

## Configuración local y proxy

Copia `.env.example` a `.env` si no existe y ajusta `HTTPS_PROXY` a tu red. La API carga el `.env` de la raíz mediante python-dotenv.

En esta preparación, `proxy` y `https-proxy` de npm se han configurado en el perfil del usuario con el valor de `HTTPS_PROXY`. Si cambia el proxy, actualiza tanto `.env` como la configuración de npm:

```powershell
$proxyLine = Get-Content .env | Where-Object { $_ -match '^HTTPS_PROXY=' } | Select-Object -First 1
$projectProxy = ($proxyLine -split '=', 2)[1].Trim()
npm.cmd config set proxy $projectProxy
npm.cmd config set https-proxy $projectProxy
```

Para instalar paquetes Python en una terminal nueva, pasa también ese valor al proceso de uv:

```powershell
$env:HTTPS_PROXY = $projectProxy
uv sync --locked
```

Para añadir nuevas dependencias Python usa siempre `uv add nombre-del-paquete`. No se utiliza pip.
`OPENAI_API_KEY` queda reservado para el desarrollo posterior y no es necesario para arrancar.

## Arrancar en desarrollo

Abre dos terminales en la carpeta del proyecto.

**Terminal 1: servidor Python en el puerto 8000.**

```powershell
uv run --locked python -m uvicorn cauce_oposiciones.api:app --reload --reload-dir src --host 127.0.0.1 --port 8000
```

**Terminal 2: interfaz en el puerto 5173.**

```powershell
cd web
npm.cmd run dev
```

- Interfaz: <http://127.0.0.1:5173/>
- API: <http://127.0.0.1:8000/api/health>
- Documentación de la API: <http://127.0.0.1:8000/docs>
- Maqueta original a través de Vite: <http://127.0.0.1:5173/api/maquetas>

Vite reenvía `/api` a `http://127.0.0.1:8000` conservando el prefijo. El puerto 5173 es fijo: si está ocupado, Vite avisa en lugar de elegir otro.
El proxy de desarrollo se aplica a `npm.cmd run dev`; `vite preview` solo previsualiza la compilación estática.

## Comprobar la interfaz

```powershell
cd web
npm.cmd run check
npm.cmd run build
```

Con los dos servidores arrancados, una petición a `http://127.0.0.1:5173/api/health` debe devolver:

```json
{"status":"ok","service":"cauce-oposiciones"}
```

## Archivos excluidos de Git

`.env`, `.venv/`, `node_modules/`, compilaciones, cachés y bases de datos SQLite se excluyen con `.gitignore`.
Se versionan `.env.example` y los archivos de bloqueo, nunca claves ni credenciales.
