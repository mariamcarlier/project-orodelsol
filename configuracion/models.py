from decimal import Decimal
from django.conf import settings
from django.db import models


class Impuesto(models.Model):
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej: IVA 19%")
    tasa = models.DecimalField(max_digits=5, decimal_places=2, help_text="Porcentaje, ej: 19.00")
    
    #en aplicaciones financieras (como el comercio electrónico de joyería) los redondeos de los decimales deben ser exactos; los flotantes suelen dar problemas de precisión.
    
    
    vigente = models.BooleanField(default=True, help_text="Indica si el impuesto aplica actualmente")
    
    class Meta:
        verbose_name = "Impuesto"
        verbose_name_plural = "Impuestos"

    def __str__(self):
        return f"{self.nombre} ({self.tasa}%)"


class Moneda(models.Model):
    codigo_iso  = models.CharField(max_length=3, unique=True, help_text="Código ISO 4217. Ej: COP, USD, EUR")
    nombre      = models.CharField(max_length=50, help_text="Nombre completo. Ej: Peso colombiano")
    simbolo     = models.CharField(max_length=5,  help_text="Símbolo. Ej: $, €, £")
    tasa_cambio = models.DecimalField(max_digits=12, decimal_places=4, default=1.0000,
                                      help_text="Tasa respecto a la moneda principal. La principal siempre vale 1.")
    es_principal = models.BooleanField(default=False,
                                       help_text="Solo puede haber una moneda principal activa a la vez.")
    activa = models.BooleanField(default=True,
                                 help_text="Monedas inactivas no se ofrecen al usuario.")

    class Meta:
        verbose_name        = "Moneda"
        verbose_name_plural = "Monedas"
        ordering            = ['-es_principal', 'codigo_iso']  # noqa: RUF012

    def save(self, *args, **kwargs):
        """
        Regla de negocio (Escenario 2 — CFG-03):
        Si esta moneda se marca como principal, se desmarcan
        automáticamente todas las demás antes de guardar.

        Maneja dos casos:
          - CREAR (pk=None): actualiza TODAS las existentes como no-principal.
          - EDITAR (pk existe): actualiza todas EXCEPTO la que se está editando.
        """
        if self.es_principal:
            otras = Moneda.objects.filter(es_principal=True)
            if self.pk:                    # Caso EDITAR: excluir la actual
                otras = otras.exclude(pk=self.pk)
            otras.update(es_principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        principal = " ★" if self.es_principal else ""
        return f"{self.codigo_iso} — {self.nombre}{principal}"


class Idioma(models.Model):
    codigo       = models.CharField(max_length=10, unique=True, help_text="Código de idioma. Ej: es, en, fr, pt")
    nombre       = models.CharField(max_length=50, help_text="Nombre descriptivo del idioma. Ej: Español, English")
    es_principal = models.BooleanField(default=False, help_text="Solo puede haber un idioma principal por defecto a la vez.")
    activo       = models.BooleanField(default=True, help_text="Idiomas inactivos no se ofrecen al usuario.")

    class Meta:
        verbose_name        = "Idioma"
        verbose_name_plural = "Idiomas"
        ordering            = ['-es_principal', 'codigo']  # noqa: RUF012

    def save(self, *args, **kwargs):
        """
        Regla de negocio (Escenario 2 — CFG-04):
        Si este idioma se marca como principal, se desmarcan
        automáticamente todos los demás antes de guardar.
        """
        if self.es_principal:
            otros = Idioma.objects.filter(es_principal=True)
            if self.pk:
                otros = otros.exclude(pk=self.pk)
            otros.update(es_principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        principal = " ★" if self.es_principal else ""
        return f"{self.codigo} — {self.nombre}{principal}"


class ParametroGeneral(models.Model):
    nombre_tienda       = models.CharField(max_length=100, default='Oro del Sol', help_text="Nombre comercial de la joyería")
    lema                = models.CharField(max_length=200, default='Joyería exclusiva en anillos de oro de 18K', blank=True, help_text="Lema o eslogan de la marca")
    nit                 = models.CharField(max_length=30, default='900.123.456-7', help_text="Identificación tributaria (NIT/RUT)")
    correo_contacto     = models.EmailField(default='contacto@orodelsol.com', help_text="Correo electrónico de contacto y atención")
    telefono_contacto   = models.CharField(max_length=30, default='+57 300 123 4567', help_text="Número telefónico / WhatsApp de atención")
    direccion           = models.CharField(max_length=200, default='Calle de la Joyería # 18K-01', help_text="Dirección física del showroom o taller")
    ciudad              = models.CharField(max_length=100, default='Bogotá, Colombia', help_text="Ciudad y país sede")
    horario_atencion    = models.CharField(max_length=150, default='Lunes a Sábado: 9:00 AM - 7:00 PM', blank=True, help_text="Horarios de atención al público")

    # Auditoría (Escenario 1 — CFG-01: quién y cuándo)
    actualizado_por     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='parametros_actualizados', verbose_name="Actualizado por")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name        = "Parámetro General"
        verbose_name_plural = "Parámetros Generales"

    def save(self, *args, **kwargs):
        # Patrón Singleton: siempre el mismo registro (pk=1)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Configuración General — {self.nombre_tienda}"



class CostoEnvio(models.Model):
    ciudad = models.CharField(
        max_length=100,
        help_text="Ciudad o municipio de destino.",
    )
    departamento = models.CharField(
        max_length=100,
        help_text="Departamento o región de destino.",
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo del envío en pesos colombianos (COP).",
    )
    tiempo_entrega = models.CharField(
        max_length=80,
        default="2 a 4 días hábiles",
        help_text="Tiempo estimado informado al cliente.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Costo de envío"
        verbose_name_plural = "Costos de envío"
        ordering = ["departamento", "ciudad"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["ciudad", "departamento"],
                name="uniq_costo_envio_ciudad_departamento",
            ),
        ]

    def __str__(self):
        return f"{self.ciudad}, {self.departamento} — ${self.precio} COP"

class CostoEnvio(models.Model):
    ciudad = models.CharField(
        max_length=100,
        help_text="Ciudad o municipio de destino.",
    )
    departamento = models.CharField(
        max_length=100,
        help_text="Departamento o región de destino.",
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Costo del envío en pesos colombianos (COP).",
    )
    tiempo_entrega = models.CharField(
        max_length=80,
        default="2 a 4 días hábiles",
        help_text="Tiempo estimado informado al cliente.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Costo de envío"
        verbose_name_plural = "Costos de envío"
        ordering = ["departamento", "ciudad"]
        constraints = [
            models.UniqueConstraint(
                fields=["ciudad", "departamento"],
                name="uniq_costo_envio_ciudad_departamento",
            ),
        ]

    def __str__(self):
        return f"{self.ciudad}, {self.departamento} — ${self.precio} COP"


class MetodoPago(models.Model):
    TIPO_CHOICES = (
        ("TRANSFERENCIA", "Transferencia bancaria"),
        ("NEQUI", "Nequi"),
        ("DAVIPLATA", "Daviplata"),
        ("EFECTIVO", "Efectivo / Contraentrega"),
        ("OTRO", "Otro medio manual"),
    )

    TIPO_CUENTA_CHOICES = (
        ("AHORROS", "Cuenta de Ahorros"),
        ("CORRIENTE", "Cuenta Corriente"),
        ("BILLETERA", "Billetera digital"),
        ("NO_APLICA", "No aplica"),
    )

    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre comercial o etiqueta del método. Ej: Bancolombia Transferencia, Nequi, Daviplata.",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="TRANSFERENCIA",
        help_text="Tipo de método de pago manual (enfoque en transferencias con validación de comprobante).",
    )
    banco = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Entidad financiera o billetera (ej: Bancolombia, Davivienda, Nequi).",
    )
    tipo_cuenta = models.CharField(
        max_length=20,
        choices=TIPO_CUENTA_CHOICES,
        default="AHORROS",
        help_text="Tipo de cuenta bancaria o billetera digital.",
    )
    numero_cuenta = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Número de cuenta bancaria o número de celular registrado.",
    )
    titular = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Nombre completo o razón social del titular de la cuenta.",
    )
    documento_titular = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="NIT o documento de identidad del titular.",
    )
    instrucciones = models.TextField(
        help_text="Instrucciones paso a paso para el cliente (datos de pago y envío de comprobante/captura).",
    )
    activo = models.BooleanField(
        default=True,
        help_text="Indica si este método de pago está disponible para los clientes en el checkout.",
    )
    orden = models.PositiveIntegerField(
        default=0,
        help_text="Orden de visualización en el checkout (menor número aparece primero).",
    )

    class Meta:
        verbose_name = "Método de pago"
        verbose_name_plural = "Métodos de pago"
        ordering = ["orden", "nombre"]

    @property
    def tipo_display(self):
        return self.get_tipo_display()

    def __str__(self):
        estado = "Activo" if self.activo else "Inactivo"
        return f"{self.nombre} ({self.get_tipo_display()}) — {estado}"


