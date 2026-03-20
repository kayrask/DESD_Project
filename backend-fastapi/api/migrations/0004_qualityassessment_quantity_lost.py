from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_checkoutorder_delivery_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="qualityassessment",
            name="quantity_lost",
            field=models.IntegerField(default=0),
        ),
    ]
