from django.db import models


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


class Producto(models.Model):
    coleccion = models.ForeignKey(
        Coleccion,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    nombre = models.CharField(max_length=120)
    detalle = models.CharField(max_length=180, blank=True)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    imagen_url = models.URLField(blank=True)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("-destacado", "nombre")

    def __str__(self):
        return self.nombre
