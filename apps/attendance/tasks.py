from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from openpyxl import Workbook
from io import BytesIO
from datetime import datetime
from apps.employees.models import Employee
from .models import Attendance

@shared_task
def send_monthly_attendance_email():
    today = datetime.today()
    year = today.year
    month = today.month - 1  # Previous month

    if month == 0:
        month = 12
        year -= 1

    for employee in Employee.objects.filter(is_active=True):

        records = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=month
        ).order_by("date")

        if not records.exists():
            continue

        # Create Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance"

        ws.append(["Date", "Status", "Check In", "Check Out"])

        for r in records:
            ws.append([
                r.date.strftime("%Y-%m-%d"),
                r.status,
                r.check_in.strftime("%H:%M:%S") if r.check_in else "",
                r.check_out.strftime("%H:%M:%S") if r.check_out else "",
            ])

        file_stream = BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)

        # Send Email
        email = EmailMessage(
            subject=f"Monthly Attendance Report - {month}-{year}",
            body="Please find attached your monthly attendance report.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[employee.user.email],
        )

        email.attach(
            f"Attendance_{month}_{year}.xlsx",
            file_stream.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        email.send()

def generate_and_send(employee, year, month):
    records = Attendance.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month
    ).order_by("date")

    if not records.exists():
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    ws.append(["Date", "Status", "Check In", "Check Out"])

    for r in records:
        ws.append([
            r.date.strftime("%Y-%m-%d"),
            r.status,
            r.check_in.strftime("%H:%M:%S") if r.check_in else "",
            r.check_out.strftime("%H:%M:%S") if r.check_out else "",
        ])

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    email = EmailMessage(
        subject=f"Monthly Attendance Report - {month}-{year}",
        body="Please find attached your monthly attendance report.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[employee.user.email],
    )

    email.attach(
        f"Attendance_{month}_{year}.xlsx",
        file_stream.read(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    email.send()


@shared_task
def send_monthly_attendance_email():
    today = datetime.today()
    year = today.year
    month = today.month - 1

    if month == 0:
        month = 12
        year -= 1

    for employee in Employee.objects.filter(is_active=True):
        generate_and_send(employee, year, month)


@shared_task
def send_monthly_attendance_manual(year, month):
    for employee in Employee.objects.filter(is_active=True):
        generate_and_send(employee, year, month)