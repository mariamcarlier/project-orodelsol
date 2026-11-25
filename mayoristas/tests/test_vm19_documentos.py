"""Pruebas de VM-19 (JODS-113): documentos del mayorista en almacén privado.

Lo que se comprueba, contra los criterios de aceptación:

  1. El archivo NO queda en MEDIA_ROOT ni se sirve por /media/ (DEC-10).
  2. Descarga solo el dueño de la solicitud y administración; un tercero no.
  3. Subir es exclusivo de administración (DEC-09).
  4. Se validan extensión, tamaño y archivo vacío.
  5. No hay borrado automático ni en cascada desde el tipo (DEC-11).
  6. Ruta con UUID: dos documentos con el mismo nombre no se pisan.

Los archivos se crean de verdad en un directorio temporal, y se comprueba
dónde quedan. No se simula el almacenamiento: si estuviera mal configurado,
la prueba debe fallar.
"""

import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from mayoristas import servicios
from mayoristas.models import (
    DocumentoSolicitud,
    SolicitudMayorista,
    TipoDocumento,
)

Usuario = get_user_model()

PDF = b"%PDF-1.4\n%prueba\n"


def crear_admin(nombre="adm"):
    """Administración: rol ADMIN + los permisos del módulo.

    Q-03 no da acceso por ser superusuario: la bandeja y la subida de
    documentos exigen el permiso nominal. Un ADMIN sin permiso es un caso
    real (cuenta recién creada) y debe recibir 403, no entrar por la puerta
    de atrás.
    """
    usuario = Usuario.objects.create_user(
        username=nombre, email=f"{nombre}@ejemplo.com",
        password="Clave-segura-123", rol="ADMIN",
    )
    usuario.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="mayoristas",
            codename__in=["ver_bandeja_solicitudesmayoristas",
                          "gestionar_solicitudesmayoristas"],
        )
    )
    return Usuario.objects.get(pk=usuario.pk)


def crear_mayorista(nombre="mayo"):
    return Usuario.objects.create_user(
        username=nombre, email=f"{nombre}@ejemplo.com",
        password="Clave-segura-123", rol="MAYORISTA",
    )


def crear_solicitud(usuario, nit="900123456", **extra):
    datos = {
        "usuario": usuario,
        "tipo_persona": "JURIDICA",
        "nit": nit,
        "nombre_comercial": "Boutique Sol",
        "representante_legal": "Ana Pérez",
        "ciudad": "Bogotá",
        "telefono": "3001234567",
        "correo": usuario.email,
        "canal_venta": "Tienda física",
    }
    datos.update(extra)
    return SolicitudMayorista.objects.create(**datos)


class BaseDocumentosTests(TestCase):
    """Cada prueba usa un PRIVATE_MEDIA_ROOT temporal y uno público distinto."""

    def setUp(self):
        self.dir_privado = tempfile.mkdtemp(prefix="priv-")
        self.dir_publico = tempfile.mkdtemp(prefix="pub-")
        self.override = override_settings(
            PRIVATE_MEDIA_ROOT=self.dir_privado,
            MEDIA_ROOT=self.dir_publico,
        )
        self.override.enable()
        # El storage se construyó al importar el módulo: hay que rehacerlo para
        # que use el directorio temporal de esta prueba.
        from mayoristas import storage as mod_storage
        from mayoristas import models as mod_models

        # `base_url=None` es la garantía de DEC-10: sin él, FileSystemStorage
        # cae a MEDIA_URL y el documento sería servible. Se replica aquí la
        # misma configuración real, solo con otro `location`.
        self.storage = mod_storage.AlmacenamientoPrivado(location=self.dir_privado)
        self._storage_original = mod_models.DocumentoSolicitud._meta.get_field(
            "archivo"
        ).storage
        mod_models.DocumentoSolicitud._meta.get_field("archivo").storage = self.storage

        self.admin = crear_admin()
        self.mayorista = crear_mayorista()
        self.solicitud = crear_solicitud(self.mayorista)
        self.otro = crear_mayorista("otro")
        self.solicitud_ajena = crear_solicitud(self.otro, nit="900999999")

    def tearDown(self):
        from mayoristas import models as mod_models

        mod_models.DocumentoSolicitud._meta.get_field(
            "archivo"
        ).storage = self._storage_original
        self.override.disable()
        shutil.rmtree(self.dir_privado, ignore_errors=True)
        shutil.rmtree(self.dir_publico, ignore_errors=True)

    def pdf(self, nombre="rut.pdf"):
        return SimpleUploadedFile(nombre, PDF, content_type="application/pdf")

    def adjuntar(self, nombre="rut.pdf", solicitud=None, **kwargs):
        documento, errores = servicios.adjuntar_documento(
            solicitud or self.solicitud, self.pdf(nombre), usuario=self.admin, **kwargs
        )
        self.assertEqual(errores, [], f"No debía haber errores: {errores}")
        return documento


