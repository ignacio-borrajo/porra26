from django.db import migrations, models


def forwards_seed_applied_points(apps, schema_editor):
    Match = apps.get_model("competition", "Match")
    for m in Match.objects.filter(finished_at__isnull=False).select_related("round"):
        m.exact_points_applied = m.round.points
        m.partial_points_applied = m.round.partial_points
        m.save(update_fields=["exact_points_applied", "partial_points_applied"])


class Migration(migrations.Migration):
    dependencies = [
        ("competition", "0006_round_partial_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="exact_points_applied",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="match",
            name="partial_points_applied",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(forwards_seed_applied_points, migrations.RunPython.noop),
    ]
