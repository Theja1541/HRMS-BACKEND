from rest_framework import serializers
from .models import Holiday
from apps.accounts.serializers import UserSerializer

class HolidaySerializer(serializers.ModelSerializer):
    created_by_details = UserSerializer(source="created_by", read_only=True)
    
    class Meta:
        model = Holiday
        fields = "__all__"

class HolidayCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = "__all__"
