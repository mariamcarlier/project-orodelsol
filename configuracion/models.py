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
        Regla de negocio (Escenario 2 del criterio de aceptación):
        Si esta moneda se marca como principal, se desmarcan
        automáticamente todas las demás antes de guardar.
        Garantiza que solo exista UNA moneda principal en todo momento.
        """
        if self.es_principal:
            # Excluimos la instancia actual (pk) para no afectarla a sí misma
            Moneda.objects.filter(es_principal=True).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        principal = " ★" if self.es_principal else ""
        return f"{self.codigo_iso} — {self.nombre}{principal}"