class PoliticaComercial(models.Model):
    monto_minimo_compra_b2c = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monto mínimo de compra para clientes particulares (B2C) en COP. 0 significa sin mínimo.",
    )
    monto_minimo_compra_b2b = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Monto mínimo de compra para clientes mayoristas (B2B) en COP. 0 significa sin mínimo.",
    )
    monto_minimo_envio_gratis = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Subtotal a partir del cual el envío nacional es gratuito. 0 desactiva el beneficio.",
    )
    tiempo_reserva_carrito_minutos = models.PositiveIntegerField(
        default=60,
        help_text="Tiempo en minutos que se retiene el inventario en el carrito antes de liberarlo.",
    )
    vigencia_cupones_dias = models.PositiveIntegerField(
        default=30,
        help_text="Vigencia por defecto en días calendario para cupones y promociones.",
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="politicas_actualizadas",
        verbose_name="Actualizado por",
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización",
    )

    class Meta:
        verbose_name = "Política comercial"
        verbose_name_plural = "Políticas comerciales"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def tiempo_reserva_display(self):
        return f"{self.tiempo_reserva_carrito_minutos} min"

    @property
    def vigencia_cupones_display(self):
        return f"{self.vigencia_cupones_dias} días"

    def validar_monto_minimo(self, usuario, subtotal):
        """Centraliza la validación de compra mínima según el rol B2B/B2C del usuario.

        Devuelve (cumple: bool, monto_minimo_requerido: Decimal).
        """
        es_mayorista = bool(usuario and getattr(usuario, "rol", None) == "MAYORISTA")
        monto_requerido = (
            self.monto_minimo_compra_b2b if es_mayorista else self.monto_minimo_compra_b2c
        )
        if monto_requerido > 0 and subtotal < monto_requerido:
            return False, monto_requerido
        return True, monto_requerido

    def aplica_envio_gratis(self, subtotal):
        """Centraliza la regla de negocio para envío gratuito."""
        if self.monto_minimo_envio_gratis > 0 and subtotal >= self.monto_minimo_envio_gratis:
            return True
        return False

    def __str__(self):
        return "Políticas Comerciales (Reglas del Negocio)"




