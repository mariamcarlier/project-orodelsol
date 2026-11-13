"""La portada de una colección son dos archivos: el original y su versión optimizada.

`Coleccion.imagen` guarda el original limpio e `imagen_detalle` la versión
optimizada (WebP) que enseña la tienda. Qué se comprueba aquí:

- `imagen_detalle` es siempre la versión de la `imagen` guardada, también
  cuando la portada se cambia sin pasar por el formulario. Lo mantiene
  `Coleccion.save()` (ver `core/portadas.py`).
- Una portada que solo tiene `imagen` —como las guardadas antes de la migración
  0010— se sigue viendo y sus archivos se limpian igual.
- Los fallos parciales: qué pasa cuando uno solo de los dos archivos no se deja
  borrar o escribir.

Lo demás de la portada (subir, sustituir, quitar, eliminar y las pantallas) está
en `core/test_portada_coleccion.py`, de donde salen también las utilidades.
"""

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.urls import reverse

from . import portadas
from .imagenes import procesar_imagen
from .models import Coleccion
from .test_portada_coleccion import (
    OTRO_COLOR,
    QUITAR,
    RUTA_DEL_DETALLE,
    RUTA_DEL_ORIGINAL,
    URL_EXTERNA,
    _Base,
    archivos_de,
    es_derivado,
    es_original,
    falla_solo_con,
    formulario,
)
from .test_servicio_galeria import foto


# ---------------------------------------------------------------------------
# La versión optimizada es siempre la de la portada guardada
# ---------------------------------------------------------------------------


