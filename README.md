# Cauce · Aula de oposiciones TIC

Base local para preparar la oposición de Técnico/a de Gestión Informática de la Junta de Castilla y León.

## Estructura

- `maquetas.html`: las seis pantallas originales, con datos ficticios.
- `servidor.py`: arranque del servidor FastAPI en el puerto 8000.
- `src/cauce_oposiciones/`: API, contratos JSON, preparación del análisis y RAG.
- `datos/documentos.json`: copia del corpus ficticio de las maquetas, editable.
- `scripts/preparar_datos.py`: regenera esa copia desde el array literal del HTML sin ejecutar JavaScript.
- `rag/indice.npz`: embeddings persistidos, generado automáticamente y excluido de Git.
- `ejemplos/`: peticiones JSON UTF-8 para probar el chat con curl.
- `tests/`: pruebas del RAG sin acceso a la red.
- `web/`: interfaz Svelte con TypeScript, creada con la plantilla oficial de Vite.
- `pyproject.toml` y `uv.lock`: dependencias Python gestionadas con uv.
- `web/package-lock.json`: versiones fijadas de las dependencias npm.

El servidor implementa búsqueda con embeddings y respuestas fundamentadas mediante OpenAI. Incluye 16 PDF oficiales descargados de cinco convocatorias del portal de Empleo Público de la Junta y conserva por separado los siete registros ficticios de las maquetas. Al haber documentos oficiales, el RAG consulta únicamente esos documentos y su análisis local. La interfaz Svelte sigue siendo la pantalla inicial de comprobación y la maqueta conserva las seis pantallas de referencia.

## Documentación oficial importada

La importación consulta el buscador de la Junta por «tecnico de gestion informatica» y «gestión informática» y recorre cinco fichas verificadas: OEP 2016 (promoción interna), OEP 2017 (libre), OEP 2020 (promoción interna) y OEP 2022/2023/2024 (libre y promoción interna). No pretende recopilar todo el histórico.

- `datos/jcyl/documentos.json`: 16 publicaciones oficiales, con 535 fragmentos extraídos de cuestionarios, prácticos, plantillas, convocatorias y programas.
- `datos/jcyl/originales/`: los PDF descargados, identificados por el ID del documento.
- `datos/jcyl/informe_importacion.json`: consultas, fichas recorridas e incidencias. Un cuadernillo antiguo en Word queda pendiente de conversión y no se indexa.
- `scripts/importar_jcyl.py`: importador reproducible. Conserva identificadores, evita duplicados por URL y huella SHA-256 y mantiene documentos anteriores si una descarga falla.

Para actualizar los documentos desde la web oficial y después arrancar con el índice actualizado:

```powershell
uv run python scripts/importar_jcyl.py
uv run servidor.py
```

Si el servidor ya estaba arrancado, detenlo con Ctrl+C y vuelve a iniciarlo tras importar. El cambio del corpus invalida el índice y genera los embeddings una vez; los siguientes arranques los reutilizan. Cada publicación conserva su URL de descarga, ficha de convocatoria, fecha de consulta, turno y huella SHA-256. Las fuentes de respuestas enlazan la página física del PDF.

El año es una referencia documental tomada de una fecha explícita, de los metadatos del PDF o de la convocatoria, en ese orden; no acredita por sí solo la fecha del examen. La lectura automática no interpreta imágenes o diagramas. Las opciones de respuesta se distinguen de las soluciones, y se adjunta la plantilla del mismo grupo cuando está disponible. Su carácter provisional, si lo indica el original, sigue siendo aplicable.

El registro `REG-02` calcula presencia de temas por grupo de examen a partir de 187 preguntas teóricas segmentadas (88 de promoción interna de 2025 y 99 de libre de 2026, incluidas reservas). No cuenta enunciados literalmente repetidos: las etiquetas por palabras clave son orientativas. Excluye supuestos, instrucciones y el cuestionario antiguo que no tiene formato de test segmentable. Los dos turnos se incluyen juntos y no sirven para estimar probabilidades de futuras preguntas.

