from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    edited_by_name = serializers.SerializerMethodField()

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
            "is_edited",
            "edit_reason",
            "edited_by",
            "edited_by_name",
            "edited_at",
            "previous_status",
        ]

    def get_edited_by_name(self, obj):
        if obj.edited_by:
            return f"{obj.edited_by.first_name} {obj.edited_by.last_name}"
        return None