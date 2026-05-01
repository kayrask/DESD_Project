import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0020_recurring_order_preferences"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=60, unique=True)),
                ("week_start", models.DateField()),
                ("week_end", models.DateField()),
                ("gross_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("commission_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("net_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("order_count", models.IntegerField(default=0)),
                ("status", models.CharField(
                    choices=[
                        ("Pending Bank Transfer", "Pending Bank Transfer"),
                        ("Processed", "Processed"),
                    ],
                    default="Pending Bank Transfer",
                    max_length=30,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "producer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="settlements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-week_start"],
                "unique_together": {("producer", "week_start")},
            },
        ),
    ]
