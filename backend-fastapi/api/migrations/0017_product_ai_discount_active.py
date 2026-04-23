from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0016_merge_0015_modelevaluation_0015_qualityoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="ai_discount_active",
            field=models.BooleanField(
                default=False,
                help_text="True when the current discount was applied by AI quality assessment.",
            ),
        ),
    ]