class PlantillaDocumento(models.Model):
    TIPO_CHOICES = (
        ("CERTIFICADO", "Certificado de autenticidad / pureza 18K"),
        ("GARANTIA", "Póliza de garantía"),
        ("FACTURA", "Factura / Comprobante de venta"),
        ("OTRO", "Otro documento"),
    )

    nombre = models.CharField(
        max_length=150,
        help_text="Nombre descriptivo de la plantilla. Ej: Certificado de Pureza Oro 18K.",
    )
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        default="CERTIFICADO",
        help_text="Tipo de documento oficial asociado a esta plantilla.",
    )
    archivo = models.FileField(
        upload_to="plantillas_documentos/%Y/%m/",
        help_text="Archivo de plantilla en formato PDF (.pdf) o Word (.docx), tamaño máx. 10 MB.",
    )
    version = models.PositiveIntegerField(
        default=1,
        help_text="Número secuencial de versión. Se incrementa automáticamente en nuevas publicaciones.",
    )
    activa = models.BooleanField(
        default=True,
        help_text="Indica si esta plantilla es la versión vigente para su tipo de documento.",
    )
    descripcion = models.TextField(
        blank=True,
        default="",
        help_text="Descripción o notas sobre las modificaciones de esta versión.",
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de actualización",
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plantillas_subidas",
        verbose_name="Subido por",
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plantillas_actualizadas",
        verbose_name="Actualizado por",
    )

    class Meta:
        verbose_name = "Plantilla de documento"
        verbose_name_plural = "Plantillas de documentos"
        ordering = ["tipo", "-version", "-creado_en"]

    def __str__(self):
        estado = "Vigente" if self.activa else "Histórico"
        return f"{self.nombre} (v{self.version}) [{self.get_tipo_display()}] — {estado}"

    @property
    def tipo_display(self):
        return self.get_tipo_display()

    @property
    def version_display(self):
        return f"v{self.version}"

    @property
    def archivo_nombre(self):
        if self.archivo:
            import os
            return os.path.basename(self.archivo.name)
        return "—"

    @property
    def archivo_enlace(self):
        if self.archivo:
            import os
            from django.utils.html import format_html
            nombre = os.path.basename(self.archivo.name)
            try:
                url = self.archivo.url
                return format_html(
                    '<a href="{}" target="_blank" rel="noopener noreferrer" style="color: var(--color-dorado, #bfa15f); text-decoration: underline;">{}</a>',
                    url,
                    nombre,
                )
            except ValueError:
                return nombre
        return "—"

    @property
    def creado_en_display(self):
        if self.creado_en:
            return self.creado_en.strftime("%d/%m/%Y %H:%M")
        return "—"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and self.version == 1:
            max_ver = PlantillaDocumento.objects.filter(tipo=self.tipo).aggregate(
                models.Max("version")
            )["version__max"]
            if max_ver:
                self.version = max_ver + 1

        super().save(*args, **kwargs)

        if self.activa:
            PlantillaDocumento.objects.filter(tipo=self.tipo).exclude(pk=self.pk).update(activa=False)

    @classmethod
    def obtener_vigente(cls, tipo):
        """Devuelve la plantilla activa y vigente para un tipo de documento determinado.

        Punto de integración para Pedidos, Facturación y Certificados de autenticidad.
        """
        return cls.objects.filter(tipo=tipo, activa=True).order_by("-version", "-creado_en").first()




