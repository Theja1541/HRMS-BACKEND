from django.shortcuts import get_object_or_404
from django.db.models import Count
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User
from .serializers import (
    LoginSerializer,
    UserSerializer,
    CreateUserSerializer,
    UpdateUserRoleSerializer
)
from .permissions import (
    IsAdmin,
    IsHR,
    IsEmployee,
    IsSuperAdmin
)
from apps.employees.models import Employee
# from apps.leaves.models import Leave
from apps.leaves.models import LeaveRequest
from apps.payroll.models import Payslip
from apps.attendance.models import Attendance

# =========================================================
# 🔐 LOGIN (JWT)
# =========================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = serializer.validated_data['user']

    # 🔒 Account Lock Check
    # 🔁 Force Password Change
    if getattr(user, "must_change_password", False):
        return Response({
            "force_password_change": True,
            "message": "You must change your password before continuing."
            }, status=status.HTTP_200_OK)


    # 🔁 Force Password Change
    # 🔁 Force Password Change
    force_password_change = getattr(user, "must_change_password", False)

    refresh = RefreshToken.for_user(user)

    employee_profile_id = None
    if user.role == "EMPLOYEE":
        try:
            employee_profile_id = user.employee_profile.id
        except:
            employee_profile_id = None

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "force_password_change": force_password_change,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "employee_profile_id": employee_profile_id
        }
    }, status=status.HTTP_200_OK)
                    
# =========================================================
# 👤 CURRENT USER PROFILE
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# =========================================================
# 👥 LIST USERS (ROLE BASED)
# =========================================================

@api_view(['GET'])
@permission_classes([IsSuperAdmin])
def superadmin_user_list(request):
    users = User.objects.all().order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_user_list(request):
    users = User.objects.all().order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsHR])
def hr_user_list(request):
    users = User.objects.all().order_by("-id")
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


# =========================================================
# ➕ CREATE USER (SUPER ADMIN)
# =========================================================

@api_view(['POST'])
@permission_classes([IsSuperAdmin])
def create_user(request):
    serializer = CreateUserSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "User created successfully"},
            status=status.HTTP_201_CREATED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# 🔄 UPDATE USER ROLE
# =========================================================

@api_view(['PATCH'])
@permission_classes([IsSuperAdmin])
def update_user_role(request, user_id):

    user = get_object_or_404(User, id=user_id)

    # 🚫 Prevent self role change
    if user == request.user:
        return Response(
            {"error": "You cannot change your own role"},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = UpdateUserRoleSerializer(
        user,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User role updated successfully"})

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# ❌ DELETE USER (ADMIN / SUPER ADMIN)
# =========================================================

@api_view(['DELETE'])
@permission_classes([IsAdmin | IsSuperAdmin])
def delete_user(request, user_id):

    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        return Response(
            {"error": "You cannot delete yourself"},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.delete()
    return Response({"message": "User deleted successfully"})


# =========================================================
# 🔑 CHANGE PASSWORD
# =========================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):

    new_password = request.data.get("new_password")

    if not new_password:
        return Response(
            {"error": "New password required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = request.user

    user.set_password(new_password)   # 🔥 IMPORTANT
    user.must_change_password = False
    user.failed_attempts = 0
    user.is_locked = False
    user.save()

    return Response({"message": "Password changed successfully"})



# =========================================================
# 📊 SUPER ADMIN ANALYTICS
# =========================================================

@api_view(["GET"])
@permission_classes([IsSuperAdmin])
def superadmin_analytics(request):

    total_users = User.objects.count()
    total_employees = Employee.objects.count()
    total_leaves = LeaveRequest.objects.count()
    total_payslips = Payslip.objects.count()
    total_attendance = Attendance.objects.count()

    role_distribution = (
        User.objects.values("role")
        .annotate(count=Count("id"))
    )

    return Response({
        "total_users": total_users,
        "total_employees": total_employees,
        "total_leaves": total_leaves,
        "total_payslips": total_payslips,
        "total_attendance": total_attendance,
        "role_distribution": role_distribution,
    })


# =========================================================
# 📋 SIDEBAR MENU (ROLE BASED)
# =========================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sidebar_permissions(request):

    role = request.user.role

    menu = {
        "SUPER_ADMIN": ["Dashboard", "Manage Users", "System Settings"],
        "ADMIN": ["Dashboard", "Employees", "Attendance", "Payroll"],
        "HR": ["Dashboard", "Employees", "Leaves"],
        "EMPLOYEE": ["Dashboard", "My Attendance", "My Payslips"]
    }

    return Response({
        "role": role,
        "menu": menu.get(role, [])
    })


# =========================================================
# 🚪 LOGOUT (JWT BLACKLIST)
# =========================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):

    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logged out successfully"})
    except Exception:
        return Response(
            {"error": "Invalid token"},
            status=status.HTTP_400_BAD_REQUEST
        )


# =========================================================
# 🏠 ROOT
# =========================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def accounts_root(request):
    return Response({
        "message": "Accounts API working",
        "available_endpoints": [
            "login/",
            "superadmin/users/",
            "change-password/",
            "analytics/",
        ]
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):

    user = request.user

    data = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
    }

    # If employee profile exists
    if hasattr(user, "employee_profile"):
        emp = user.employee_profile
        data.update({
            "employee_id": emp.employee_id,
            "first_name": emp.first_name,
            "last_name": emp.last_name,
            "company": emp.company.name if emp.company else None
        })

    return Response(data)