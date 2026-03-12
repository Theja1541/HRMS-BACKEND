# Generated migration for transaction IFSC and account holder fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daybook', '0003_add_vendor_payment_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='ifsc_code',
            field=models.CharField(blank=True, max_length=11, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='account_holder_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
