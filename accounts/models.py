from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [("jugador", "Jugador"), ("gestor", "Gestor")]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    dept = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="jugador")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class AuditLog(models.Model):
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_actions"
    )
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "-created_at"])]

    def __str__(self):
        return f"{self.action} on {self.target_type}#{self.target_id} by {self.actor_id}"