# ─────────────────────────────────────────────────────────────────────
# 1. Almacenamiento privado (DEC-10)
# ─────────────────────────────────────────────────────────────────────

class StoragePrivadoTests(BaseDocumentosTests):
    def test_el_archivo_queda_en_el_directorio_privado(self):
        documento = self.adjuntar()
        self.assertTrue(documento.archivo.path.startswith(self.dir_privado))

    def test_el_archivo_no_queda_en_media_root(self):
        documento = self.adjuntar()
        self.assertFalse(documento.archivo.path.startswith(self.dir_publico))

    def test_el_storage_no_expone_una_url_publica(self):
        documento = self.adjuntar()
        try:
            url = documento.archivo.url
        except (ValueError, NotImplementedError):
            return
        self.fail(f"El storage devolvió una URL pública: {url!r}")

    def test_la_ruta_no_se_puede_adivinar(self):
        """UUID en el nombre: dos documentos iguales no comparten ruta."""
        primero = self.adjuntar("rut.pdf")
        segundo = self.adjuntar("rut.pdf")
        self.assertNotEqual(primero.archivo.name, segundo.archivo.name)

    def test_la_ruta_lleva_el_id_de_la_solicitud(self):
        documento = self.adjuntar()
        self.assertIn(f"solicitudes/{self.solicitud.pk}/", documento.archivo.name)

    def test_se_guarda_el_nombre_original(self):
        documento = self.adjuntar("camara-comercio.pdf")
        self.assertEqual(documento.nombre_original, "camara-comercio.pdf")

    def test_tamano_legible(self):
        documento = self.adjuntar()
        self.assertIn("KB", documento.tamano_legible)


# ─────────────────────────────────────────────────────────────────────
# 2. Descarga autorizada
# ─────────────────────────────────────────────────────────────────────

