from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_product_discount_pct"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="harvest_date",
            field=models.DateField(blank=True, null=True, help_text="Date produce was harvested"),
        ),
        migrations.AddField(
            model_name="product",
            name="season_start",
            field=models.DateField(blank=True, null=True, help_text="Season availability start"),
        ),
        migrations.AddField(
            model_name="product",
            name="season_end",
            field=models.DateField(blank=True, null=True, help_text="Season availability end"),
        ),
        migrations.AddField(
            model_name="product",
            name="low_stock_threshold",
            field=models.IntegerField(default=5, help_text="Alert when stock falls to or below this level"),
        ),
    ]
