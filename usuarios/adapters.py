from allauth.account.adapter import DefaultAccountAdapter

from .models import generar_username


class UsuarioAccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        if not user.username:
            user.username = generar_username(user.first_name, user.email)
