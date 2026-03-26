from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_checkoutorder_customer"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
