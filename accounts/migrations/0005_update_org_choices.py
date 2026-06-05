from django.db import migrations, models


def forwards_remap_sede_latam(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(sede="latam").update(sede="sie")


def reverse_remap_sede_sie(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(sede="sie").update(sede="latam")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_avatar"),
    ]

    operations = [
        migrations.RunPython(forwards_remap_sede_latam, reverse_remap_sede_sie),
        migrations.AlterField(
            model_name="user",
            name="dept",
            field=models.CharField(
                blank=True,
                choices=[
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
                    ("atencion_clientes", "Atención clientes"),
                    ("otros", "Otros"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
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
                    ("sie", "SIE"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="puesto",
            field=models.CharField(
                blank=True,
                choices=[
                    ("desarrollo", "Desarrollo"),
                    ("sistemas", "Sistemas"),
                    ("consultoria", "Consultoría"),
                    ("administracion", "Administración"),
                    ("practicas", "Prácticas"),
                ],
                max_length=20,
            ),
        ),
    ]
