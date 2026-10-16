/** Ejecutar desde web/: node capturas.mjs. Requiere FastAPI y Vite arrancados. */
import { chromium } from 'playwright-core'
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve, dirname } from 'node:path'

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const carpeta = resolve(raiz, 'capturas')
const origen = process.env.APP_URL ?? 'http://127.0.0.1:5173'
await mkdir(carpeta, { recursive: true })
const navegador = await chromium.launch({ channel: 'msedge', headless: true })
const contexto = await navegador.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1, locale: 'es-ES' })
const pagina = await contexto.newPage()
pagina.setDefaultTimeout(120_000)
const errores = []
pagina.on('pageerror', error => errores.push(error.message))
const preguntas = [
  ['01-repetidas', '¿Qué preguntas se repiten más?'],
  ['02-probables', '¿Cuáles son las más probables en función de las anteriores?'],
  ['03-imprescindibles', '¿Qué no debo no saber?'],
  ['04-no-consta', '¿Qué preguntas caerán en la siguiente convocatoria?'],
]
try {
  await pagina.goto(origen, { waitUntil: 'networkidle' })
  await pagina.getByText('Repositorio disponible', { exact: true }).waitFor()
  const catalogoRespuesta = await contexto.request.get(`${origen}/api/documentos`)
  assert(catalogoRespuesta.ok(), 'El catálogo debe estar accesible a través de Vite')
  const catalogo = await catalogoRespuesta.json()
  const corpus = new Map(catalogo.documentos.flatMap(d => d.fragmentos.map(f => [`${d.id}:${f.id}`, { documento: d, fragmento: f }])))
  const resultados = []
  for (const [i, [nombre, pregunta]] of preguntas.entries()) {
    console.log(`${i + 1}/5: ${pregunta}`)
    const espera = pagina.waitForResponse(r => r.url() === `${origen}/api/preguntar` && r.request().method() === 'POST')
    await pagina.getByLabel('Tu pregunta', { exact: true }).fill(pregunta)
    await pagina.getByRole('button', { name: 'Enviar pregunta', exact: true }).click()
    const http = await espera
    const respuesta = await http.json()
    assert(http.ok(), `La API debe responder correctamente: ${JSON.stringify(respuesta)}`)
    assert.equal(respuesta.no_consta, i === 3, 'Solo la pregunta futura debe carecer de evidencia')
    assert.equal(respuesta.modelo_utilizado, i !== 3)
    assert(respuesta.respuesta.length > 30 && respuesta.fuentes.length > 0, 'Hay respuesta real y fuentes')
    const historial = http.request().postDataJSON().historial
    assert.equal(historial.length, i * 2, 'Cada petición conserva los intercambios anteriores')
    for (const fuente of respuesta.fuentes) {
      const original = corpus.get(fuente.referencia)
      assert(original, `La fuente ${fuente.referencia} existe en el catálogo`)
      assert.equal(fuente.fragmento, original.fragmento.texto, 'El fragmento citado coincide literalmente con el almacenado')
      assert.equal(fuente.ficticio, false, 'La respuesta se apoya en el corpus real')
    }
    const turno = pagina.locator('.chat-turn').nth(i)
    await turno.locator('.answer').waitFor()
    await turno.locator('.source-card').first().waitFor()
    if (i === 3) await turno.getByText('ⓘ No consta en los datos.', { exact: true }).waitFor()
    // Desplazar la vista al intercambio actual, mostrando respuesta y fuentes.
    await turno.evaluate(elemento => {
      const fuente = elemento.querySelector('.sources')
      const comienzo = elemento.getBoundingClientRect().top + window.scrollY
      const inicioFuentes = fuente.getBoundingClientRect().top + window.scrollY
      window.scrollTo(0, Math.max(0, comienzo - 25, inicioFuentes - 490))
    })
    await pagina.evaluate(() => document.fonts.ready)
    await turno.locator('.source-card').first().waitFor({ state: 'visible' })
    const fuenteVisible = await turno.locator('.source-card').first().boundingBox()
    assert(fuenteVisible && fuenteVisible.y < 850 && fuenteVisible.y + fuenteVisible.height > 0, 'La captura muestra las fuentes')
    await pagina.screenshot({ path: resolve(carpeta, `${nombre}.png`), fullPage: false, animations: 'disabled' })
    // También se conserva el intercambio completo, para lectura sin recortes.
    await turno.screenshot({ path: resolve(carpeta, `${nombre}-completa.png`), animations: 'disabled' })
    resultados.push({ nombre, pregunta, respuesta, historial_enviado: historial.length,
      fuentes_verificadas_literalmente: true, captura: `capturas/${nombre}.png`, detalle: `capturas/${nombre}-completa.png` })
    console.log(`  OK: ${respuesta.fuentes.length} fuentes cotejadas; no_consta=${respuesta.no_consta}`)
  }
  await pagina.getByRole('link', { name: /Biblioteca/ }).first().click()
  await pagina.getByRole('heading', { name: 'Todo tiene una fuente.' }).waitFor()
  assert(await pagina.locator('tbody tr').count() >= 16)
  await pagina.evaluate(() => window.scrollTo(0, 0))
  await pagina.screenshot({ path: resolve(carpeta, '05-documentos.png'), fullPage: false, animations: 'disabled' })
  assert.deepEqual(errores, [], 'La interfaz no presenta errores JavaScript')
  await writeFile(resolve(carpeta, 'resultados.json'), JSON.stringify({
    proyecto: 'Clases TGI', fecha: new Date().toISOString(), origen,
    viewport: { width: 1366, height: 900 }, navegador: 'Microsoft Edge (channel: msedge)',
    consultas: resultados, documentos: catalogo.documentos,
    listado: { captura: 'capturas/05-documentos.png', total_catalogo: catalogo.total,
      oficiales: catalogo.documentos.filter(d => !d.ficticio && d.origen === 'JCyL').length,
      visibles_por_defecto: catalogo.documentos.filter(d => !d.ficticio).length },
  }, null, 2) + '\n', 'utf8')
  console.log('5/5: catálogo capturado. PNG y resultados reales guardados en capturas/.')
} finally { await navegador.close() }
