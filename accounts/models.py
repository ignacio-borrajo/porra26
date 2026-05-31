from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model (placeholder; ampliado en Fase 1)."""

    class Meta:
        db_table = "accounts_user"
