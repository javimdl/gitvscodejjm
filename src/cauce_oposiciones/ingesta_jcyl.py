"""Descarga reproducible de documentación pública oficial de Gestión Informática.

Se conservan PDF, huellas y páginas físicas. La clasificación por palabras clave
es orientativa; nunca determina por sí sola la respuesta correcta de un test.
"""

from datetime import date
import hashlib
import json
import logging
from pathlib import Path
import re
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from bs4 import BeautifulSoup
from dotenv import dotenv_values
from pypdf import PdfReader

from .datos import RAIZ, normalizar
from .modelos import Documento, Fragmento

BASE = "https://empleopublico.jcyl.es"
PREFIJO = BASE + "/web/jcyl/EmpleoPublico/es/Plantilla100Detalle/"
BUSCADOR = BASE + "/web/jcyl/EmpleoPublico/es/PlantillaBuscadorContenidos/1277227614255/Convocatoria/1277227637904/_"
CONVOCATORIAS = [
    (PREFIJO + "1246947697738/Convocatoria/1284573187214/Empleo", "OEP 2016", "Promoción interna", 2016),
    (PREFIJO + "1277227614255/Convocatoria/1284838424880/Empleo", "OEP 2017", "Libre", 2018),
    (PREFIJO + "1277227614255/Convocatoria/1285340770431/Empleo", "OEP 2020", "Promoción interna", 2023),
    (PREFIJO + "1277227614255/Convocatoria/1285519771741/Empleo", "OEP 2022/2023/2024", "Libre", 2025),
    (PREFIJO + "1277227614255/Convocatoria/1285584370271/Empleo", "OEP 2022/2023/2024", "Promoción interna", 2025),
]
PATRONES = {
    "SQL": r"\bsql\b|\bjoin\b|\bselect\b|\bhaving\b|group\s+by",
    "Bases de datos": r"\bsgbd\b|base[s]? de datos|modelo relacional|\boracle\b|\bpostgres\w*\b|\bmongodb\b|normalizaci|\btransaccion\w*\b",
    "Redes": r"\bipv[46]\b|\btcp\b|\budp\b|\bdns\b|\bvlan\b|\bsubred\w*\b|\bethernet\b|\brouter\b|\bswitch\b|\bosi\b|\bdhcp\b",
    "Seguridad": r"\bseguridad\b|\bens\b|\bautentic\w*\b|\bautoriz\w*\b|\bjwt\b|\bcifrad\w*\b|\bfirewall\b|\brgpd\b|certificado[s]? digital|minimo privilegio",
    "Programación": r"\bjava\b|\bpython\b|\bjavascript\b|\bclase[s]?\b|\bherencia\b|\bpolimorfismo\b|\bsingleton\b|\bhtml\b|\bcss\b|\bxml\b|\bgit\b|\brest\b|\bsoap\b",
    "Sistemas": r"\blinux\b|\bunix\b|\bwindows\b|sistema[s]? operativo|\bvirtualiza\w*\b|\bhipervisor\b|\bcontenedor\w*\b|\bkubernetes\b|\bnube\b",
    "Normativa": r"\bley\s+\d|\bconstitucion\b|\bdecreto\s+\d|\bebep\b|procedimiento administrativo|funcion publica|estatuto de autonomia",
    "Gestión TIC": r"\bitil\b|\bscrum\b|\bkanban\b|gestion de proyectos|ciclo de vida|gestion de servicios|\bmagerit\b",
}
MESES = dict(zip("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), range(1, 13)))


def clasificar_temas(texto: str) -> list[str]:
    texto = normalizar(texto)
    return [tema for tema, patron in PATRONES.items() if re.search(patron, texto)]


def _trozos(lineas: list[tuple[int, str]], limite: int = 1800):
    actual = []
    longitud = 0
    for pagina, linea in lineas:
        if actual and longitud + len(linea) > limite:
            yield actual
            actual, longitud = [], 0
        actual.append((pagina, linea))
        longitud += len(linea) + 1
    if actual:
        yield actual


def extraer_fragmentos(paginas: list[str], tipo: str) -> list[Fragmento]:
    fragmentos = []

    def agregar(lineas, identificador, etiqueta, clase):
        for parte, trozo in enumerate(_trozos(lineas), 1):
            texto = "\n".join(linea for _, linea in trozo).strip()
            if len(texto) < 20:
                continue
            temas = clasificar_temas(texto)
            inicio, fin = trozo[0][0], trozo[-1][0]
            fragmentos.append(Fragmento(
                id=f"{identificador}-{parte}", texto=texto, clase=clase,
                tema=temas[0] if temas else "Sin clasificar", temas=temas,
                pagina_inicio=inicio, pagina_fin=fin,
                ubicacion=f"{etiqueta} · página física {inicio}" + (f"–{fin}" if fin != inicio else "") + " del PDF"))

    if tipo != "Cuestionario":
        for numero, texto in enumerate(paginas, 1):
            agregar([(numero, l.rstrip()) for l in texto.splitlines() if l.strip()],
                    f"p{numero}", "Texto publicado", "practico" if tipo == "Práctico" else "texto")
        return fragmentos

    lineas = []
    for numero, pagina in enumerate(paginas, 1):
        for linea in pagina.splitlines():
            norm = normalizar(linea.strip())
            if (not norm or re.match(r"^(?:pagina\s+\d+\s+de\s+\d+|\d{1,3})$", norm)
                    or re.match(r"^(?:categoria profesional:|tecnico\s*-?\s*a?\s+de\s+gestion informatica|primer ejercicio \d|valladolid, \d)", norm)):
                continue
            lineas.append((numero, linea.rstrip()))
    bloque, contexto, numero_actual, esperado = [], [], None, 1
    practico = False
    contextos = 0

    def guardar_pregunta():
        if bloque:
            agregar(bloque, f"q{numero_actual}", f"Pregunta {numero_actual}", "practico" if practico else "pregunta")

    for posicion, (pagina, linea) in enumerate(lineas):
        norm = normalizar(linea.strip())
        if re.match(r"^(?:(?:primer|segundo|tercer)\s+supuesto|supuesto\s+(?:practico\s*)?\d)", norm):
            guardar_pregunta()
            bloque = []
            numero_actual = None
            if contexto:
                contextos += 1
                agregar(contexto, f"contexto{contextos}", "Contexto e instrucciones", "texto")
            contexto = [(pagina, linea)]
            practico = True
            continue
        match = re.match(r"^\s*(\d{1,3})\s*(?:[.)]\s*[-–—]?|-)\s*(\S.*)$", linea)
        candidato = int(match[1]) if match else None
        opciones = any(re.match(r"^\s*[a-dA-D]\s*[).]", l) for _, l in lineas[posicion + 1:posicion + 18])
        if candidato == esperado and opciones:
            guardar_pregunta()
            if contexto:
                contextos += 1
                agregar(contexto, f"contexto{contextos}", "Contexto del supuesto" if practico else "Instrucciones", "practico" if practico else "texto")
                contexto = []
            numero_actual, esperado = candidato, candidato + 1
            bloque = [(pagina, linea)]
        elif numero_actual is not None:
            bloque.append((pagina, linea))
        else:
            contexto.append((pagina, linea))
    guardar_pregunta()
    if contexto:
        agregar(contexto, "contexto-final", "Contexto del documento", "practico" if practico else "texto")
    if not any(f.clase == "pregunta" for f in fragmentos):
        # Fallback verificable: conservar páginas, no inventar preguntas numeradas.
        return extraer_fragmentos(paginas, "Texto")
    return fragmentos


def _anio_pdf(reader: PdfReader, paginas: list[str], tipo: str, defecto: int) -> int:
    if tipo in {"Cuestionario", "Práctico", "Plantilla"}:
        cabecera = normalizar(" ".join(paginas[:3]))
        fecha = re.search(r"(?:ejercicio|valladolid)[^\d]{0,25}\d{1,2}\s+de\s+\w+\s+de\s+(20\d{2})", cabecera)
        if fecha:
            return int(fecha[1])
        fecha = re.search(r"\b\d{1,2}/\d{1,2}/(20\d{2})\b", cabecera)
        if fecha:
            return int(fecha[1])
        fecha = re.search(r"primer ejercicio\s+\d{1,2}/\d{1,2}/(20\d{2})", cabecera)
        if fecha:
            return int(fecha[1])
        metadata = reader.metadata or {}
        fecha = re.match(r"D:(20\d{2})", str(metadata.get("/CreationDate", "")))
        if fecha:
            return int(fecha[1])
    return defecto


class ImportadorJcyl:
    def __init__(self):
        valor = dotenv_values(RAIZ / ".env").get("HTTPS_PROXY")
        proxies = {}
        if valor:
            proxy = urlsplit(valor)
            # urllib y curl no resuelven igual un proxy sin puerto explícito.
            if proxy.port is None:
                proxy = proxy._replace(netloc=proxy.netloc + (":80" if proxy.scheme == "http" else ":443"))
            proxies = {"http": proxy.geturl(), "https": proxy.geturl()}
        self.opener = build_opener(ProxyHandler(proxies))
        self.carpeta = RAIZ / "datos" / "jcyl"
        self.cache = RAIZ / ".cache" / "jcyl"
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.incidencias = []

    def descargar(self, url: str) -> bytes:
        hostname = urlsplit(url).hostname or ""
        if not (hostname == "jcyl.es" or hostname.endswith(".jcyl.es")):
            raise ValueError("La fuente no pertenece a la Junta de Castilla y León.")
        peticion = Request(url, headers={"User-Agent": "Mozilla/5.0 Cauce/0.1 (documentación pública de oposiciones)"})
        with self.opener.open(peticion, timeout=25) as respuesta:
            final = urlsplit(respuesta.geturl()).hostname or ""
            if not (final == "jcyl.es" or final.endswith(".jcyl.es")):
                raise ValueError("La descarga se ha redirigido fuera de la Junta.")
            datos = respuesta.read(20 * 1024 * 1024 + 1)
        if len(datos) > 20 * 1024 * 1024:
            raise ValueError("El documento supera el límite de descarga de 20 MiB.")
        return datos

    def pagina(self, url: str):
        raw = self.descargar(url)
        (self.cache / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".html")).write_bytes(raw)
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
        if not soup.h1:
            raise ValueError("La ficha no contiene un título reconocible.")
        return soup

    @staticmethod
    def enlaces(soup, url):
        return [(a.get_text(" ", strip=True), urljoin(url, a["href"]))
                for a in soup.find_all("a", href=True)]

    def ejecutar(self) -> dict:
        archivo = self.carpeta / "documentos.json"
        anteriores = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else []
        por_url = {d["url"].split("?", 1)[0]: d for d in anteriores}
        siguiente = max([100, *[int(d["id"].split("-")[1]) for d in anteriores]]) + 1
        consultas = []
        candidatos = []
        for consulta in ("tecnico de gestion informatica", "gestión informática"):
            url = BUSCADOR + "?" + urlencode({"p0": "false", "p2": "Convocatoria", "tituloc": "true", "q": consulta, "aceptar": "Buscar"})
            try:
                soup = self.pagina(url)
                consultas.append({"consulta": consulta, "url": url,
                                  "titulo": soup.h1.get_text(" ", strip=True)})
            except Exception as error:
                self.incidencias.append({"url": url, "error": type(error).__name__})
        for url, oferta, turno, anio in CONVOCATORIAS:
            try:
                soup = self.pagina(url)
                titulo = soup.h1.get_text(" ", strip=True)
                if "gestion informatica" not in normalizar(titulo):
                    raise ValueError("La ficha corresponde a otra categoría.")
                print(f"Convocatoria: {titulo} · {oferta}", flush=True)
                meta = {"convocatoria": f"{titulo} · {oferta}", "turno": turno,
                        "anio_base": anio, "grupo_examen": f"TGI-{oferta}-{turno}", "url_ficha": url}
                for texto, href in self.enlaces(soup, url):
                    norm = normalizar(texto)
                    if ".pdf" in href.lower():
                        if "programa" in norm or "temario" in norm:
                            candidatos.append((texto, href, "Temario", meta))
                        elif norm.startswith("resolucion") and "convoc" not in norm:
                            candidatos.append((texto, href, "Convocatoria", meta))
                    elif any(x in norm for x in ("cuestionario", "cuadernillo", "plantilla de respuestas", "supuesto practico")):
                        fase = self.pagina(href)
                        for nombre, enlace in self.enlaces(fase, href):
                            if ".pdf" in enlace.lower():
                                nt = normalizar(nombre)
                                tipo = "Plantilla" if "plantilla" in nt or "respuestas" in nt else "Práctico" if "supuesto" in nt else "Cuestionario"
                                candidatos.append((nombre, enlace, tipo, {**meta, "url_ficha": href,
                                    "fase": fase.h1.get_text(" ", strip=True)}))
                            elif re.search(r"\.(?:doc|docx|zip)(?:\?|$)", enlace, re.I):
                                self.incidencias.append({"url": enlace, "motivo": "Formato distinto de PDF; no se indexa sin conversión."})
            except Exception as error:
                self.incidencias.append({"url": url, "error": type(error).__name__, "mensaje": str(error)[:180]})
        hashes = {d.get("sha256"): clave for clave, d in por_url.items()}
        consultados = set()
        incorporados = 0
        for nombre, url, tipo, meta in candidatos:
            canonica = url.split("?", 1)[0]
            if canonica in consultados:
                continue
            consultados.add(canonica)
            try:
                raw = self.descargar(url)
                if not raw.lstrip().startswith(b"%PDF-"):
                    raise ValueError("La respuesta no es un PDF.")
                huella = hashlib.sha256(raw).hexdigest()
                if huella in hashes and hashes[huella] != canonica:
                    continue  # Mismo archivo publicado con otro enlace.
                existente = por_url.get(canonica)
                identificador = existente["id"] if existente else f"DOC-{siguiente}"
                if not existente:
                    siguiente += 1
                original = self.carpeta / "originales" / f"{identificador}.pdf"
                original.parent.mkdir(parents=True, exist_ok=True)
                original.write_bytes(raw)
                reader = PdfReader(original)
                paginas = [(p.extract_text(extraction_mode="layout") if tipo == "Plantilla" else p.extract_text()) or ""
                           for p in reader.pages]
                fragmentos = extraer_fragmentos(paginas, tipo)
                if not fragmentos:
                    raise ValueError("No hay texto extraíble; se necesita OCR y el documento no se indexa.")
                anio = _anio_pdf(reader, paginas, tipo, meta["anio_base"])
                temas = sorted({t for f in fragmentos for t in f.temas})
                etiqueta = meta.get("fase", meta["convocatoria"])
                documento = Documento(
                    id=identificador, titulo=f"{tipo} · {meta['convocatoria']} · año de referencia {anio}", tipo=tipo,
                    anio=anio, origen="JCyL", procedencia="Portal oficial de Empleo Público de JCyL",
                    temas=temas, ficticio=False, fragmentos=fragmentos, url=url,
                    url_ficha=meta["url_ficha"], fecha_consulta=date.today().isoformat(), sha256=huella,
                    convocatoria=meta["convocatoria"], turno=meta["turno"], grupo_examen=meta["grupo_examen"],
                    alcance=(f"Documento oficial descargado: {nombre}. Ficha: {etiqueta}. "
                             "Texto extraído del PDF; páginas físicas, sin interpretar imágenes o diagramas. "
                             "La clasificación temática es automática y orientativa. "
                             "El año es una referencia documental: fecha explícita en el texto, "
                             "creación del PDF o, en su defecto, año de convocatoria; no acredita por sí solo la fecha del examen. "
                             "Los enunciados y sus opciones no acreditan por sí solos la respuesta correcta."))
                por_url[canonica] = documento.model_dump()
                hashes[huella] = canonica
                incorporados += 1
                print(f"{identificador}: {tipo} · {anio} · {len(paginas)} páginas · {len(fragmentos)} fragmentos", flush=True)
            except Exception as error:
                self.incidencias.append({"url": url, "error": type(error).__name__, "mensaje": str(error)[:180]})
                print(f"No incorporado: {nombre}: {type(error).__name__}", flush=True)
        documentos = sorted(por_url.values(), key=lambda d: int(d["id"].split("-")[1]))
        if not documentos:
            raise RuntimeError("No se ha podido incorporar ningún PDF oficial.")
        temporal = archivo.with_suffix(".tmp")
        temporal.write_text(json.dumps(documentos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporal.replace(archivo)
        informe = {"fecha": date.today().isoformat(), "consultas": consultas,
                   "convocatorias": [u for u, *_ in CONVOCATORIAS],
                   "documentos_oficiales": len(documentos), "archivos_verificados": incorporados,
                   "fragmentos": sum(len(d["fragmentos"]) for d in documentos), "incidencias": self.incidencias}
        (self.carpeta / "informe_importacion.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return informe
