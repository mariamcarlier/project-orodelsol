from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse

def admin_required(view_func):
    """
    Decorador para proteger vistas del panel administrativo y de configuración.
    
    Reglas de negocio (Escenario 2 — CFG-02):
    1. Si el usuario no está autenticado, deniega el acceso redirigiendo a la URL de login.
    2. Si el usuario está autenticado pero no tiene rol 'ADMIN' (y no es superusuario),
       deniega el acceso lanzando PermissionDenied (HTTP 403 Forbidden).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('admin:login'))
        
        if getattr(request.user, 'rol', None) != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied("Acceso denegado: se requieren permisos de Administrador.")
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view
