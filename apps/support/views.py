from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsSuperAdmin, IsAdmin, IsHR
from .models import SupportTicket
from .serializers import SupportTicketSerializer, SupportTicketCreateSerializer


def _get_company(request):
    return getattr(request.user, "company", None) or getattr(request, "company", None)


# ==================== LIST TICKETS (SuperAdmin: all; Company: own) ====================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ticket_list(request):
    qs = SupportTicket.objects.select_related("company", "created_by").order_by("-created_at")
    if getattr(request.user, "role", None) == "SUPER_ADMIN":
        # SuperAdmin sees all; optional query filters
        company_id = request.query_params.get("company_id")
        if company_id:
            qs = qs.filter(company_id=company_id)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        priority_filter = request.query_params.get("priority")
        if priority_filter:
            qs = qs.filter(priority=priority_filter.upper())
    else:
        # Tenant isolation: Admin/HR see only their company's tickets
        if request.user.role not in ("ADMIN", "HR"):
            return Response({"detail": "Only Admin or HR can list tickets."}, status=status.HTTP_403_FORBIDDEN)
        company = _get_company(request)
        if not company:
            return Response({"detail": "No company context."}, status=status.HTTP_403_FORBIDDEN)
        qs = qs.filter(company=company)
    serializer = SupportTicketSerializer(qs, many=True)
    return Response(serializer.data)


# ==================== COMPANY: CREATE TICKET ====================

@api_view(["POST"])
@permission_classes([IsAuthenticated, (IsAdmin | IsHR)])
def ticket_create(request):
    company = _get_company(request)
    if not company:
        return Response({"detail": "No company context."}, status=status.HTTP_403_FORBIDDEN)
    serializer = SupportTicketCreateSerializer(data=request.data)
    if serializer.is_valid():
        ticket = serializer.save(company=company, created_by=request.user)
        return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== TICKET DETAIL (SuperAdmin: any + PATCH; Company: own, read-only) ====================

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def ticket_detail(request, ticket_id):
    is_superadmin = getattr(request.user, "role", None) == "SUPER_ADMIN"
    if is_superadmin:
        ticket = SupportTicket.objects.filter(id=ticket_id).select_related("company", "created_by").first()
    else:
        company = _get_company(request)
        if not company:
            return Response({"detail": "No company context."}, status=status.HTTP_403_FORBIDDEN)
        ticket = SupportTicket.objects.filter(id=ticket_id, company=company).select_related("company", "created_by").first()
    if not ticket:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        return Response(SupportTicketSerializer(ticket).data)
    if request.method == "PATCH":
        if not is_superadmin:
            return Response({"detail": "Only Super Admin can update tickets."}, status=status.HTTP_403_FORBIDDEN)
        serializer = SupportTicketSerializer(ticket, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
