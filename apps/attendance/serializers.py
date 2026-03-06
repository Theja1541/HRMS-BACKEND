from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee",
            "date",
            "status",
            "check_in",
            "check_out",
            "is_late",
            "late_minutes",
            "work_hours",
            "locked",
            "locked_at",
            "notes",
        ]