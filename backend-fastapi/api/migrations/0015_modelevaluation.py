from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_user_account_type_org_checkoutorder_instructions"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.CharField(max_length=100)),
                ("accuracy", models.FloatField()),
                ("precision", models.FloatField()),
                ("recall", models.FloatField()),
                ("f1_score", models.FloatField()),
                ("evaluated_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["evaluated_at"]},
        ),
    ]