class VersionOptimizadaTests(_Base):
    """`imagen_detalle` depende de `imagen`; lo mantiene `Coleccion.save()`."""

    def setUp(self):
        super().setUp()
        self.coleccion = self.con_portada()
        self.anteriores = archivos_de(self.coleccion)
        self.assertEqual(len(self.anteriores), 2)

    def en_la_base(self):
        return archivos_de(Coleccion.objects.get(pk=self.coleccion.pk))

    def guardar_objeto(self, **opciones):
        """Guarda sin formulario; al volver, la transacción ya se confirmó."""
        with self.captureOnCommitCallbacks(execute=True):
            self.coleccion.save(**opciones)

    def test_al_sustituir_cambian_los_dos_archivos(self):
        nueva = foto(color=OTRO_COLOR)
        esperado = procesar_imagen(nueva)
        nueva.seek(0)

        self.guardar(formulario(self.coleccion, archivo=nueva))

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual(self.contenido(guardada.imagen.name), esperado.original)
        self.assertEqual(self.contenido(guardada.imagen_detalle.name), esperado.detalle)
        self.assertEqual(set(self.en_la_base()) & set(self.anteriores), set())

    def test_al_quitar_la_portada_se_vacian_los_dos_campos(self):
        self.guardar(formulario(self.coleccion, **QUITAR))

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual((guardada.imagen.name, guardada.imagen_detalle.name), ("", ""))
        self.assertEqual(guardada.imagen_catalogo, "")

    def test_cambiar_el_original_por_otra_via_no_deja_la_version_de_la_anterior(self):
        # Sin formulario no hay versión optimizada nueva. Dejar la que había
        # sería enseñar en la tienda la portada ANTERIOR.
        self.coleccion.imagen = ContentFile(b"otra portada", name="otra.webp")

        self.guardar_objeto()

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual(guardada.imagen_detalle.name, "")
        self.assertEqual(guardada.imagen_catalogo, guardada.imagen.url)  # se ve el original
        self.assertEqual(self.archivos(), [guardada.imagen.name])  # y las dos anteriores se borran

    def test_un_archivo_nuevo_que_se_llama_como_el_guardado_tambien_cuenta_como_otra_portada(self):
        # Lo que decide no es el nombre que trae el archivo, sino que es una subida nueva.
        self.coleccion.imagen = ContentFile(b"otra portada", name=self.coleccion.imagen.name)

        self.guardar_objeto()

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual(guardada.imagen_detalle.name, "")
        self.assertEqual(self.contenido(guardada.imagen.name), b"otra portada")
        self.assertEqual(self.archivos(), [guardada.imagen.name])

    def test_una_subida_del_formulario_manda_sobre_un_objeto_atrasado(self):
        # Dos personas abren la misma colección. La primera cambia la portada; la
        # segunda, que aún tiene en memoria la portada de antes, sube otra.
        atrasada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.guardar(formulario(self.coleccion, archivo=foto(color=OTRO_COLOR)))
        ultima = foto(color=(1, 2, 3))
        esperado = procesar_imagen(ultima)
        ultima.seek(0)

        self.guardar(formulario(atrasada, archivo=ultima))

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual(self.contenido(guardada.imagen.name), esperado.original)
        self.assertEqual(self.contenido(guardada.imagen_detalle.name), esperado.detalle)
        self.assertEqual(self.archivos(), archivos_de(guardada))  # nada suelto, nada roto

    def test_apuntar_a_otro_archivo_ya_guardado_tambien_vacia_la_version_optimizada(self):
        otro = default_storage.save("colecciones/" + "a" * 32 + ".jpg", ContentFile(b"x"))
        self.coleccion.imagen = otro

        self.guardar_objeto()

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual((guardada.imagen.name, guardada.imagen_detalle.name), (otro, ""))
        self.assertEqual(self.archivos(), [otro])

    def test_quien_guarda_puede_traer_su_propia_version_optimizada(self):
        self.coleccion.imagen = ContentFile(b"original nuevo", name="otra.png")
        self.coleccion.imagen_detalle = ContentFile(b"detalle nuevo", name="otra.webp")

        self.guardar_objeto()

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertTrue(RUTA_DEL_ORIGINAL.fullmatch(guardada.imagen.name), guardada.imagen.name)
        self.assertTrue(RUTA_DEL_DETALLE.fullmatch(guardada.imagen_detalle.name))
        self.assertEqual(self.contenido(guardada.imagen_detalle.name), b"detalle nuevo")
        self.assertEqual(self.archivos(), archivos_de(guardada))

    def test_la_version_que_trae_quien_guarda_vale_aunque_se_llame_como_la_guardada(self):
        nombre_guardado = self.coleccion.imagen_detalle.name
        self.coleccion.imagen = ContentFile(b"original nuevo", name="otra.png")
        self.coleccion.imagen_detalle = ContentFile(b"detalle nuevo", name=nombre_guardado)

        self.guardar_objeto()

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual(self.contenido(guardada.imagen_detalle.name), b"detalle nuevo")
        self.assertEqual(self.archivos(), archivos_de(guardada))

    def test_se_puede_regenerar_solo_la_version_optimizada(self):
        original, detalle_anterior = self.coleccion.imagen.name, self.coleccion.imagen_detalle.name
        self.coleccion.imagen_detalle = ContentFile(b"regenerada", name="detalle.webp")

        self.guardar_objeto(update_fields=["imagen_detalle"])

        guardada = Coleccion.objects.get(pk=self.coleccion.pk)
        self.assertEqual(guardada.imagen.name, original)  # el original no se toca
        self.assertNotEqual(guardada.imagen_detalle.name, detalle_anterior)
        self.assertEqual(self.archivos(), archivos_de(guardada))

    def test_guardar_solo_la_portada_guarda_tambien_su_version_optimizada(self):
        self.coleccion.imagen = ""

        self.guardar_objeto(update_fields=["imagen"])

        self.assertEqual(self.en_la_base(), [])  # no quedó una versión optimizada sin original
        self.assertEqual(self.archivos(), [])

    def test_guardar_solo_otros_campos_no_consulta_ni_programa_nada(self):
        self.coleccion.temporada = "2027"

        with self.captureOnCommitCallbacks(execute=True) as pendientes:
            with self.assertNumQueries(1):  # solo el UPDATE
                self.coleccion.save(update_fields=["temporada"])

        self.assertEqual(pendientes, [])
        self.assertEqual(self.en_la_base(), self.anteriores)

    def test_una_version_optimizada_sin_original_no_cuenta_como_portada(self):
        suelta = Coleccion(
            nombre="Suelta", imagen_detalle="colecciones/derivados/a.webp", imagen_url=URL_EXTERNA
        )
        self.assertEqual(suelta.imagen_catalogo, URL_EXTERNA)

        suelta.save()

        suelta.refresh_from_db()
        self.assertEqual(suelta.imagen_detalle.name, "")

    def test_el_formulario_ensena_la_version_optimizada_no_el_original(self):
        campo = str(formulario(self.coleccion)["imagen"])

        self.assertIn(f'<img src="{self.coleccion.imagen_detalle.url}"', campo)
        self.assertNotIn(self.coleccion.imagen.url, campo)


