from django.db import migrations, models


DEPT_KEYS = {
    "nóminas": "nominas",
    "nominas": "nominas",
    "gestión": "gestion",
    "gestion": "gestion",
    "financiera": "financiera",
    "pesca": "pesca",
}


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for u in User.objects.all():
        u.is_gestor = (u.role == "gestor")
        u.is_jugador = not u.is_superuser
        normalized = DEPT_KEYS.get((u.dept or "").strip().lower(), "")
        u.dept = normalized
        u.save(update_fields=["is_gestor", "is_jugador", "dept"])


def reverse_noop(apps, schema_editor):
    # No restauramos el campo `role`: la separación en flags es irreversible.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_auditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_jugador",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="is_gestor",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="sede",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ourense", "Ourense"),
                    ("vigo", "Vigo"),
                    ("asturias", "Asturias"),
                    ("madrid", "Madrid"),
                    ("barcelona", "Barcelona"),
                    ("latam", "Latinoamérica"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="puesto",
            field=models.CharField(
                blank=True,
                choices=[
                    ("desarrollo", "Desarrollo"),
                    ("sistemas", "Sistemas"),
                    ("consultoria", "Consultoría"),
                    ("administracion", "Administración"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="dept",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.RunPython(forwards, reverse_noop),
        migrations.AlterField(
            model_name="user",
            name="dept",
            field=models.CharField(
                blank=True,
                choices=[
                    ("nominas", "Nóminas"),
                    ("gestion", "Gestión"),
                    ("financiera", "Financiera"),
                    ("pesca", "Pesca"),
                ],
                max_length=20,
            ),
        ),
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
    ]
