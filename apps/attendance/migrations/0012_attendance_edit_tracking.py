# Generated migration for attendance edit tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('attendance', '0011_attendance_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='is_edited',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='attendance',
            name='edit_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='edited_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='edited_attendances',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name='attendance',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='attendance',
            name='previous_status',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
