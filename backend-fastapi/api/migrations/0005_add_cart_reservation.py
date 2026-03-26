from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_qualityassessment_quantity_lost"),
    ]

    operations = [
        migrations.CreateModel(
            name="CartReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(db_index=True, max_length=40)),
                ("quantity", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cart_reservations",
                        to="api.product",
                    ),
                ),
            ],
            options={
                "unique_together": {("session_key", "product")},
            },
        ),
    ]
