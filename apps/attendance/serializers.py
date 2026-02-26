from rest_framework import serializers
from .models import Attendance

class AttendanceSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(
        source='employee.id',
        read_only=True
    )
    username = serializers.CharField(
        source='employee.user.username',
        read_only=True
    )

    class Meta:
        model = Attendance
        fields = [
            'id',
            'employee_id',
            'username',
            'date',
            'check_in',
            'check_out',
            'status',
            'marked_at',
        ]