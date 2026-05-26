from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db.models import Q
from .models import Holiday
from .serializers import HolidaySerializer, HolidayCreateSerializer
import openpyxl
from datetime import datetime

class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return HolidayCreateSerializer
        return HolidaySerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming(self, request):
        today = timezone.localdate()
        holidays = self.get_queryset().filter(to_date__gte=today, is_active=True).order_by("from_date")
        
        month_holidays = holidays.filter(from_date__month=today.month).count()
        next_holiday = holidays.first()
        
        serializer = self.get_serializer(next_holiday) if next_holiday else None
        
        return Response({
            "next_holiday": serializer.data if serializer else None,
            "total_this_month": month_holidays
        })

    @action(detail=False, methods=["get"], url_path="calendar")
    def calendar(self, request):
        holidays = self.get_queryset().filter(is_active=True)
        events = []
        for h in holidays:
            color = "#3b82f6" # default blue
            if h.holiday_type == "PUBLIC":
                color = "#ef4444" # red
            elif h.holiday_type == "OPTIONAL":
                color = "#f59e0b" # yellow
            elif h.holiday_type == "FESTIVAL":
                color = "#8b5cf6" # purple
                
            events.append({
                "id": h.id,
                "title": h.holiday_name,
                "start": h.from_date.isoformat(),
                "end": (h.to_date + timezone.timedelta(days=1)).isoformat() if h.to_date else h.from_date.isoformat(),
                "allDay": True,
                "backgroundColor": color,
                "borderColor": color,
                "extendedProps": {
                    "type": h.holiday_type,
                    "state": h.state,
                    "description": h.description
                }
            })
        return Response(events)

    @action(detail=False, methods=["post"], url_path="bulk-upload", parser_classes=[MultiPartParser, FormParser])
    def bulk_upload(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not file.name.endswith(".xlsx"):
            return Response({"error": "Only .xlsx files are supported"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            wb = openpyxl.load_workbook(file)
            sheet = wb.active
            
            holidays_created = 0
            for i, row in enumerate(sheet.iter_rows(values_only=True)):
                if i == 0:
                    continue # skip header
                
                name = row[0]
                from_date_val = row[1]
                to_date_val = row[2]
                h_type = row[3] or "PUBLIC"
                state = row[4] or "ALL"
                desc = row[5]
                p_type = row[6] or "PAID" if len(row) > 6 else "PAID"
                
                if not name or not from_date_val:
                    continue
                    
                if isinstance(from_date_val, datetime):
                    from_date_val = from_date_val.date()
                if isinstance(to_date_val, datetime):
                    to_date_val = to_date_val.date()
                
                if not to_date_val:
                    to_date_val = from_date_val
                
                Holiday.objects.update_or_create(
                    holiday_name=name,
                    from_date=from_date_val,
                    to_date=to_date_val,
                    defaults={
                        "holiday_type": h_type,
                        "payment_type": p_type.upper(),
                        "state": state,
                        "description": desc,
                        "created_by": request.user,
                        "is_active": True
                    }
                )
                holidays_created += 1
                
            return Response({"message": f"Successfully uploaded {holidays_created} holidays."})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
