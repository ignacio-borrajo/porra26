from django.core.management.base import BaseCommand

from accounts.services.bulk_welcome import (
    DEFAULT_DELAY_SECONDS,
    pending_welcome_recipients,
    send_bulk_welcome,
)


class Command(BaseCommand):
    help = (
        "Envía el email de bienvenida a todos los jugadores activos que aún "
        "no han entrado al portal. Aplica un sleep entre correos para no "
        "saturar el SMTP de Resend."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=DEFAULT_DELAY_SECONDS,
            help=f"Segundos entre correos (default: {DEFAULT_DELAY_SECONDS}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista los destinatarios sin enviar nada.",
        )

    def handle(self, *args, **options):
        users = list(pending_welcome_recipients())
        if not users:
            self.stdout.write("No hay jugadores pendientes de activar.")
            return

        self.stdout.write(f"Destinatarios pendientes: {len(users)}")
        for u in users:
            self.stdout.write(f"  · {u.name} <{u.email}>")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: no se envía nada."))
            return

        sent, failed = send_bulk_welcome(users, actor=None, delay_seconds=options["delay"])
        self.stdout.write(self.style.SUCCESS(f"Enviados: {sent}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"Fallos: {len(failed)}"))
            for f in failed:
                self.stdout.write(f"  ! {f['email']}: {f['error']}")
