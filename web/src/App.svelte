<script lang="ts">
  import { onMount } from 'svelte'

  let status = $state<'loading' | 'ok' | 'error'>('loading')
  let message = $state('Conectando con el servidor Python…')

  async function checkApi(): Promise<void> {
    status = 'loading'
    message = 'Conectando con el servidor Python…'
    try {
      const response = await fetch('/api/health', {
        signal: AbortSignal.timeout(5000),
      })
      if (!response.ok) throw new Error(`La API ha respondido con HTTP ${response.status}.`)
      const data: { status: string; service: string } = await response.json()
      if (data.status !== 'ok' || data.service !== 'cauce-oposiciones') {
        throw new Error('La respuesta no corresponde a la API de Cauce.')
      }
      status = 'ok'
      message = 'La interfaz y el servidor Python están conectados.'
    } catch (error) {
      status = 'error'
      message = 'No se puede conectar con la API. Comprueba que FastAPI esté arrancado en el puerto 8000.'
      console.error('No se ha podido comprobar /api/health:', error)
    }
  }

  onMount(() => { void checkApi() })
</script>

<svelte:head>
  <title>Cauce · Entorno de desarrollo</title>
</svelte:head>

<main>
  <header>
    <a class="brand" href="/" aria-label="Cauce, inicio">
      <span class="brand-icon" aria-hidden="true">≈</span> cauce
    </a>
    <span class="environment">Entorno local</span>
  </header>

  <section class="welcome" aria-labelledby="welcome-title">
    <p class="eyebrow">AULA DE OPOSICIONES TIC</p>
    <h1 id="welcome-title">Una base lista para construir.</h1>
    <p class="description">Preparación de Técnico/a de Gestión Informática de la Junta de Castilla y León.</p>

    <div class="connection" class:connected={status === 'ok'} class:failed={status === 'error'} role="status" aria-live="polite">
      <span class="status-dot" aria-hidden="true"></span>
      <div>
        <h2>{status === 'ok' ? 'API conectada' : status === 'error' ? 'API no disponible' : 'Comprobando conexión'}</h2>
        <p>{message}</p>
      </div>
    </div>

    <div class="actions">
      <button type="button" onclick={checkApi} disabled={status === 'loading'}>Comprobar conexión</button>
      {#if status === 'ok'}
        <a class="secondary" href="/api/maquetas" target="_blank" rel="noopener noreferrer">Abrir maquetas ↗</a>
      {:else}
        <span class="hint">Las maquetas estarán disponibles al conectar la API.</span>
      {/if}
    </div>
    <p class="footnote">Esta pantalla verifica la instalación. Las seis pantallas de la aplicación siguen en <code>maquetas.html</code>.</p>
  </section>

  <footer>FastAPI + uv · Svelte + TypeScript + Vite</footer>
</main>
