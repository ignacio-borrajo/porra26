import uuid
from pathlib import Path

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .managers import UserManager


def avatar_upload_to(instance, filename):
    ext = Path(filename).suffix.lower() or ".jpg"
    return f"avatars/{instance.id}_{uuid.uuid4().hex[:8]}{ext}"


class User(AbstractBaseUser, PermissionsMixin):
    DEPT_CHOICES = [
        ("gestion", "Gestión"),
        ("financiera", "Financiera"),
        ("nominas", "Nóminas"),
        ("entorno", "Entorno"),
        ("galileo", "Servicios Galileo"),
        ("web_movilidad", "Web y Movilidad"),
        ("pesca", "Pesca"),
        ("aluminio", "Aluminio"),
        ("farmacia", "Farmacia"),
        ("sistemas", "Sistemas"),
        ("sie", "SIE"),
        ("atencion_clientes", "Atención clientes"),
        ("otros", "Otros"),
    ]
    SEDE_CHOICES = [
        ("ourense", "Ourense"),
        ("vigo", "Vigo"),
        ("asturias", "Asturias"),
        ("madrid", "Madrid"),
        ("barcelona", "Barcelona"),
    ]
    PUESTO_CHOICES = [
        ("desarrollo", "Desarrollo"),
        ("sistemas", "Sistemas"),
        ("consultoria", "Consultoría"),
        ("administracion", "Administración"),
        ("practicas", "Prácticas"),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    dept = models.CharField(max_length=20, choices=DEPT_CHOICES, blank=True)
    sede = models.CharField(max_length=20, choices=SEDE_CHOICES, blank=True)
    puesto = models.CharField(max_length=20, choices=PUESTO_CHOICES, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_to, blank=True, null=True)
    is_jugador = models.BooleanField(default=True)
    is_gestor = models.BooleanField(default=False)
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


@receiver(pre_delete, sender=User)
def _delete_avatar_file(sender, instance, **kwargs):
    if instance.avatar:
        instance.avatar.delete(save=False)
