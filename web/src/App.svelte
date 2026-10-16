<script lang="ts">
  import { onMount, tick } from 'svelte'
  import RespuestaVista from './lib/Respuesta.svelte'
  import { obtenerDocumentos, obtenerSalud, preguntar, normalizar, rutaDocumento, enlaceSeguro,
    type Documento, type Respuesta, type Mensaje, type Salud } from './lib/api'
  type Turno = { id: number; pregunta: string; respuesta?: Respuesta; error?: string }
  let ruta = $state('/chat'), documentos = $state<Documento[]>([]), cargando = $state(true)
  let errorDatos = $state(''), salud = $state<Salud | null>(null), texto = $state('')
  let turnos = $state<Turno[]>([]), enviando = $state(false)
  let consulta = $state(''), tipo = $state(''), anio = $state(''), procedencia = $state('reales')
  let filtroClase = $state(''), lecciones = $state<Record<string, Respuesta>>({})
  let leccionPendiente = $state(''), errorLeccion = $state('')
  let controlador: AbortController | undefined
  let secuencia = 0
  const sugerencias = ['¿Qué preguntas se repiten más?', '¿Cuáles son las más probables en función de las anteriores?', '¿Qué no debo no saber?', '¿Qué preguntas caerán en la siguiente convocatoria?']
  const seccion = $derived(ruta.startsWith('/documentos') ? 'Biblioteca' : ruta.startsWith('/clase') ? 'Mis clases' : 'Asistente')
  const partesRuta = $derived(ruta.split('/').filter(Boolean))
  const documento = $derived(documentos.find(d => d.id === partesRuta[1]))
  const fragmentoSeleccionado = $derived(partesRuta[2] ?? '')
  const reales = $derived(documentos.filter(d => !d.ficticio))
  const publicaciones = $derived(reales.filter(d => d.origen === 'JCyL'))
  const temas = $derived([...new Set(publicaciones.flatMap(d => d.temas))].filter(t => t !== 'Sin clasificar').sort())
  const temaClase = $derived(partesRuta[0] === 'clase' ? partesRuta[1] ?? '' : '')
  const tipos = $derived([...new Set(documentos.map(d => d.tipo))].sort())
  const anios = $derived([...new Set(documentos.map(d => d.anio))].sort((a, b) => b - a))
  const filtrados = $derived(documentos.filter(d => (!tipo || d.tipo === tipo) && (!anio || d.anio === Number(anio))
    && (procedencia === 'todos' || (procedencia === 'reales' ? !d.ficticio : d.ficticio))
    && (!consulta.trim() || normalizar([d.id, d.titulo, d.procedencia, ...d.temas, ...d.fragmentos.map(f => f.texto)].join(' ')).includes(normalizar(consulta.trim())))))
  const clases = $derived(temas.filter(t => normalizar(t).includes(normalizar(filtroClase))))
  function leerRuta() {
    try { ruta = decodeURIComponent(location.hash.slice(1)) || '/chat' } catch { ruta = '/chat' }
    errorLeccion = ''
    void tick().then(() => {
      const seleccionado = document.getElementById(`fragmento-${fragmentoSeleccionado}`)
      if (seleccionado) seleccionado.scrollIntoView({ block: 'center' })
      else window.scrollTo({ top: 0 })
    })
  }
  function mensajeError(error: unknown): string { return error instanceof Error ? error.message : 'No se ha podido completar la consulta.' }
  async function cargar() {
    cargando = true; errorDatos = ''
    const resultados = await Promise.allSettled([obtenerDocumentos(), obtenerSalud()])
    if (resultados[0].status === 'fulfilled') documentos = resultados[0].value.documentos
    else errorDatos = mensajeError(resultados[0].reason)
    salud = resultados[1].status === 'fulfilled' ? resultados[1].value : null
    cargando = false
    await tick()
    document.getElementById(`fragmento-${fragmentoSeleccionado}`)?.scrollIntoView({ block: 'center' })
  }
  onMount(() => {
    leerRuta(); void cargar(); window.addEventListener('hashchange', leerRuta)
    return () => { window.removeEventListener('hashchange', leerRuta); controlador?.abort() }
  })
  async function enviar(pregunta = texto, reintentar?: number) {
    const contenido = pregunta.trim()
    if (!contenido || contenido.length > 2000 || enviando) return
    const posicion = reintentar === undefined ? turnos.length : turnos.findIndex(t => t.id === reintentar)
    if (posicion < 0) return
    const historial: Mensaje[] = turnos.slice(0, posicion).filter(t => t.respuesta).flatMap(t => [
      { role: 'user' as const, content: t.pregunta }, { role: 'assistant' as const, content: t.respuesta!.respuesta.slice(0, 4000) },
    ]).slice(-20)
    const turno: Turno = { id: reintentar ?? ++secuencia, pregunta: contenido }
    if (reintentar === undefined) { turnos = [...turnos, turno]; texto = '' }
    else turnos = turnos.map(t => t.id === turno.id ? turno : t)
    enviando = true; controlador = new AbortController()
    const peticion = controlador
    const temporizador = window.setTimeout(() => peticion.abort(), 120_000)
    await tick(); document.getElementById('final-chat')?.scrollIntoView({ block: 'end', behavior: 'smooth' })
    try {
      const respuesta = await preguntar(contenido, historial, peticion.signal)
      turnos = turnos.map(t => t.id === turno.id ? { ...t, respuesta } : t)
    } catch (error) {
      const mensaje = peticion.signal.aborted ? 'Consulta detenida. Puedes volver a intentarlo.' : mensajeError(error)
      turnos = turnos.map(t => t.id === turno.id ? { ...t, error: mensaje } : t)
    } finally { window.clearTimeout(temporizador); enviando = false; controlador = undefined }
  }
  function nuevaConversacion() { if (!enviando) { turnos = []; texto = ''; location.hash = '/chat' } }
  function limpiar() { consulta = ''; tipo = ''; anio = ''; procedencia = 'reales' }
  function documentosTema(tema: string) { return publicaciones.filter(d => d.temas.includes(tema)) }
  async function prepararClase(tema: string) {
    if (leccionPendiente) return
    errorLeccion = ''; leccionPendiente = tema
    try {
      const respuesta = await preguntar(`Prepara una clase breve de repaso sobre ${tema} para Técnico de Gestión Informática de JCyL. Usa solo los fragmentos disponibles. Explica conceptos respaldados, identifica turno y convocatoria de las fuentes y propone un ejercicio con solución solo si está acreditada por los datos. Si falta evidencia, indícalo; no inventes explicaciones ni soluciones.`, [])
      lecciones = { ...lecciones, [tema]: respuesta }
    } catch (error) { errorLeccion = mensajeError(error) }
    finally { leccionPendiente = '' }
  }
