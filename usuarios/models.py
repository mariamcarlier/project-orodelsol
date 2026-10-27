from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


# Create your models here.
class Usuario(AbstractUser):
    email = models.EmailField(
        blank=False,
        max_length=254,
        verbose_name="email address",
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="unique_nonempty_email_ci",
            )
        ]

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
    REQUIRED_FIELDS = [  # noqa: RUF012
        "email",
        "first_name",
        "last_name",
        "tipo_documento",
        "documento",
        "fecha_nacimiento",
        "telefono",
    ]

    @property
    def rol_efectivo(self):
        """Código del rol con el que se decide qué ve el usuario: ADMIN, MAYORISTA o CLIENTE.

        ÚNICO lugar donde vive la regla «un superusuario cuenta como administrador»:
        createsuperuser deja el campo «rol» en CLIENTE (su valor por defecto), así
        que mirar solo «rol» mostraría a un administrador como cliente.
        Es solo presentación: no concede ni quita permisos.
        """
        if self.is_superuser or self.rol == "ADMIN":
            return "ADMIN"
        return self.rol

    @property
    def es_administrador(self):
        """True si el usuario cuenta como administrador (superusuario o rol ADMIN)."""
        return self.rol_efectivo == "ADMIN"

    @property
    def tipo_cuenta(self):
        """Etiqueta del tipo de cuenta que se muestra en pantalla."""
        if self.es_administrador:
            return "Administrador"
        return self.get_rol_display()

    @property
    def nombre_visible(self):
        """Nombre con el que se saluda al usuario en pantalla.

        Usa first_name sin espacios sobrantes (también los repetidos dentro
        del nombre). Si está vacío, usa el nombre de usuario. Nunca devuelve
        None ni una cadena formada solo por espacios.
        """
        nombre = " ".join((self.first_name or "").split())
        return nombre or self.username

    @property
    def frase_bienvenida(self):
        """Frase de la cabecera de la cuenta, SIN el nombre: «Te damos la bienvenida».

        Hoy es neutra para todas las personas. Cuando exista el campo opcional
        de género (decisión pendiente, en su propio commit con migración), la
        variación «Bienvenida» / «Bienvenido» se decide AQUÍ y solo aquí. La
        plantilla pone el nombre aparte (en cursiva) con nombre_visible.
        """
        return "Te damos la bienvenida"

    @property
    def saludo_bienvenida(self):
        """Frase completa en texto plano: «Te damos la bienvenida, Mariam»."""
        return f"{self.frase_bienvenida}, {self.nombre_visible}"
