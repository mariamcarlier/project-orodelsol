from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .upload_paths import (
    ruta_derivado_producto,
    ruta_imagen_coleccion,
    ruta_imagen_producto,
)

PREFIJO_CODIGO = "AN-"


class Coleccion(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    temporada = models.CharField(max_length=30, blank=True)
    imagen_url = models.URLField(blank=True)
    # Portada propia. Convive con imagen_url (compatibilidad). La regla de
    # «archivo O URL, nunca ambos» se aplicará en el formulario (Paso 7).
    imagen = models.ImageField(upload_to=ruta_imagen_coleccion, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("nombre",)
        verbose_name = "colección"
        verbose_name_plural = "colecciones"

    def __str__(self):
        return self.nombre


def _sin_ceros(valor):
    """Muestra 7.0 como '7' y 6.5 como '6.5' (sin tocar enteros como 10)."""
    texto = format(Decimal(str(valor)), "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto


class Talla(models.Model):
    """Talla de anillo.

    La referencia comercial principal es la talla US. El diámetro interior en
    milímetros es la referencia física: son datos relacionados pero NO
    intercambiables, por eso el diámetro solo se considera confiable cuando
    `diametro_verificado` es verdadero (medido y validado, no calculado).
    """

    talla_us = models.DecimalField(max_digits=4, decimal_places=1, unique=True)
    diametro_interno_mm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    talla_nacional = models.CharField(max_length=10, null=True, blank=True)
    diametro_verificado = models.BooleanField(default=False)

    class Meta:
        ordering = ("talla_us",)
        verbose_name = "talla"
        verbose_name_plural = "tallas"
        constraints = [
            models.CheckConstraint(
                condition=Q(talla_us__gt=0),
                name="talla_us_positiva",
            ),
            models.CheckConstraint(
                condition=Q(diametro_interno_mm__isnull=True)
                | Q(diametro_interno_mm__gt=0),
                name="talla_diametro_positivo",
            ),
            models.CheckConstraint(
                condition=Q(diametro_verificado=False)
                | Q(diametro_interno_mm__isnull=False),
                name="talla_verificada_con_diametro",
            ),
        ]

    def __str__(self):
        texto = f"US {_sin_ceros(self.talla_us)}"
        if self.diametro_verificado and self.diametro_interno_mm is not None:
            texto += f" ({_sin_ceros(self.diametro_interno_mm)} mm)"
        return texto


class Material(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ("nombre",)
        verbose_name = "material"
        verbose_name_plural = "materiales"

    def __str__(self):
        return self.nombre


class ProductoQuerySet(models.QuerySet):
    def publicos(self):
        """Visibilidad pública = activo AND NOT es_borrador."""
        return self.filter(activo=True, es_borrador=False)

    def completos(self):
        """Productos que cumplen los requisitos para publicarse."""
        return (
            self.exclude(nombre="")
            .exclude(codigo="")
            .exclude(imagen_url="")
            .filter(precio__gt=0)
        )

    def incompletos(self):
        return self.exclude(pk__in=self.completos().values("pk"))


class Producto(models.Model):
    """Lo que el anillo ES. Lo que SE VENDE (talla, material, stock) vive en
    VarianteProducto."""

    coleccion = models.ForeignKey(
        Coleccion,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    codigo = models.CharField(max_length=30, unique=True, blank=True)
    nombre = models.CharField(max_length=120)
    detalle = models.CharField(max_length=180, blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    imagen_url = models.URLField(blank=True)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    es_borrador = models.BooleanField(default=False)
    # True = la galería (ProductoImagen) ya es la fuente de verdad de las
    # imágenes de este producto. Mientras sea False, imagen_url sigue
    # sirviendo como respaldo de lectura. Lo gestionan el servicio de galería
    # y la migración de datos; por eso no es editable en formularios.
    galeria_gestionada = models.BooleanField(default=False, editable=False)
    tallas = models.ManyToManyField(
        Talla,
        blank=True,
        related_name="productos",
        verbose_name="tallas permitidas",
    )
    materiales = models.ManyToManyField(
        Material,
        blank=True,
        related_name="productos",
        verbose_name="materiales permitidos",
    )

    objects = ProductoQuerySet.as_manager()

    class Meta:
        ordering = ("-destacado", "nombre")

    def __str__(self):
        return self.nombre

    @property
    def es_publico(self):
        return self.activo and not self.es_borrador

    @classmethod
    def siguiente_codigo(cls):
        """Siguiente AN-NNNN: arranca desde el mayor número ya usado."""
        mayor = 0
        existentes = cls.objects.filter(codigo__startswith=PREFIJO_CODIGO)
        for codigo in existentes.values_list("codigo", flat=True):
            sufijo = codigo[len(PREFIJO_CODIGO):]
            if sufijo.isdigit():
                mayor = max(mayor, int(sufijo))
        return f"{PREFIJO_CODIGO}{mayor + 1:04d}"

    def asegurar_codigo(self):
        self.codigo = (self.codigo or "").strip().upper()
        if not self.codigo:
            self.codigo = self.siguiente_codigo()

    def clean(self):
        self.asegurar_codigo()
        if not self.es_publico:
            return
        faltantes = {}
        if not (self.nombre or "").strip():
            faltantes["nombre"] = "El nombre es obligatorio para publicar."
        if self.precio is None or self.precio <= 0:
            faltantes["precio"] = "El precio debe ser mayor a cero para publicar."
        if not (self.imagen_url or "").strip():
            faltantes["imagen_url"] = (
                "La imagen es obligatoria para publicar. "
                "Márcalo como borrador si aún no la tienes."
            )
        if faltantes:
            raise ValidationError(faltantes)

    def save(self, *args, **kwargs):
        self.asegurar_codigo()
        super().save(*args, **kwargs)


class VarianteProducto(models.Model):
    """Lo que SE VENDE: un producto en una talla y un material concretos.

    Precio final = producto.precio + precio_adicional (no hay tabla de precios).
    """

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="variantes",
    )
    talla = models.ForeignKey(
        Talla,
        on_delete=models.PROTECT,
        related_name="variantes",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="variantes",
    )
    sku = models.CharField(max_length=40, unique=True)
    peso_gramos = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    precio_adicional = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    stock = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("producto", "talla")
        verbose_name = "variante de producto"
        verbose_name_plural = "variantes de producto"
        constraints = [
            models.UniqueConstraint(
                fields=("producto", "talla", "material"),
                name="variante_unica",
            ),
            models.CheckConstraint(
                condition=Q(peso_gramos__isnull=True) | Q(peso_gramos__gt=0),
                name="variante_peso_positivo",
            ),
            models.CheckConstraint(
                condition=Q(precio_adicional__gte=0),
                name="variante_precio_adicional_no_negativo",
            ),
        ]

    def __str__(self):
        return self.sku

    @property
    def precio_final(self):
        return self.producto.precio + self.precio_adicional

    def clean(self):
        if not (self.producto_id and self.talla_id and self.material_id):
            return
        errores = {}
        if not self.producto.tallas.filter(pk=self.talla_id).exists():
            errores["talla"] = "Esta talla no está permitida para el producto."
        if not self.producto.materiales.filter(pk=self.material_id).exists():
            errores["material"] = "Este material no está permitido para el producto."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.sku = (self.sku or "").strip().upper()
        super().save(*args, **kwargs)


class ProductoImagen(models.Model):
    """Una fotografía de la galería de un producto.

    Cada fila tiene EXACTAMENTE una fuente: un archivo propio (`archivo`) o una
    URL externa (`url`). Una galería puede mezclar ambas.

    Garantías, por capas (ninguna sustituye a las otras):
    - Base de datos: una sola fuente por fila y, como máximo, una principal
      por producto (restricciones de `Meta.constraints`).
    - `clean()`: mensaje legible para formularios y admin. OJO: `save()` NO
      llama a `clean()`; solo lo ejecutan `full_clean()`, los ModelForm y el
      admin.
    - Servicio de galería (Paso 4): cantidad máxima, «exactamente una
      principal si hay imágenes» y reglas de publicación. La base de datos no
      puede exigir «al menos una principal», solo «a lo sumo una».
    """

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="imagenes",
    )
    archivo = models.ImageField(upload_to=ruta_imagen_producto, blank=True)
    archivo_detalle = models.ImageField(
        upload_to=ruta_derivado_producto, blank=True, editable=False
    )
    archivo_miniatura = models.ImageField(
        upload_to=ruta_derivado_producto, blank=True, editable=False
    )
    url = models.URLField(max_length=500, blank=True)
    es_principal = models.BooleanField(default=False)
    # Sin unicidad: reordenar no debe chocar con una restricción a mitad de
    # operación. El orden se normaliza en el servicio; los empates los
    # resuelve el pk.
    orden = models.PositiveSmallIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("orden", "pk")
        verbose_name = "imagen de producto"
        verbose_name_plural = "imágenes de producto"
        constraints = [
            models.CheckConstraint(
                condition=(Q(archivo="") & ~Q(url=""))
                | (~Q(archivo="") & Q(url="")),
                name="imagen_una_sola_fuente",
                violation_error_message=(
                    "Cada fotografía necesita exactamente una fuente: "
                    "un archivo o una URL."
                ),
            ),
            models.UniqueConstraint(
                fields=("producto",),
                condition=Q(es_principal=True),
                name="imagen_principal_unica",
                violation_error_message=(
                    "Un producto solo puede tener una fotografía principal."
                ),
            ),
        ]

    def __str__(self):
        # Solo usa campos propios: no consulta el producto (evita N+1 en listados).
        return f"Imagen {self.pk or 'nueva'} del producto {self.producto_id}"

    def clean(self):
        """Exige exactamente una fuente (archivo o URL).

        Se ejecuta aunque un ModelForm no incluya `archivo` ni `url`: Django
        omite las restricciones que tocan campos excluidos del formulario,
        pero siempre llama a `clean()`.
        """
        self.url = (self.url or "").strip()
        tiene_archivo = bool(self.archivo)
        tiene_url = bool(self.url)
        if tiene_archivo and tiene_url:
            raise ValidationError(
                "Cada fotografía debe tener una sola fuente: "
                "sube un archivo o indica una URL, no ambos."
            )
        if not tiene_archivo and not tiene_url:
            raise ValidationError(
                "Cada fotografía necesita una fuente: un archivo o una URL."
            )

    def _primera_fuente(self, *campos):
        for campo in campos:
            if campo:
                return campo.url
        return self.url

    @property
    def src(self):
        """Imagen original: archivo propio o, si no hay, la URL."""
        return self._primera_fuente(self.archivo)

    @property
    def src_miniatura(self):
        """Miniatura (~480 px) o, si no existe, original / URL."""
        return self._primera_fuente(self.archivo_miniatura, self.archivo)

    @property
    def src_detalle(self):
        """Versión de detalle (~1200 px) o, si no existe, original / URL."""
        return self._primera_fuente(self.archivo_detalle, self.archivo)
