from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0014_user_account_type_org_checkoutorder_instructions"),
    ]

    operations = [
        migrations.CreateModel(
            name="QualityOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ai_grade",       models.CharField(max_length=1, choices=[("A", "Grade A – Premium"), ("B", "Grade B – Standard"), ("C", "Grade C – Discounted")])),
                ("override_grade", models.CharField(max_length=1, choices=[("A", "Grade A – Healthy / Premium"), ("B", "Grade B – Standard"), ("C", "Grade C – Discounted / Borderline")])),
                ("reason",         models.CharField(max_length=30, choices=[("wrong_grade", "AI grade was incorrect"), ("context", "Context the model could not see"), ("image_quality", "Poor image quality affected the result"), ("other", "Other")])),
                ("notes",          models.TextField(blank=True, default="")),
                ("created_at",     models.DateTimeField(auto_now_add=True)),
                ("assessment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="overrides", to="api.qualityassessment")),
                ("producer",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quality_overrides", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
