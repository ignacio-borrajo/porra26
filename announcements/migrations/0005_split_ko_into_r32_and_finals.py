from django.db import migrations, models


def delete_ko_announcements(apps, schema_editor):
    """Defensivo e idempotente: a mitad de fase de grupos no puede existir
    ningún anuncio scope_kind="ko" (solo se creaba al resolverse la Final),
    pero limpiamos por si acaso para no dejar filas huérfanas tras el split."""
    WinnerAnnouncement = apps.get_model("announcements", "WinnerAnnouncement")
    WinnerAnnouncement.objects.filter(scope_kind="ko").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0004_drop_round_scope_add_ko"),
    ]

    operations = [
        migrations.RunPython(delete_ko_announcements, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="winnerannouncement",
            name="uniq_ann_ko",
        ),
        migrations.AlterField(
            model_name="winnerannouncement",
            name="scope_kind",
            field=models.CharField(
                choices=[
                    ("matchday", "Jornada de grupos"),
                    ("r32", "Jornada de dieciseisavos"),
                    ("finals", "Jornada de fases finales"),
                    ("global", "Campeón del Mundial"),
                    ("sede", "Ganadores por sede"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="winnerannouncement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("scope_kind", "r32")),
                fields=("scope_kind",),
                name="uniq_ann_r32",
            ),
        ),
        migrations.AddConstraint(
            model_name="winnerannouncement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("scope_kind", "finals")),
                fields=("scope_kind",),
                name="uniq_ann_finals",
            ),
        ),
    ]
