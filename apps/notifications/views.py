from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notifications(request):

    notifications = Notification.objects.filter(user=request.user)

    serializer = NotificationSerializer(notifications, many=True)

    unread_count = notifications.filter(is_read=False).count()

    return Response({
        "unread_count": unread_count,
        "notifications": serializer.data
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):

    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.is_read = True
        notification.save()
        return Response({"message": "Marked as read"})
    except Notification.DoesNotExist:
        return Response({"error": "Not found"}, status=404)
    

