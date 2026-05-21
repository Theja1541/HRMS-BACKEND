from rest_framework import serializers
from .models import SupportTicket


class SupportTicketSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_code = serializers.CharField(source="company.company_code", read_only=True)
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "company",
            "company_name",
            "company_code",
            "title",
            "description",
            "priority",
            "status",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["title", "description", "priority"]
