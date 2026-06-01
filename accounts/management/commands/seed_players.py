"""Crea (o actualiza) los jugadores iniciales de la porra con una contraseña común.

Uso típico en PythonAnywhere:

    python manage.py seed_players

Por defecto la contraseña es "1234" y `must_change_password=True`, así que el
jugador la cambiará en el primer login. Si el correo ya existe, se respeta el
usuario salvo que se pase --reset-password.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User

DEFAULT_PASSWORD = "1234"

PLAYERS = [
    ("Adrián Pineda", "adrian.pineda@edisa.com"),
    ("Fran Vázquez", "francisco.vazquez@edisa.com"),
    ("Hugo García", "hugo.garcia@edisa.com"),
    ("Xacobo González", "xacobo.gonzalez@edisa.com"),
]


class Command(BaseCommand):
    help = "Crea los jugadores iniciales de la porra (contraseña por defecto: 1234)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Contraseña a asignar (por defecto: {DEFAULT_PASSWORD!r}).",
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Si el jugador ya existe, le restablece la contraseña.",
        )

    @transaction.atomic
    def handle(self, *, password: str, reset_password: bool, **opts):
        created, updated, skipped = 0, 0, 0
        for name, email in PLAYERS:
            email_norm = email.lower()
            user = User.objects.filter(email=email_norm).first()
            if user is None:
                user = User.objects.create_user(
                    email=email_norm,
                    password=password,
                    name=name,
                    is_jugador=True,
                    is_gestor=False,
                    must_change_password=True,
                )
                created += 1
                self.stdout.write(self.style.SUCCESS(f"creado    {name} <{email_norm}>"))
            elif reset_password:
                user.set_password(password)
                user.must_change_password = True
                user.save(update_fields=["password", "must_change_password"])
                updated += 1
                self.stdout.write(self.style.WARNING(f"reset pwd {name} <{email_norm}>"))
            else:
                skipped += 1
                self.stdout.write(f"ya existe {name} <{email_norm}>")

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo. Creados: {created} · Reset: {updated} · Sin cambios: {skipped}"
            )
        )
