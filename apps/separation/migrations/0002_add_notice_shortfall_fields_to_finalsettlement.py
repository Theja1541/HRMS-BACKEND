from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('separation', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='finalsettlement',
            name='notice_period_shortfall_days',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='finalsettlement',
            name='notice_shortfall_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
