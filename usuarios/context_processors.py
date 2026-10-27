from django.conf import settings
from allauth.socialaccount.models import SocialApp


def google_oauth(request):
    configured_in_admin = SocialApp.objects.filter(
        provider="google",
        sites__id=settings.SITE_ID,
        client_id__gt="",
        secret__gt="",
    ).exists()
    return {
        "google_login_enabled": settings.GOOGLE_OAUTH_ENABLED or configured_in_admin
    }
