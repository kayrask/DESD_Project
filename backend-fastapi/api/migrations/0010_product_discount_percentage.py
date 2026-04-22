from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_order_created_at_order_expires_at_order_commission"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="discount_percentage",
            field=models.IntegerField(default=0, help_text="Surplus/quality discount 0–50%"),
        ),
    ]
