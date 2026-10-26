from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

PREFIJO_CODIGO = "AN-"


class Coleccion(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    temporada = models.CharField(max_length=30, blank=True)
    imagen_url = models.URLField(blank=True)
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
    codigo = models.CharField(max_length=30, null=True, blank=True)
    nombre = models.CharField(max_length=120)
    detalle = models.CharField(max_length=180, blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    imagen_url = models.URLField(blank=True)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    es_borrador = models.BooleanField(default=False)
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
