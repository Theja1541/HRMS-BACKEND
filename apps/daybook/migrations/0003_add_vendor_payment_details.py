# Generated migration for vendor bank and UPI details

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daybook', '0002_add_payment_mode_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='gst_applicable',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='vendor',
            name='bank_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='account_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='ifsc_code',
            field=models.CharField(blank=True, max_length=11, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='account_holder_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='upi_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
