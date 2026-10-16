export interface Fragmento {
  id: string; ubicacion: string; tema: string; texto: string; temas: string[]
}
export interface Documento {
  id: string; titulo: string; tipo: string; anio: number; origen: string
  procedencia: string; temas: string[]; alcance: string; ficticio: boolean
  fragmentos: Fragmento[]; url: string | null; url_ficha: string | null
  fecha_consulta: string | null; convocatoria: string | null; turno: string | null
}
export interface Fuente {
  referencia: string; documento_id: string; titulo: string; fragmento_id: string
  ubicacion: string; fragmento: string; ficticio: boolean; url: string | null
  url_ficha: string | null; turno: string | null
}
export interface Respuesta {
  respuesta: string; fuentes: Fuente[]; no_consta: boolean; modelo_utilizado: boolean
}
export interface Mensaje { role: 'user' | 'assistant'; content: string }
export interface Salud { status: string; rag: { indice_disponible: boolean; modo_oficial: boolean } }

async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  try {
    const respuesta = await fetch(`/api${ruta}`, {
      ...opciones, signal: opciones.signal ?? AbortSignal.timeout(120_000),
    })
    if (!respuesta.ok) {
      const datos = await respuesta.json().catch(() => null)
      throw new Error(datos?.detail?.mensaje ?? `El servidor ha respondido con HTTP ${respuesta.status}. Inténtalo de nuevo.`)
    }
    return await respuesta.json() as T
  } catch (error) {
    if (error instanceof TypeError) throw new Error('No se puede conectar con el servidor. Comprueba que esté arrancado en el puerto 8000.')
    if (error instanceof DOMException && error.name === 'TimeoutError') throw new Error('La consulta ha tardado demasiado. Puedes volver a intentarlo.')
    throw error
  }
}
export const obtenerDocumentos = () => api<{ documentos: Documento[]; total: number }>('/documentos')
export const obtenerSalud = () => api<Salud>('/health', { signal: AbortSignal.timeout(8000) })
export const preguntar = (pregunta: string, historial: Mensaje[], signal?: AbortSignal) => api<Respuesta>('/preguntar', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ pregunta, historial }), signal,
})
export const rutaDocumento = (id: string, fragmento?: string) => `#/documentos/${encodeURIComponent(id)}${fragmento ? `/${encodeURIComponent(fragmento)}` : ''}`
export function enlaceSeguro(url: string | null): string | undefined {
  if (!url) return undefined
  try { return new URL(url).protocol === 'https:' ? url : undefined } catch { return undefined }
}
export function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}
