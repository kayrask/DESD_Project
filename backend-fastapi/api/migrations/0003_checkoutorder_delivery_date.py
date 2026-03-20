from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_add_quality_assessment'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkoutorder',
            name='delivery_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
