# Generated migration for payment mode specific fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daybook', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='bank_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='account_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='upi_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='cheque_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
