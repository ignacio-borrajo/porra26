from django.db import migrations


def drop_scoped(apps, schema_editor):
    Prize = apps.get_model("pot", "Prize")
    Prize.objects.exclude(scope="global").delete()


def noop(apps, schema_editor):
    # No restauramos: las filas se pueden re-sembrar manualmente si hace falta.
    pass


class Migration(migrations.Migration):
    dependencies = [("pot", "0004_potsettings_matchday_winner_prize")]
    operations = [migrations.RunPython(drop_scoped, noop)]
