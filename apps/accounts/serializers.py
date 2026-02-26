from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from .models import User


# ===========================
# CREATE USER
# ===========================
class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ===========================
# USER SERIALIZER (MISSING)
# ===========================
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "phone"]


# ===========================
# LOGIN SERIALIZER
# ===========================
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate


from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    MAX_FAILED_ATTEMPTS = 5

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No account found with this email"}
            )

        # 🔒 Check if locked
        if user.is_locked:
            raise serializers.ValidationError(
                {"detail": "Account is locked. Contact admin."}
            )

        # Authenticate
        authenticated_user = authenticate(
            username=user.username,
            password=password
        )

        if not authenticated_user:
            # Increase failed attempts
            user.failed_attempts += 1

            if user.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.is_locked = True
                user.locked_at = timezone.now()

            user.save()

            raise serializers.ValidationError(
                {"password": "Invalid password"}
            )

        # Reset failed attempts on success
        user.failed_attempts = 0
        user.save()

        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "User is inactive"}
            )

        if user.must_change_password:
            raise serializers.ValidationError(
                {"detail": "Password change required"}
            )

        data["user"] = user
        return data

# ===========================
# UPDATE ROLE
# ===========================
class UpdateUserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["role"]
