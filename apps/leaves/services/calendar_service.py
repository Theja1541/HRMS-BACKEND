from ..models import LeaveRequest, Holiday


def get_calendar_events(request):

    leaves = LeaveRequest.objects.filter(
        status="APPROVED"
    ).select_related("employee","leave_type")

    holidays = Holiday.objects.all()

    events = []

    for leave in leaves:

        avatar = None
        if leave.employee.profile_photo:
            avatar = request.build_absolute_uri(
                leave.employee.profile_photo.url
            )

        events.append({
            "type": "leave",
            "title": f"{leave.employee.first_name}",
            "start": leave.start_date,
            "end": leave.end_date,
            "leave_type": leave.leave_type.name,
            "avatar": avatar
        })

    for holiday in holidays:

        events.append({
            "type": "holiday",
            "title": holiday.name,
            "start": holiday.date,
            "end": holiday.date
        })

    return events