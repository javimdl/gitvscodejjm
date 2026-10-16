<script lang="ts">
  import { rutaDocumento, type Fuente } from './api'
  let { texto, fuentes }: { texto: string; fuentes: Fuente[] } = $props()
  type Bloque = { tipo: 'parrafo' | 'titulo' | 'lista' | 'codigo'; lineas: string[] }
  const bloques = $derived.by(() => {
    const resultado: Bloque[] = []
    let codigo = false
    for (const linea of texto.split('\n')) {
      if (/^\s*```/.test(linea)) { codigo = !codigo; if (codigo) resultado.push({ tipo: 'codigo', lineas: [] }); continue }
      if (codigo) { resultado.at(-1)!.lineas.push(linea); continue }
      if (!linea.trim()) { resultado.push({ tipo: 'parrafo', lineas: [] }); continue }
      const titulo = /^#{1,6}\s+(.+)$/.exec(linea)
      const lista = /^\s*(?:[-*]|\d+[.)])\s+(.+)$/.exec(linea)
      if (titulo) resultado.push({ tipo: 'titulo', lineas: [titulo[1]!] })
      else if (lista) {
        const anterior = resultado.at(-1)
        if (anterior?.tipo === 'lista') anterior.lineas.push(lista[1]!)
        else resultado.push({ tipo: 'lista', lineas: [lista[1]!] })
      } else {
        const anterior = resultado.at(-1)
        if (anterior?.tipo === 'parrafo') anterior.lineas.push(linea)
        else resultado.push({ tipo: 'parrafo', lineas: [linea] })
      }
    }
    return resultado.filter(b => b.lineas.length)
  })
</script>

{#snippet enLinea(contenido: string)}
  {#each contenido.split(/(\[(?:DOC|REG)-[^\]\s]+\]|\*\*[^*]+\*\*|`[^`]+`)/g) as parte}{@const fuente = parte.startsWith('[') ? fuentes.find(f => f.referencia === parte.slice(1, -1)) : undefined}{#if fuente}<a class="citation" href={rutaDocumento(fuente.documento_id, fuente.fragmento_id)} title={fuente.titulo}>{parte}</a>{:else if parte.startsWith('**') && parte.endsWith('**')}<strong>{parte.slice(2, -2)}</strong>{:else if parte.startsWith('`') && parte.endsWith('`')}<code>{parte.slice(1, -1)}</code>{:else}{parte}{/if}{/each}
{/snippet}
<div class="answer-text">
  {#each bloques as bloque}
    {#if bloque.tipo === 'titulo'}<h3>{@render enLinea(bloque.lineas[0]!)}</h3>
    {:else if bloque.tipo === 'lista'}<ul>{#each bloque.lineas as linea}<li>{@render enLinea(linea)}</li>{/each}</ul>
    {:else if bloque.tipo === 'codigo'}<pre><code>{bloque.lineas.join('\n')}</code></pre>
    {:else}<p>{@render enLinea(bloque.lineas.join('\n'))}</p>{/if}
  {/each}
</div>
