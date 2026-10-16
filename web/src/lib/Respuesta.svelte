<script lang="ts">
  import { enlaceSeguro, rutaDocumento, type Respuesta } from './api'
  import TextoRespuesta from './TextoRespuesta.svelte'
  let { respuesta }: { respuesta: Respuesta } = $props()
  let todas = $state(false)
  const visibles = $derived(todas ? respuesta.fuentes : respuesta.fuentes.slice(0, 4))
</script>

<div class="assistant-message">
  <span class="assistant-mark" aria-hidden="true">✧</span>
  <div class="answer">
    <div class="answer-heading">Cauce <span class:amber={respuesta.no_consta} class="pill green">{respuesta.no_consta ? 'Sin evidencia suficiente' : 'Con fuentes'}</span></div>
    {#if respuesta.no_consta}
      <div class="no-data" role="status"><strong>ⓘ No consta en los datos.</strong><p>{respuesta.respuesta}</p></div>
      <p class="muted small">Podemos revisar el histórico o consultar los documentos disponibles. Una prioridad de repaso no equivale a una predicción.</p>
    {:else}
      <TextoRespuesta texto={respuesta.respuesta} fuentes={respuesta.fuentes} />
    {/if}
    {#if respuesta.fuentes.length}
      <div class="sources">
        <h3 class="sources-label">↗ {respuesta.no_consta ? 'Registro que delimita la respuesta' : 'Fuentes que justifican la respuesta'} · {respuesta.fuentes.length}</h3>
        <div class="source-grid">
          {#each visibles as fuente (fuente.referencia)}
            <article class="source-card">
              <a class="source-title" href={rutaDocumento(fuente.documento_id, fuente.fragmento_id)}>{fuente.titulo}</a>
              <p class="source-location">{fuente.referencia} · {fuente.ubicacion}</p>
              <p class="source-quote">«{fuente.fragmento.length > 260 ? fuente.fragmento.slice(0, 260) + '…' : fuente.fragmento}»</p>
              <div class="source-actions"><a href={rutaDocumento(fuente.documento_id, fuente.fragmento_id)}>Ver fragmento completo →</a>{#if enlaceSeguro(fuente.url)}<a href={enlaceSeguro(fuente.url)} target="_blank" rel="noopener noreferrer">PDF ↗</a>{/if}</div>
              {#if fuente.ficticio}<span class="pill amber">Ejemplo ficticio</span>{/if}
            </article>
          {/each}
        </div>
        {#if respuesta.fuentes.length > 4}<button class="text-button" type="button" onclick={() => todas = !todas}>{todas ? 'Mostrar menos fuentes' : `Ver las ${respuesta.fuentes.length} fuentes`}</button>{/if}
      </div>
    {/if}
    {#if respuesta.no_consta}<div class="actions"><a class="btn secondary" href="#/documentos">Consultar biblioteca</a><a class="btn light" href="#/clases">Elegir una clase</a></div>{/if}
  </div>
</div>
