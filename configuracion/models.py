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
        ordering            = ['-es_principal', 'codigo_iso']

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
        ordering            = ['-es_principal', 'codigo']

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
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Configuración General — {self.nombre_tienda}"
