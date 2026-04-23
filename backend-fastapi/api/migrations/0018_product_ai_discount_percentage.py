from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0017_product_ai_discount_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="ai_discount_percentage",
            field=models.IntegerField(default=0, help_text="AI quality discount 0–50%"),
        ),
    ]
