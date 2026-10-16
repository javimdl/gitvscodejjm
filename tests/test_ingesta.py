"""Verificaciones del corpus oficial y del aislamiento frente a las maquetas."""

import hashlib
import unittest

from cauce_oposiciones.datos import RAIZ, agregar_analisis, cargar_documentos
from cauce_oposiciones.ingesta_jcyl import extraer_fragmentos
from cauce_oposiciones.modelos import Pregunta
from cauce_oposiciones.rag import ServicioRag


class PruebasIngesta(unittest.TestCase):
    def test_numeracion_y_separacion_de_supuestos(self):
        paginas = ["1.- ¿Qué instrucción SQL se utiliza?\na) SELECT\nb) Otra opción\n"
                   "Primer supuesto práctico\nUna aplicación debe autenticar usuarios mediante JWT.\n"
                   "2.- ¿Qué mecanismo utiliza?\na) Firma\nb) Otra opción"]
        fragmentos = extraer_fragmentos(paginas, "Cuestionario")
        pregunta = next(f for f in fragmentos if f.id == "q1-1")
        practica = next(f for f in fragmentos if f.id == "q2-1")
        self.assertEqual(pregunta.clase, "pregunta")
        self.assertEqual(practica.clase, "practico")
        self.assertIn("SQL", pregunta.temas)
        self.assertEqual(pregunta.pagina_inicio, 1)
        self.assertNotIn("Primer supuesto", pregunta.texto)

    def test_sin_opciones_conserva_texto_sin_inventar_preguntas(self):
        fragmentos = extraer_fragmentos(["1. Desarrolle un sistema de información para una oficina pública."], "Cuestionario")
        self.assertTrue(fragmentos)
        self.assertTrue(all(f.clase == "texto" for f in fragmentos))

    def test_oficiales_conservan_original_y_fuentes(self):
        documentos = cargar_documentos()
        oficiales = [d for d in documentos if not d.ficticio and d.origen == "JCyL"]
        self.assertGreaterEqual(len(oficiales), 16)
        self.assertTrue(any(d.ficticio for d in documentos))
        for d in oficiales:
            with self.subTest(documento=d.id):
                raw = (RAIZ / "datos/jcyl/originales" / f"{d.id}.pdf").read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), d.sha256)
                self.assertTrue(d.url.startswith("https://empleopublico.jcyl.es/"))
                self.assertTrue(all(f.pagina_inicio for f in d.fragmentos))

    def test_rag_oficial_excluye_ejemplos_y_negativa_sin_cliente(self):
        servicio = ServicioRag(agregar_analisis(cargar_documentos()))
        self.assertTrue(servicio.modo_oficial)
        self.assertTrue(all(not f.ficticio for f in servicio.fragmentos))
        fuente = next(f for f in servicio.fragmentos if f.documento_id == "DOC-111")
        self.assertIn("#page=", fuente.url)
        self.assertEqual(fuente.turno, "Libre")
        salida = servicio.responder(Pregunta(pregunta="Qué preguntas caerán en la siguiente convocatoria"))
        self.assertFalse(salida.modelo_utilizado)
        self.assertEqual(salida.fuentes[0].referencia, "REG-02:c2")

    def test_recuentos_no_cambian_al_duplicar_un_modelo_del_mismo_examen(self):
        documentos = cargar_documentos()
        copia = next(d for d in documentos if d.id == "DOC-111").model_copy(deep=True)
        copia.id = "DOC-999"
        con_copia = agregar_analisis([*documentos, copia])
        registro = next(d for d in con_copia if d.id == "REG-02")
        texto = next(f.texto for f in registro.fragmentos if f.id == "analisis-repeticion")
        self.assertIn("2 grupos de examen", texto)
        self.assertNotIn("DOC-01:", texto)
        self.assertNotIn("DOC-999:", texto)


if __name__ == "__main__":
    unittest.main()
