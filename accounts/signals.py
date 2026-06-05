from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserSession


@receiver(post_save, sender=User)
def wipe_user_sessions_on_password_change(sender, instance, **kwargs):
    """Si una operación cambia explícitamente el campo `password`,
    limpia las UserSession del usuario. Las Session reales se invalidan
    aparte vía session_auth_hash."""
    update_fields = kwargs.get("update_fields") or set()
    if update_fields and "password" in update_fields:
        UserSession.objects.filter(user=instance).delete()