class DescargaTests(BaseDocumentosTests):
    def test_el_duenio_descarga(self):
        documento = self.adjuntar()
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(
            reverse("mayoristas:descargar_documento", args=[documento.pk])
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("attachment", respuesta["Content-Disposition"])

    def test_administracion_descarga(self):
        documento = self.adjuntar()
        self.client.force_login(self.admin)
        respuesta = self.client.get(
            reverse("mayoristas:descargar_documento", args=[documento.pk])
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_otro_mayorista_no_descarga(self):
        documento = self.adjuntar()
        self.client.force_login(self.otro)
        respuesta = self.client.get(
            reverse("mayoristas:descargar_documento", args=[documento.pk])
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_anonimo_no_descarga(self):
        documento = self.adjuntar()
        respuesta = self.client.get(
            reverse("mayoristas:descargar_documento", args=[documento.pk])
        )
        self.assertEqual(respuesta.status_code, 302)

    def test_el_contenido_es_el_archivo(self):
        documento = self.adjuntar()
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(
            reverse("mayoristas:descargar_documento", args=[documento.pk])
        )
        self.assertEqual(b"".join(respuesta.streaming_content), PDF)

    def test_archivo_borrado_del_disco_da_404_no_500(self):
        documento = self.adjuntar()
        self.storage.delete(documento.archivo.name)
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(
            reverse("mayoristas:descargar_documento", args=[documento.pk])
        )
        self.assertEqual(respuesta.status_code, 404)


# ─────────────────────────────────────────────────────────────────────
# 3. Subida solo administración (DEC-09)
# ─────────────────────────────────────────────────────────────────────

class SubidaTests(BaseDocumentosTests):
    def url(self, solicitud=None):
        return reverse(
            "mayoristas:subir_documento", args=[(solicitud or self.solicitud).pk]
        )

    def test_administracion_sube(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(self.url(), {"archivo": self.pdf()})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.solicitud.documentos.count(), 1)

    def test_un_mayorista_no_sube(self):
        self.client.force_login(self.mayorista)
        respuesta = self.client.post(self.url(), {"archivo": self.pdf()})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.solicitud.documentos.count(), 0)

    def test_anonimo_no_sube(self):
        respuesta = self.client.post(self.url(), {"archivo": self.pdf()})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.solicitud.documentos.count(), 0)

    def test_get_no_permitido(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_sin_archivo_no_crea_nada(self):
        self.client.force_login(self.admin)
        self.client.post(self.url(), {})
        self.assertEqual(self.solicitud.documentos.count(), 0)


# ─────────────────────────────────────────────────────────────────────
# 4. Validación del archivo
# ─────────────────────────────────────────────────────────────────────

class ValidacionTests(BaseDocumentosTests):
    def test_pdf_valido(self):
        self.assertEqual(servicios.validar_documento(self.pdf()), [])

    def test_extension_no_admitida(self):
        archivo = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/exe")
        errores = servicios.validar_documento(archivo)
        self.assertTrue(any("no admitido" in e for e in errores))

    def test_archivo_vacio(self):
        archivo = SimpleUploadedFile("vacio.pdf", b"", content_type="application/pdf")
        errores = servicios.validar_documento(archivo)
        self.assertTrue(any("vacío" in e for e in errores))

    @override_settings(DOCUMENTO_MAX_BYTES=100)
    def test_archivo_demasiado_grande(self):
        archivo = SimpleUploadedFile("grande.pdf", PDF * 50, content_type="application/pdf")
        errores = servicios.validar_documento(archivo)
        self.assertTrue(any("máximo" in e for e in errores))

    def test_sin_archivo(self):
        self.assertTrue(servicios.validar_documento(None))

    def test_una_extension_invalida_no_crea_registro(self):
        archivo = SimpleUploadedFile("x.exe", b"MZ", content_type="application/exe")
        documento, errores = servicios.adjuntar_documento(self.solicitud, archivo)
        self.assertIsNone(documento)
        self.assertTrue(errores)
        self.assertEqual(self.solicitud.documentos.count(), 0)

    def test_no_se_puede_forzar_un_tipo_inactivo(self):
        inactivo = TipoDocumento.objects.create(nombre="Viejo", activo=False)
        self.client.force_login(self.admin)
        self.client.post(
            self.url_subir(), {"archivo": self.pdf(), "tipo": str(inactivo.pk)}
        )
        documento = self.solicitud.documentos.get()
        self.assertIsNone(documento.tipo)

    def url_subir(self):
        return reverse("mayoristas:subir_documento", args=[self.solicitud.pk])


# ─────────────────────────────────────────────────────────────────────
# 5. Integridad (DEC-11, DEC-16)
# ─────────────────────────────────────────────────────────────────────

class IntegridadTests(BaseDocumentosTests):
    def test_no_hay_tipos_sembrados(self):
        self.assertEqual(TipoDocumento.objects.count(), 0)

    def test_borrar_un_tipo_no_borra_documentos(self):
        from django.db.models import ProtectedError

        tipo = TipoDocumento.objects.create(nombre="RUT")
        documento = self.adjuntar(tipo=tipo)
        with self.assertRaises(ProtectedError):
            tipo.delete()
        self.assertTrue(DocumentoSolicitud.objects.filter(pk=documento.pk).exists())

    def test_borrar_la_solicitud_se_lleva_sus_documentos(self):
        """La solicitud es el dueño del documento: no queda huérfano."""
        documento = self.adjuntar()
        self.solicitud.delete()
        self.assertFalse(DocumentoSolicitud.objects.filter(pk=documento.pk).exists())

    def test_eliminar_documento_borra_el_archivo_del_disco(self):
        documento = self.adjuntar()
        ruta = documento.archivo.path
        self.assertTrue(documento.archivo.storage.exists(documento.archivo.name))
        servicios.eliminar_documento(documento)
        self.assertFalse(self.storage.exists(ruta))

    def test_el_tipo_es_opcional(self):
        """DEC-16: sin tipos configurados se puede adjuntar igual."""
        documento = self.adjuntar()
        self.assertIsNone(documento.tipo)

    def test_queda_registro_de_quien_subio(self):
        documento = self.adjuntar()
        self.assertEqual(documento.subido_por, self.admin)


# ─────────────────────────────────────────────────────────────────────
# 6. Pantalla
# ─────────────────────────────────────────────────────────────────────

class PantallaDocumentosTests(BaseDocumentosTests):
    def url(self, solicitud=None):
        return reverse("mayoristas:documentos", args=[(solicitud or self.solicitud).pk])

    def test_el_duenio_ve_su_lista(self):
        self.adjuntar()
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(self.url())
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "rut.pdf")

    def test_el_duenio_no_ve_el_formulario_de_subida(self):
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(self.url())
        self.assertNotContains(respuesta, 'type="file"')

    def test_administracion_ve_el_formulario_de_subida(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url())
        self.assertContains(respuesta, 'type="file"')

    def test_un_tercero_no_ve_la_lista(self):
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_anonimo_va_al_login(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_estado_vacio_para_el_mayorista(self):
        self.client.force_login(self.mayorista)
        respuesta = self.client.get(self.url())
        self.assertContains(respuesta, "Todavía no hay documentos")

    def test_la_lista_no_ofrece_enlaces_directos_al_archivo(self):
        """Ninguna URL de /media/ en la pantalla (DEC-10)."""
        documento = self.adjuntar()
        self.client.force_login(self.admin)
        respuesta = self.client.get(self.url())
        self.assertNotContains(respuesta, "/media/")
        self.assertNotContains(respuesta, documento.archivo.name)