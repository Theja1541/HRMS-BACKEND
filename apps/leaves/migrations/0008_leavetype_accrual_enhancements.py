# Generated migration for leave type enhancements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0007_leaveaccruallog'),
    ]

    operations = [
        migrations.AddField(
            model_name='leavetype',
            name='accrual_type',
            field=models.CharField(
                choices=[
                    ('ANNUAL', 'Annual (All at once)'),
                    ('MONTHLY', 'Monthly Accrual'),
                    ('QUARTERLY', 'Quarterly Accrual')
                ],
                default='ANNUAL',
                help_text='How leaves are credited to employees',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='leavetype',
            name='accrual_start_month',
            field=models.IntegerField(
                default=1,
                help_text='Month when accrual starts (1=Jan, 12=Dec)'
            ),
        ),
        migrations.AddField(
            model_name='leavetype',
            name='allow_negative_balance',
            field=models.BooleanField(
                default=False,
                help_text='Allow employees to take leave even if balance is insufficient (will become LOP)'
            ),
        ),
    ]
