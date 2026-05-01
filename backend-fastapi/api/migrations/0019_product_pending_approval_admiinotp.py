from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0018_product_ai_discount_percentage"),
    ]

    operations = [
        # Product.status: add Pending Approval and Rejected choices (no schema change, choices are enforced in Python)
        migrations.AlterField(
            model_name="product",
            name="status",
            field=models.CharField(
                choices=[
                    ("Available", "Available"),
                    ("In Season", "In Season"),
                    ("Out of Stock", "Out of Stock"),
                    ("Unavailable", "Unavailable"),
                    ("Pending Approval", "Pending Approval"),
                    ("Rejected", "Rejected"),
                ],
                default="Available",
                max_length=50,
            ),
        ),
        # New AdminOTP table
        migrations.CreateModel(
            name="AdminOTP",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=6)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("is_used", models.BooleanField(default=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="otps",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
