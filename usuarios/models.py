from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class Usuario(AbstractUser):

    ROL_CHOICES = (
        ('ADMIN', 'Administrador'),
        ('MAYORISTA', 'Mayorista'),
        ('CLIENTE', 'Cliente'),
    )
    rol = models.CharField(max_length=10,choices=ROL_CHOICES,default='CLIENTE',verbose_name="Rol")
    TIPO_DOCUMENTO_CHOICES = (
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('PA', 'Pasaporte'),
        ('PPT', 'Permiso de Permanecia Temporal'),
        ('TI', 'Tarjeta de Identidad'),
        ('RC', 'Registro Civil'),
        ('NU', 'Otro')
    )
    
    first_name = models.CharField(max_length=50,blank=False,verbose_name="Nombre")
    last_name = models.CharField(max_length=50,blank=False,verbose_name="Apellido")
    tipo_documento = models.CharField(max_length=3,choices=TIPO_DOCUMENTO_CHOICES ,verbose_name="Tipo de Documento")
    documento = models.CharField(max_length=20,unique=True,verbose_name="Documento")
    fecha_nacimiento = models.DateField(blank=False, verbose_name="Fecha de Nacimiento")
    telefono = models.CharField(max_length=15, blank=False, verbose_name="Teléfono")
    foto = models.ImageField(upload_to="perfiles/", blank=True, null=True, verbose_name="Foto de perfil")
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "tipo_documento",
        "documento",
        "fecha_nacimiento",
        "telefono",
    ]

    @property
    def tipo_cuenta(self):
        """Etiqueta del tipo de cuenta que se muestra en pantalla.

        Es solo presentación: no concede ni quita permisos. Aplica la misma
        regla que usuarios.views.es_administrador (superusuario o rol ADMIN).
        """
        if self.is_superuser or self.rol == "ADMIN":
            return "Administrador"
        return self.get_rol_display() 