</script>

<svelte:head><title>{seccion} · Cauce</title><meta name="description" content="Prepara Gestión Informática de JCyL con respuestas basadas en documentos y fuentes verificables." /></svelte:head>
<a class="skip-link" href="#contenido" onclick={e => { e.preventDefault(); document.getElementById('contenido')?.focus() }}>Saltar al contenido</a>
<div class="app-shell">
  <aside class="sidebar" aria-label="Navegación principal">
    <a class="brand" href="#/chat"><span class="brand-symbol" aria-hidden="true">≈</span><span>cauce<small>TU AULA DE OPOSICIONES</small></span></a>
    <p class="eyebrow workspace-label">MI ESPACIO DE ESTUDIO</p>
    <nav>
      <a href="#/chat" class:active={seccion === 'Asistente'} aria-current={seccion === 'Asistente' ? 'page' : undefined}><span aria-hidden="true">◷</span> Asistente</a>
      <a href="#/clases" class:active={seccion === 'Mis clases'} aria-current={seccion === 'Mis clases' ? 'page' : undefined}><span aria-hidden="true">▤</span> Mis clases</a>
      <a href="#/documentos" class:active={seccion === 'Biblioteca'} aria-current={seccion === 'Biblioteca' ? 'page' : undefined}><span aria-hidden="true">▧</span> Biblioteca <span class="nav-count">{cargando ? '…' : documentos.length}</span></a>
    </nav>
    <div class="sidebar-note"><span class="note-art" aria-hidden="true">✧</span><p>Menos memorizar a ciegas.<br /><strong>Más entender el porqué.</strong></p><small>Gestión Informática<br />Junta de Castilla y León</small></div>
    <div class="sidebar-bottom"><span class="avatar">TÚ</span><div>Mi espacio de estudio<small>Sesión local</small></div></div>
  </aside>
  <div class="app-main">
    <header class="app-topbar"><div class="crumbs">Mi aula <span>/</span> <strong>{seccion}</strong></div><span class="pill" class:green={salud?.rag.indice_disponible} class:amber={!salud?.rag.indice_disponible}><span class="dot"></span>{cargando ? 'Conectando' : salud?.rag.indice_disponible ? 'Repositorio disponible' : 'Servicio no disponible'}</span></header>
    <main id="contenido" class="app-body" tabindex="-1">
      {#if errorDatos}<div class="error-box" role="alert"><strong>No se ha podido cargar la biblioteca.</strong><p>{errorDatos}</p><button class="btn secondary" onclick={cargar}>Volver a conectar</button></div>{/if}
      {#if ruta === '/chat' || ruta === '/'}
        <div class="chat-layout"><section class="chat-column" aria-label="Conversación con el asistente">
          <div class="page-title"><div><p class="eyebrow">ESTUDIA CON EVIDENCIAS</p><h1>Pregunta. Conecta. Entiende.</h1><p>Tu histórico de exámenes, convertido en un punto de partida.</p></div>{#if turnos.length}<button class="btn secondary" disabled={enviando} onclick={nuevaConversacion}>Nueva conversación</button>{/if}</div>
          {#if !turnos.length}<div class="chat-welcome"><span class="welcome-symbol" aria-hidden="true">✧</span><h2>¿Por dónde empezamos?</h2><p>Explora los temas del histórico, organiza tu repaso o consulta un concepto. Cada respuesta muestra sus fuentes.</p><div class="starter-grid">{#each sugerencias as sugerencia}<button disabled={enviando} onclick={() => enviar(sugerencia)}>{sugerencia}<span aria-hidden="true">↗</span></button>{/each}</div></div>{/if}
          <div class="chat-messages" aria-label="Mensajes de la conversación">
            {#each turnos as turno (turno.id)}<article class="chat-turn"><div class="user-message"><p>{turno.pregunta}</p><span class="avatar" aria-hidden="true">TÚ</span></div>{#if turno.respuesta}<RespuestaVista respuesta={turno.respuesta} />{:else if turno.error}<div class="error-box" role="alert"><strong>No se ha obtenido una respuesta.</strong><p>{turno.error}</p><button class="btn secondary" disabled={enviando} onclick={() => enviar(turno.pregunta, turno.id)}>Reintentar</button></div>{:else}<div class="loading-answer" role="status"><span class="assistant-mark" aria-hidden="true">✧</span><span>Consultando los documentos…</span></div>{/if}</article>{/each}
          </div>
          <div class="composer-area" id="final-chat"><form class="chat-composer" onsubmit={e => { e.preventDefault(); void enviar() }}><label class="sr-only" for="pregunta">Tu pregunta</label><textarea id="pregunta" bind:value={texto} maxlength="2000" rows="2" placeholder="¿Qué necesitas entender hoy?" disabled={enviando} onkeydown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); void enviar() } }}></textarea>{#if enviando}<button type="button" class="send-button" aria-label="Detener consulta" onclick={() => controlador?.abort()}>■</button>{:else}<button class="send-button" type="submit" aria-label="Enviar pregunta" disabled={!texto.trim()}>↑</button>{/if}</form><p class="composer-note">Enter para enviar · Mayús + Enter para nueva línea · {texto.length}/2000</p><p class="composer-note">Respuestas basadas en el repositorio. Si no hay evidencia, lo indicamos.</p></div>
        </section><aside class="chat-context" aria-label="Contexto de estudio"><div class="context-card"><p class="eyebrow">TU PUNTO DE PARTIDA</p><h2>El histórico, a mano.</h2><div class="context-metric"><strong>{cargando ? '—' : publicaciones.length}</strong><span>documentos oficiales</span></div><p>Cuestionarios, supuestos, programas y plantillas, con su procedencia y fragmentos.</p><div class="context-tags">{#each temas.slice(0, 4) as tema}<span>{tema}</span>{/each}</div><a class="text-link" href="#/documentos">Explorar la biblioteca →</a></div><div class="context-card accent"><span class="note-art" aria-hidden="true">▤</span><h2>Del dato al aprendizaje.</h2><p>Elige un tema y prepara una clase breve a partir de los documentos.</p><a class="text-link" href="#/clases">Ver mis clases →</a></div><p class="context-footnote">Una frecuencia describe la muestra. No predice el siguiente examen.<br /><br />La conversación permanece mientras esta pestaña siga abierta; recargarla inicia una nueva sesión.</p></aside></div>
      {:else if ruta === '/documentos'}
        <div class="page-title"><div><p class="eyebrow">EL PUNTO DE PARTIDA</p><h1>Todo tiene una fuente.</h1><p>Consulta qué documentos y registros utiliza el asistente.</p></div></div>
        <div class="library-stats"><div class="stat-card"><span class="stat-icon">▧</span><div><strong>{publicaciones.length}</strong><span>documentos oficiales</span></div></div><div class="stat-card"><span class="stat-icon green-icon">✓</span><div><strong>{reales.filter(d => d.tipo === 'Registro').length}</strong><span>registros de análisis local</span></div></div><div class="stat-card"><span class="stat-icon">↗</span><div><strong>{publicaciones.filter(d => d.tipo === 'Cuestionario').length}</strong><span>cuestionarios disponibles</span></div></div></div>
        <div class="toolbar"><label class="search-field"><span aria-hidden="true">⌕</span><span class="sr-only">Buscar documentos</span><input bind:value={consulta} placeholder="Buscar por título, tema o contenido…" maxlength="200" type="search" /></label><label><span class="sr-only">Año de referencia</span><select bind:value={anio}><option value="">Todos los años</option>{#each anios as valor}<option value={String(valor)}>{valor}</option>{/each}</select></label><label><span class="sr-only">Procedencia de los datos</span><select bind:value={procedencia}><option value="reales">Datos reales</option><option value="ejemplos">Ejemplos ficticios</option><option value="todos">Todo el catálogo</option></select></label></div>
        <div class="filter-tabs" aria-label="Filtrar por tipo"><button aria-pressed={tipo === ''} onclick={() => tipo = ''}>Todos</button>{#each tipos as valor}<button aria-pressed={tipo === valor} onclick={() => tipo = valor}>{valor}</button>{/each}</div>
        {#if cargando}<p class="empty-state" role="status">Cargando documentos…</p>{:else if filtrados.length}<div class="library-table-wrap"><table class="library-table"><caption class="sr-only">Documentos y registros disponibles</caption><thead><tr><th scope="col">Documento</th><th scope="col">Tipo</th><th scope="col">Año ref.</th><th scope="col">Procedencia</th><th scope="col"><span class="sr-only">Abrir</span></th></tr></thead><tbody>{#each filtrados as doc}<tr><td><a class="library-doc" href={rutaDocumento(doc.id)}><span class="file-icon" aria-hidden="true">▧</span><span><strong>{doc.titulo}</strong><small>{doc.id} · {doc.temas.slice(0, 3).join(' / ')}{doc.ficticio ? ' · Ficticio' : ''}</small></span></a></td><td><span class="pill neutral">{doc.tipo}</span></td><td>{doc.anio}</td><td>{doc.origen}<small>{doc.turno ?? (doc.ficticio ? 'Ejemplo' : 'Análisis local')}</small></td><td><a class="row-open" href={rutaDocumento(doc.id)} aria-label={`Abrir ${doc.titulo}`}>→</a></td></tr>{/each}</tbody></table></div>{:else if !errorDatos}<div class="empty-state"><h2>No encontramos coincidencias.</h2><p>Prueba otro término o elimina algún filtro.</p><button class="btn secondary" onclick={limpiar}>Limpiar búsqueda y filtros</button></div>{/if}
        <div class="table-footer"><span>{filtrados.length} de {documentos.length} registros</span><button class="text-button" onclick={limpiar}>Limpiar filtros</button></div><div class="reference-note">ⓘ Los ejemplos ficticios se conservan como referencia. Con documentación oficial disponible, el asistente consulta los documentos reales y su análisis local. El año es una referencia documental; consulta la ficha para conocer su alcance.</div>
      {:else if partesRuta[0] === 'documentos'}
        {#if cargando}<p class="empty-state" role="status">Cargando ficha…</p>{:else if documento}<div class="page-title"><div><p class="eyebrow">EVIDENCIA A LA VISTA</p><h1>Lee el contexto completo.</h1><p>El fragmento citado y su ubicación dentro del documento.</p></div><a class="btn secondary" href="#/documentos">← Biblioteca</a></div><div class="doc-layout"><article class="doc-sheet"><span class="pill" class:amber={documento.ficticio}>{documento.ficticio ? 'Ejemplo ficticio' : documento.origen === 'JCyL' ? 'Documento oficial' : 'Análisis local'}</span><h2>{documento.titulo}</h2><p class="muted small">{documento.id} · {documento.fragmentos.length} fragmentos</p>{#each documento.fragmentos as fragmento}<section id={`fragmento-${fragmento.id}`} class="document-fragment" class:selected={fragmentoSeleccionado === fragmento.id}><div class="fragment-heading"><h3>{fragmento.ubicacion}</h3><a href={rutaDocumento(documento.id, fragmento.id)} aria-label={`Enlace a ${fragmento.ubicacion}`}>#</a></div><small>{documento.id}:{fragmento.id} · {fragmento.tema}</small><p>{fragmento.texto}</p></section>{/each}<a class="text-link" href="#/chat">Volver al chat →</a></article><aside><div class="context-card"><p class="eyebrow">FICHA DEL REGISTRO</p><dl class="metadata"><dt>Identificador</dt><dd>{documento.id}</dd><dt>Procedencia</dt><dd>{documento.procedencia}</dd><dt>Año de referencia</dt><dd>{documento.anio}</dd>{#if documento.turno}<dt>Turno</dt><dd>{documento.turno}</dd>{/if}{#if documento.fecha_consulta}<dt>Fecha de consulta</dt><dd>{documento.fecha_consulta}</dd>{/if}</dl>{#if enlaceSeguro(documento.url)}<a class="btn light" href={enlaceSeguro(documento.url)} target="_blank" rel="noopener noreferrer">Abrir PDF original ↗</a>{/if}{#if enlaceSeguro(documento.url_ficha)}<a class="text-link" href={enlaceSeguro(documento.url_ficha)} target="_blank" rel="noopener noreferrer">Ficha en la Junta ↗</a>{/if}</div><div class="context-card accent"><h2>Alcance de la fuente</h2><p>{documento.alcance}</p></div></aside></div>{:else}<div class="empty-state"><h1>Documento no disponible.</h1><p>El identificador no aparece en el catálogo cargado.</p><a class="btn secondary" href="#/documentos">Volver a la biblioteca</a></div>{/if}
      {:else if ruta === '/clases'}
        <div class="page-title"><div><p class="eyebrow">DEL DOCUMENTO AL APRENDIZAJE</p><h1>Una clase, un paso más.</h1><p>Elige un tema presente en los documentos y prepara tu sesión de repaso.</p></div><span class="pill neutral">{temas.length} temas disponibles</span></div><div class="study-banner"><span class="welcome-symbol" aria-hidden="true">▤</span><div><h2>Entender primero. Practicar después.</h2><p>Clases a petición con las fuentes que respaldan cada explicación.</p></div></div><label class="search-field course-search"><span aria-hidden="true">⌕</span><span class="sr-only">Buscar tema de clase</span><input type="search" bind:value={filtroClase} placeholder="¿Qué quieres repasar?" /></label>{#if cargando}<p role="status">Cargando temas…</p>{:else if !clases.length}<div class="empty-state"><h2>No hay temas coincidentes.</h2><button class="btn secondary" onclick={() => filtroClase = ''}>Limpiar búsqueda</button></div>{:else}<div class="course-grid">{#each clases as tema, i}<article class="course-card"><div class="course-art" class:alternate={i % 2 === 1}><span aria-hidden="true">{['{ }', '⌘', '▤', '◇'][i % 4]}</span><span class="pill">Repaso con fuentes</span></div><div class="course-content"><p class="eyebrow">{documentosTema(tema).length} DOCUMENTOS RELACIONADOS</p><h2>{tema}</h2><p>Conceptos y práctica a partir del material disponible de Gestión Informática.</p><a class="btn secondary" href={`#/clase/${encodeURIComponent(tema)}`}>{lecciones[tema] ? 'Continuar clase' : 'Preparar clase'} →</a></div></article>{/each}</div>{/if}<div class="reference-note">ⓘ Los temas se agrupan mediante etiquetas orientativas del catálogo. La clase se solicita al servidor al pulsar «Generar sesión» y puede indicar que falta evidencia.</div>
      {:else if partesRuta[0] === 'clase' && temaClase}
        <div class="page-title"><div><p class="eyebrow">APRENDER, PRACTICAR, COMPROBAR</p><h1>{temaClase}</h1><p>Una sesión de estudio apoyada en los documentos.</p></div><a class="btn secondary" href="#/clases">← Mis clases</a></div><div class="doc-layout"><section class="lesson-main"><div class="lesson-intro"><span class="pill">Sesión de repaso</span><h2>Empieza por entender el porqué.</h2><p>Pediremos una explicación breve y un ejercicio cuando las fuentes permitan justificar su solución.</p>{#if !lecciones[temaClase]}<button class="btn" disabled={!!leccionPendiente || !temas.includes(temaClase)} onclick={() => prepararClase(temaClase)}>{leccionPendiente === temaClase ? 'Preparando la clase…' : 'Generar sesión'}</button>{/if}</div>{#if errorLeccion}<div role="alert" class="error-box"><p>{errorLeccion}</p><button class="btn secondary" disabled={!!leccionPendiente} onclick={() => prepararClase(temaClase)}>Reintentar</button></div>{/if}{#if leccionPendiente === temaClase}<p class="loading-answer" role="status">Consultando los fragmentos disponibles…</p>{/if}{#if lecciones[temaClase]}<RespuestaVista respuesta={lecciones[temaClase]} /><div class="actions"><button class="btn secondary" disabled={!!leccionPendiente} onclick={() => prepararClase(temaClase)}>Preparar otra versión</button><a class="btn light" href="#/chat" onclick={() => texto = `Tengo una duda sobre ${temaClase}: `}>Preguntar al asistente →</a></div>{/if}</section><aside><div class="context-card"><p class="eyebrow">MATERIAL DE PARTIDA</p><h2>Fuentes relacionadas</h2><div class="related-docs">{#each documentosTema(temaClase).slice(0, 6) as doc}<a href={rutaDocumento(doc.id)}>{doc.tipo} · {doc.anio}<small>{doc.turno}</small></a>{/each}</div><p class="small">Las fuentes utilizadas en la clase aparecerán bajo la respuesta.</p></div><div class="context-card accent"><h2>Tu criterio cuenta.</h2><p>Comprueba el turno y la convocatoria de cada fuente. Las opciones de un test no acreditan por sí solas su respuesta correcta.</p></div></aside></div>
      {:else}<div class="empty-state"><h1>Página no encontrada.</h1><a class="btn" href="#/chat">Volver al asistente</a></div>{/if}
    </main><footer class="app-footer">Cauce · Aprender con criterio.<span>Gestión Informática · JCyL</span></footer>
  </div>
</div>
