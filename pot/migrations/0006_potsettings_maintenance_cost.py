from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pot", "0005_drop_scoped_prizes"),
    ]

    operations = [
        migrations.AddField(
            model_name="potsettings",
            name="maintenance_cost",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0"), max_digits=8
            ),
        ),
    ]
