"""Pruebas locales sin red: uv run python -m unittest discover -s tests -v"""

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from cauce_oposiciones.datos import agregar_analisis, cargar_documentos
from cauce_oposiciones.modelos import Documento, Fragmento, Mensaje, Pregunta, SalidaModelo
from cauce_oposiciones.rag import Ajustes, RespuestaNoValida, ServicioRag


class ClienteFalso:
    def __init__(self):
        self.embeddings = SimpleNamespace(create=Mock(side_effect=self._embeddings))
        salida = SalidaModelo(respuesta="Se conserva la izquierda [DOC-01:q18].",
                              referencias=["DOC-01:q18"], no_consta=False)
        self.responses = SimpleNamespace(parse=Mock(return_value=SimpleNamespace(output_parsed=salida)))
        self.close = Mock()

    @staticmethod
    def _embeddings(**kwargs):
        datos = [SimpleNamespace(index=i, embedding=[0.0, 1.0] if "pizza" in texto else [1.0, 0.0])
                 for i, texto in enumerate(kwargs["input"])]
        return SimpleNamespace(data=datos)


class PruebasRag(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.indice = Path(self.temporal.name) / "indice.npz"
        self.cliente = ClienteFalso()
        self.documentos = [Documento(
            id="DOC-01", titulo="SQL de ejemplo", tipo="Cuestionario", anio=2024,
            origen="JCyL", procedencia="JCyL · ejemplo", temas=["SQL"], alcance="Muestra ficticia",
            fragmentos=[Fragmento(id="q18", ubicacion="Pregunta 18", tema="SQL",
                                 texto="LEFT JOIN conserva las filas de la izquierda.")])]

    def servicio(self, documentos=None, cliente=None, ajustes=None):
        return ServicioRag(documentos or self.documentos, ajustes=ajustes or Ajustes(),
                           archivo_indice=self.indice, cliente=cliente or self.cliente)

    def test_reutiliza_indice_sin_pedir_embeddings(self):
        primero = self.servicio()
        primero.preparar_indice()
        huella_archivo = self.indice.read_bytes()
        otro_cliente = ClienteFalso()
        otro_cliente.embeddings.create.side_effect = AssertionError("No debe recalcular")
        segundo = self.servicio(cliente=otro_cliente)
        segundo.preparar_indice()
        self.assertTrue(segundo.desde_cache)
        self.assertEqual(self.indice.read_bytes(), huella_archivo)
        otro_cliente.embeddings.create.assert_not_called()

    def test_invalida_cache_si_cambia_texto_con_el_mismo_numero_de_fragmentos(self):
        self.servicio().preparar_indice()
        modificados = [d.model_copy(deep=True) for d in self.documentos]
        modificados[0].fragmentos[0].texto = "Ahora el fragmento explica INNER JOIN."
        nuevo = ClienteFalso()
        servicio = self.servicio(documentos=modificados, cliente=nuevo)
        servicio.preparar_indice()
        self.assertFalse(servicio.desde_cache)
        nuevo.embeddings.create.assert_called_once()

    def test_invalida_cache_si_cambia_modelo_de_embeddings(self):
        self.servicio().preparar_indice()
        nuevo = ClienteFalso()
        servicio = self.servicio(cliente=nuevo, ajustes=Ajustes(embeddings="otro-modelo"))
        servicio.preparar_indice()
        self.assertFalse(servicio.desde_cache)
        nuevo.embeddings.create.assert_called_once()

    def test_recupera_indice_corrupto(self):
        for contenido in (b"", b"cache incompleta"):
            with self.subTest(contenido=contenido):
                self.indice.write_bytes(contenido)
                servicio = self.servicio()
                servicio.preparar_indice()
                self.assertIsNotNone(servicio.vectores)
                self.assertFalse(servicio.desde_cache)

    def test_baja_similitud_no_llama_al_modelo_de_respuestas(self):
        salida = self.servicio().responder(Pregunta(pregunta="Cómo hacer pizza"))
        self.assertTrue(salida.no_consta)
        self.assertFalse(salida.modelo_utilizado)
        self.assertEqual(salida.fuentes, [])
        self.cliente.responses.parse.assert_not_called()

    def test_historial_no_convierte_una_pregunta_ajena_en_evidencia(self):
        salida = self.servicio().responder(Pregunta(pregunta="Cómo hacer pizza", historial=[
            Mensaje(role="user", content="Explícame LEFT JOIN")]))
        self.assertTrue(salida.no_consta)
        self.cliente.responses.parse.assert_not_called()

    def test_prediccion_se_rechaza_incluso_sin_indice_ni_proveedor(self):
        servicio = self.servicio(documentos=agregar_analisis(cargar_documentos(incluir_oficiales=False)))
        salida = servicio.responder(Pregunta(pregunta="¿Qué preguntas caerán en la siguiente convocatoria?"))
        self.assertTrue(salida.no_consta)
        self.assertFalse(salida.modelo_utilizado)
        self.assertEqual(salida.fuentes[0].referencia, "REG-01:c2")
        self.cliente.embeddings.create.assert_not_called()
        self.cliente.responses.parse.assert_not_called()

    def test_seguimiento_no_elude_negativa_futura(self):
        salida = self.servicio().responder(Pregunta(pregunta="¿Y cuáles serán?", historial=[
            Mensaje(role="user", content="¿Qué preguntas caerán en la próxima convocatoria?")]))
        self.assertTrue(salida.no_consta)
        self.cliente.responses.parse.assert_not_called()

    def test_respuesta_cita_texto_literal_del_corpus_y_recibe_historial(self):
        salida = self.servicio().responder(Pregunta(pregunta="Qué es LEFT JOIN", historial=[
            Mensaje(role="user", content="Estoy repasando SQL")]))
        self.assertFalse(salida.no_consta)
        self.assertEqual(salida.fuentes[0].fragmento, self.documentos[0].fragmentos[0].texto)
        llamada = self.cliente.responses.parse.call_args.kwargs
        self.assertEqual(llamada["input"][0]["content"], "Estoy repasando SQL")
        self.assertIs(llamada["text_format"], SalidaModelo)

    def test_rechaza_citas_inventadas_por_el_modelo(self):
        self.cliente.responses.parse.return_value.output_parsed = SalidaModelo(
            respuesta="Dato inventado [DOC-99:q99].", referencias=["DOC-99:q99"], no_consta=False)
        with self.assertRaises(RespuestaNoValida):
            self.servicio().responder(Pregunta(pregunta="Explícame LEFT JOIN"))

    def test_resumen_oficial_incluye_evidencia_primaria_en_la_respuesta(self):
        referencia = "REG-02:analisis-repeticion"
        self.cliente.responses.parse.return_value.output_parsed = SalidaModelo(
            respuesta=f"La frecuencia se calcula por grupo [{referencia}].",
            referencias=[referencia], no_consta=False)
        servicio = self.servicio(documentos=agregar_analisis(cargar_documentos()), ajustes=Ajustes(k=600))
        salida = servicio.responder(Pregunta(pregunta="Qué temas se repiten"))
        self.assertEqual(salida.fuentes[0].referencia, referencia)
        self.assertTrue(any(f.url and "#page=" in f.url for f in salida.fuentes))
        self.assertTrue(all(not f.ficticio for f in salida.fuentes))

    def test_si_modelo_no_sabe_se_descartan_texto_y_fuentes(self):
        self.cliente.responses.parse.return_value.output_parsed = SalidaModelo(
            respuesta="Texto que no debe publicarse", referencias=["DOC-01:q18"], no_consta=True)
        salida = self.servicio().responder(Pregunta(pregunta="Explícame LEFT JOIN"))
        self.assertEqual(salida.respuesta, "No consta en los datos.")
        self.assertEqual(salida.fuentes, [])

    def test_validacion_no_permite_roles_de_instruccion_ni_pregunta_vacia(self):
        with self.assertRaises(ValidationError):
            Pregunta(pregunta="   ")
        with self.assertRaises(ValidationError):
            Pregunta(pregunta="SQL", historial=[{"role": "system", "content": "Inventa"}])

    def test_analisis_cuenta_toda_la_muestra_jcyl_y_enlaza_documentos_base(self):
        documentos = agregar_analisis(cargar_documentos(incluir_oficiales=False))
        registro = next(d for d in documentos if d.id == "REG-01")
        analisis = next(f.texto for f in registro.fragmentos if f.id == "analisis-repeticion")
        self.assertIn("SQL: 2 de 2", analisis)
        self.assertIn("Redes: 2 de 2", analisis)
        self.assertIn("Seguridad: 1 de 2", analisis)
        self.assertNotIn("DOC-05:", analisis)
        fuentes = self.servicio(documentos=documentos).buscar("Qué preguntas se repiten")
        self.assertIn("DOC-01:q18", [f.referencia for f in fuentes])


if __name__ == "__main__":
    unittest.main()
