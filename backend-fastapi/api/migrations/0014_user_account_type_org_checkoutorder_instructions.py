from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0013_recurringorder_recipe_farmstory"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="account_type",
            field=models.CharField(
                choices=[
                    ("individual", "Individual"),
                    ("community_group", "Community Group"),
                    ("restaurant", "Restaurant"),
                ],
                default="individual",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="organization_name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="checkoutorder",
            name="special_instructions",
            field=models.TextField(blank=True, default=""),
        ),
    ]