Prueba el catálogo oficial sin los ejemplos:

```powershell
curl.exe --noproxy "*" --silent --show-error --fail-with-body "http://127.0.0.1:8000/api/documentos?origen=JCyL&ficticio=false"
```

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
Configura `OPENAI_API_KEY` en el `.env` local para generar embeddings y respuestas. La clave nunca se envía al navegador ni se incluye en Git. Los valores opcionales son `OPENAI_MODEL=gpt-6-luna`, `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` y `RAG_UMBRAL=0.35`, siguiendo el modelo del RAG de referencia.

## Arrancar en desarrollo

Abre dos terminales en la carpeta del proyecto.

**Terminal 1: servidor Python en el puerto 8000.**

```powershell
uv run servidor.py
```

Antes de pasar a la interfaz, comprueba la API con las instrucciones de [Probar la API con curl](#probar-la-api-con-curl).

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

## Probar la API con curl

Con FastAPI arrancado, ejecuta primero estas peticiones al servidor Python. Usa `curl.exe` en PowerShell para invocar curl directamente.
`--noproxy "*"` hace que las peticiones locales no pasen por el proxy corporativo.

```powershell
curl.exe --noproxy "*" --silent --show-error --fail-with-body -i http://127.0.0.1:8000/api/health
curl.exe --noproxy "*" --silent --show-error --fail-with-body --output NUL --write-out "HTTP %{http_code}\n" http://127.0.0.1:8000/openapi.json
curl.exe --noproxy "*" --silent --show-error --fail-with-body --output NUL --write-out "HTTP %{http_code}\n" http://127.0.0.1:8000/api/maquetas
curl.exe --noproxy "*" --silent --show-error --output NUL --write-out "HTTP %{http_code}\n" http://127.0.0.1:8000/api/no-existe
```

Resultados esperados: `200` para las tres primeras peticiones y `404` para la ruta inexistente. `/api/health` debe devolver:

```json
{"status":"ok","service":"cauce-oposiciones"}
```

La última petición omite `--fail-with-body` porque su resultado esperado es un error HTTP 404. La respuesta de salud incluye además `rag.indice_disponible`, `rag.indice_reutilizado` y el número de fragmentos.

### Las cuatro preguntas de las maquetas

Desde la raíz, con `uv run servidor.py` arrancado, envía estos archivos UTF-8. Usar archivos evita problemas con las comillas y los acentos al pasar JSON a curl en PowerShell.

```powershell
curl.exe --noproxy "*" --silent --show-error --fail-with-body http://127.0.0.1:8000/api/preguntar -H "Content-Type: application/json" --data-binary "@ejemplos/repetidas.json"
curl.exe --noproxy "*" --silent --show-error --fail-with-body http://127.0.0.1:8000/api/preguntar -H "Content-Type: application/json" --data-binary "@ejemplos/probables.json"
curl.exe --noproxy "*" --silent --show-error --fail-with-body http://127.0.0.1:8000/api/preguntar -H "Content-Type: application/json" --data-binary "@ejemplos/imprescindibles.json"
curl.exe --noproxy "*" --silent --show-error --fail-with-body http://127.0.0.1:8000/api/preguntar -H "Content-Type: application/json" --data-binary "@ejemplos/siguiente-convocatoria.json"
```

Las tres primeras deben responder con `no_consta: false` y fuentes literales del corpus. La segunda ofrece prioridades de estudio y explica que no puede calcular probabilidades fiables. La cuarta responde «No consta en los datos», con `no_consta: true`, `modelo_utilizado: false` y el registro de cobertura como fuente; no hace llamadas de generación ni embeddings de esa pregunta.

### Contrato de conversación

`POST /api/preguntar` recibe:

```json
{"pregunta":"¿Qué preguntas se repiten más?","historial":[{"role":"user","content":"Estoy repasando los cuestionarios JCyL."}]}
```

El historial acepta hasta 20 mensajes `user` o `assistant`. La pregunta admite de 1 a 2000 caracteres y cada mensaje hasta 4000. Los roles de instrucciones (`system`, etc.) y las preguntas vacías se rechazan con HTTP 422.

La salida JSON tiene `respuesta` (texto con referencias), `fuentes` (lista), `no_consta` (booleano) y `modelo_utilizado` (booleano referido al modelo de respuestas). Cada fuente incluye `referencia`, `documento_id`, `titulo`, `fragmento_id`, `ubicacion`, `fragmento`, `similitud`, `ficticio`, `url`, `url_ficha`, `convocatoria` y `turno`.
Las fuentes proceden del servidor, no de fragmentos redactados por el modelo. `similitud: null` identifica fuentes de cobertura o documentos enlazados por un registro calculado, sin asignarles una similitud ficticia.

Sin resultados que alcancen el umbral, se devuelve «No consta en los datos» sin llamar al modelo de respuestas; la búsqueda sí puede usar un embedding de la pregunta. Los errores de configuración o del proveedor son HTTP 503, y una salida con citas inválidas es HTTP 502: ninguno se disfraza como falta de datos.

### Listado y búsqueda de documentos

```powershell
curl.exe --noproxy "*" --silent --show-error --fail-with-body http://127.0.0.1:8000/api/documentos
curl.exe --noproxy "*" --silent --show-error --fail-with-body "http://127.0.0.1:8000/api/documentos?q=SQL&tipo=Cuestionario&origen=JCyL&anio=2024"
```

`GET /api/documentos` devuelve `documentos` y `total`. Admite los filtros opcionales `q`, `tipo`, `anio`, `origen` y `ficticio`. Cada registro incluye identificador, título, tipo, año, procedencia, temas, alcance, la marca `ficticio`, metadatos de procedencia y los fragmentos para la ficha documental. Los filtros de texto ignoran tildes y mayúsculas. Sin filtros incluye también los ejemplos conservados y los registros de análisis local.

### Datos e índice persistente

Los ejemplos originales contienen seis documentos y un registro interno ficticios. Al cargarlos se mantienen sus análisis en `REG-01`. Los documentos oficiales se cargan desde un archivo independiente y se sintetizan en `REG-02`, sin mezclar ejemplos en las respuestas reales.

Los 535 fragmentos oficiales y cuatro fragmentos de análisis local se indexan con embeddings normalizados; la recuperación usa similitud coseno, hasta 8 resultados por encima del umbral, los documentos de base enlazados por los registros calculados y las plantillas del mismo grupo. El índice comprimido se escribe de forma atómica en `rag/indice.npz`. Su huella incluye el corpus activo, los metadatos y el modelo de embeddings: cambiar un texto con el mismo número de fragmentos también lo invalida. Los arranques con la misma huella leen disco sin recalcular embeddings documentales. Cambiar solo el modelo de respuestas no obliga a reconstruirlos.

Puedes editar `datos/documentos.json` y reiniciar. Para volver a copiar los datos desde la maqueta:

```powershell
uv run python scripts/preparar_datos.py
```

Este comando regenera únicamente el JSON ficticio y sustituye las ediciones manuales que contuviera; conserva la carpeta `datos/jcyl/`. Una caché ausente o corrupta se reconstruye; no se usa pickle. Las preguntas y respuestas de los usuarios no se guardan en disco.

### Pruebas automáticas sin red

```powershell
uv run python -m unittest discover -s tests -v
```

Verifican reutilización e invalidación de caché, recuperación de una caché corrupta, negativas sin llamadas al modelo, seguimiento del historial, recuentos históricos y validación de citas. Los clientes falsos de las pruebas nunca se utilizan en el servidor real.

Después, con Vite también arrancado, comprueba el reenvío al mismo servidor Python:

```powershell
curl.exe --noproxy "*" --silent --show-error --fail-with-body -i http://127.0.0.1:5173/api/health
```

Debe devolver `200` y el mismo JSON. Así se verifica la conexión antes de trabajar en la interfaz.

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