class PortadaSinVersionOptimizadaTests(_Base):
    """Portadas que solo tienen `imagen`.

    Es como queda una portada guardada cuando `imagen_detalle` aún no existía
    (antes de la migración 0010): un único archivo en `colecciones/`.
    """

    def setUp(self):
        super().setUp()
        self.archivo = default_storage.save(
            "colecciones/" + "b" * 32 + ".webp", ContentFile(foto().read())
        )
        self.coleccion = Coleccion.objects.create(nombre="Alma Dorada", imagen=self.archivo)
        self.assertEqual(self.archivos(), [self.archivo])

    def test_la_tienda_la_sigue_ensenando(self):
        self.assertEqual(self.coleccion.imagen_catalogo, self.coleccion.imagen.url)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertContains(respuesta, f'<img src="{self.coleccion.imagen.url}"')

    def test_el_formulario_la_ensena_y_permite_quitarla(self):
        campo = str(formulario(self.coleccion)["imagen"])

        self.assertIn(f'<img src="{self.coleccion.imagen.url}"', campo)
        self.assertIn('name="imagen-clear"', campo)

    def test_guardar_otros_datos_la_deja_como_esta(self):
        self.guardar(formulario(self.coleccion, temporada="2027"))

        self.coleccion.refresh_from_db()
        self.assertEqual(archivos_de(self.coleccion), [self.archivo])
        self.assertEqual(self.archivos(), [self.archivo])

    def test_al_sustituirla_se_borra_y_la_nueva_ya_tiene_los_dos_archivos(self):
        self.guardar(formulario(self.coleccion, archivo=foto(color=OTRO_COLOR)))

        self.coleccion.refresh_from_db()
        self.assertEqual(len(archivos_de(self.coleccion)), 2)
        self.assertEqual(self.archivos(), archivos_de(self.coleccion))

    def test_al_quitarla_se_borra_su_archivo(self):
        self.guardar(formulario(self.coleccion, **QUITAR))

        self.assertEqual(self.archivos(), [])

    def test_al_eliminar_la_coleccion_se_borra_su_archivo(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.coleccion.delete()

        self.assertEqual(self.archivos(), [])


# ---------------------------------------------------------------------------
# Fallos parciales: uno de los dos archivos no se deja borrar o escribir
# ---------------------------------------------------------------------------


class FallosParcialesTests(_Base):
    def setUp(self):
        super().setUp()
        self.coleccion = self.con_portada()
        self.coleccion_id = self.coleccion.pk  # delete() lo borra del objeto en memoria
        self.original = self.coleccion.imagen.name
        self.detalle = self.coleccion.imagen_detalle.name
        self.almacenamiento = Coleccion._meta.get_field("imagen").storage

    def en_la_base(self):
        return archivos_de(Coleccion.objects.get(pk=self.coleccion_id))

    def quitar_fallando_con(self, condicion, error, registro="core.portadas"):
        form = formulario(self.coleccion, **QUITAR)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        with falla_solo_con(self.almacenamiento, "delete", condicion, error):
            with self.assertLogs(registro, level="ERROR") as anotado:
                with self.captureOnCommitCallbacks(execute=True):
                    form.save()  # no debe lanzar
        return "\n".join(anotado.output)

    def test_si_el_original_no_se_deja_borrar_la_version_optimizada_si_se_borra(self):
        registro = self.quitar_fallando_con(es_original, PermissionError(13, "En uso"))

        self.assertEqual(self.en_la_base(), [])  # la portada se quitó igualmente
        self.assertEqual(self.archivos(), [self.original])
        self.assertIn(self.original, registro)  # el registro dice cuál quedó

    def test_si_la_version_optimizada_no_se_deja_borrar_el_original_si_se_borra(self):
        registro = self.quitar_fallando_con(es_derivado, PermissionError(13, "En uso"))

        self.assertEqual(self.en_la_base(), [])
        self.assertEqual(self.archivos(), [self.detalle])
        self.assertIn(self.detalle, registro)

    def test_un_error_que_nadie_previo_en_un_archivo_no_impide_borrar_el_otro(self):
        # No es un `OSError`: lo recoge `on_commit(robust=True)` y lo anota Django
        # (aquí, quien ejecuta lo programado es `captureOnCommitCallbacks`).
        inesperado = RuntimeError("el almacenamiento respondió algo que nadie previó")

        self.quitar_fallando_con(es_original, inesperado, registro="django.test")

        self.assertEqual(self.en_la_base(), [])
        self.assertEqual(self.archivos(), [self.original])

    def test_al_sustituir_la_portada_nueva_queda_bien_aunque_una_anterior_no_se_borre(self):
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())

        en_uso = PermissionError(13, "En uso")
        with falla_solo_con(self.almacenamiento, "delete", lambda n: n == self.detalle, en_uso):
            with self.assertLogs("core.portadas", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    form.save()

        nuevas = self.en_la_base()
        self.assertEqual(len(nuevas), 2)
        self.assertEqual(self.archivos(), sorted([*nuevas, self.detalle]))

    def test_al_eliminar_la_coleccion_se_elimina_aunque_un_archivo_no_se_deje_borrar(self):
        with falla_solo_con(
            self.almacenamiento, "delete", es_derivado, PermissionError(13, "En uso")
        ):
            with self.assertLogs("core.portadas", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    self.coleccion.delete()  # no debe lanzar

        self.assertFalse(Coleccion.objects.filter(pk=self.coleccion_id).exists())
        self.assertEqual(self.archivos(), [self.detalle])

    def test_un_archivo_que_quedo_suelto_se_puede_borrar_despues(self):
        self.quitar_fallando_con(es_original, PermissionError(13, "En uso"))
        self.assertEqual(self.archivos(), [self.original])

        borrado = portadas.borrar_si_nadie_la_usa(Coleccion, self.original)  # ya sin el fallo

        self.assertTrue(borrado)
        self.assertEqual(self.archivos(), [])

    def test_si_la_version_optimizada_no_se_puede_escribir_no_queda_medio_guardada(self):
        anteriores = [self.detalle, self.original]
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with falla_solo_con(self.almacenamiento, "save", es_derivado, OSError(28, "Disco lleno")):
            with self.assertRaises(OSError), transaction.atomic():
                form.save()

        # El original nuevo, que sí se había escrito, se borra…
        self.assertEqual(self.archivos(), sorted(anteriores))
        self.assertEqual(self.en_la_base(), sorted(anteriores))
        # …y el objeto vuelve entero a la portada guardada: un reintento no mezcla
        # el original de una portada con la versión optimizada de otra.
        self.assertEqual(archivos_de(self.coleccion), sorted(anteriores))

    def guardado_rechazado_sin_poder_descartar(self, cual, error):
        """La base rechaza el guardado y, al descartar, el archivo nuevo `cual` falla con `error`.

        `cual` es `es_original` o `es_derivado`. Devuelve el objeto que se intentó guardar.
        """
        anteriores = (self.original, self.detalle)
        Coleccion.objects.create(nombre="Repetida")
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())
        coleccion = form.save(commit=False)
        coleccion.nombre = "Repetida"  # choca con el nombre único

        def el_nuevo(nombre):
            return cual(nombre) and nombre not in anteriores

        with falla_solo_con(self.almacenamiento, "delete", el_nuevo, error):
            with self.assertLogs("core.portadas", level="ERROR"):
                # Quien guarda recibe el error del guardado, no el del almacenamiento.
                with self.assertRaises(IntegrityError), transaction.atomic():
                    coleccion.save()
        return coleccion

    def assertSoloQuedoSuelto(self, cual, coleccion):
        anteriores = sorted([self.detalle, self.original])
        # El otro archivo nuevo sí se descartó; este queda suelto (y anotado).
        (suelto,) = set(self.archivos()) - set(anteriores)
        self.assertTrue(cual(suelto), suelto)
        # El objeto no se queda apuntando a un archivo que ya no existe.
        self.assertEqual(archivos_de(coleccion), anteriores)
        self.assertEqual(self.en_la_base(), anteriores)

    def test_si_falla_el_guardado_y_el_original_nuevo_no_se_deja_borrar_el_objeto_no_se_rompe(self):
        coleccion = self.guardado_rechazado_sin_poder_descartar(
            es_original, PermissionError(13, "En uso")
        )

        self.assertSoloQuedoSuelto(es_original, coleccion)

    def test_si_falla_el_guardado_y_el_detalle_nuevo_no_se_deja_borrar_el_objeto_no_se_rompe(self):
        coleccion = self.guardado_rechazado_sin_poder_descartar(
            es_derivado, PermissionError(13, "En uso")
        )

        self.assertSoloQuedoSuelto(es_derivado, coleccion)

    def test_un_error_imprevisto_al_descartar_no_tapa_el_error_del_guardado(self):
        coleccion = self.guardado_rechazado_sin_poder_descartar(
            es_original, RuntimeError("el almacenamiento respondió algo que nadie previó")
        )

        self.assertSoloQuedoSuelto(es_original, coleccion)

    def test_si_el_original_no_se_puede_escribir_no_se_escribe_nada(self):
        form = formulario(self.coleccion, archivo=foto(color=OTRO_COLOR))
        self.assertTrue(form.is_valid(), form.errors.as_json())

        with falla_solo_con(self.almacenamiento, "save", es_original, OSError(28, "Disco lleno")):
            with self.assertRaises(OSError), transaction.atomic():
                form.save()

        self.assertEqual(self.archivos(), sorted([self.detalle, self.original]))
        self.assertEqual(self.en_la_base(), sorted([self.detalle, self.original]))

    def test_si_no_se_llego_a_escribir_nada_un_reintento_guarda_la_portada_nueva(self):
        nueva = foto(color=OTRO_COLOR)
        esperado = procesar_imagen(nueva)
        nueva.seek(0)
        form = formulario(self.coleccion, archivo=nueva)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        with falla_solo_con(self.almacenamiento, "save", es_original, OSError(28, "Disco lleno")):
            with self.assertRaises(OSError), transaction.atomic():
                form.save()

        with self.captureOnCommitCallbacks(execute=True):
            form.instance.save()  # ya con espacio en el disco

        guardada = Coleccion.objects.get(pk=self.coleccion_id)
        self.assertEqual(self.contenido(guardada.imagen.name), esperado.original)
        self.assertEqual(self.contenido(guardada.imagen_detalle.name), esperado.detalle)
        self.assertEqual(self.archivos(), archivos_de(guardada))
