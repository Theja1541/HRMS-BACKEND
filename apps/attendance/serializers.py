from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    edited_by_name = serializers.SerializerMethodField()
    working_hours = serializers.DecimalField(source='work_hours', max_digits=5, decimal_places=2, read_only=True)
    remarks = serializers.CharField(source='notes', read_only=True)
    marked_by = serializers.PrimaryKeyRelatedField(source='edited_by', read_only=True)

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
            "working_hours",
            "locked",
            "locked_at",
            "notes",
            "remarks",
            "is_edited",
            "edit_reason",
            "edited_by",
            "marked_by",
            "edited_by_name",
            "edited_at",
            "previous_status",
            "source",
        ]

    def get_edited_by_name(self, obj):
        if obj.edited_by:
            return f"{obj.edited_by.first_name} {obj.edited_by.last_name}"
        return None