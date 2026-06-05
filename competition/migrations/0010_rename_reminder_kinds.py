from django.db import migrations, models

OLD_TO_NEW = {
    "T_MINUS_4H": "T_MINUS_2H",
    "T_MINUS_2_5H": "T_MINUS_30M",
}
NEW_TO_OLD = {v: k for k, v in OLD_TO_NEW.items()}


def _rewrite(apps, mapping):
    BetsReminderLog = apps.get_model("competition", "BetsReminderLog")
    for old, new in mapping.items():
        BetsReminderLog.objects.filter(kind=old).update(kind=new)


def forwards(apps, schema_editor):
    _rewrite(apps, OLD_TO_NEW)


def backwards(apps, schema_editor):
    _rewrite(apps, NEW_TO_OLD)


class Migration(migrations.Migration):
    dependencies = [
        ("competition", "0009_match_slots_and_nullable_teams"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="betsreminderlog",
            name="kind",
            field=models.CharField(
                choices=[
                    ("T_MINUS_2H", "2 h antes del saque"),
                    ("T_MINUS_30M", "30 min antes del saque"),
                    ("MANUAL", "Manual"),
                ],
                max_length=20,
            ),
        ),
    ]
