"""Bildirishnomalar va harakatlar jurnali uchun yordamchi funksiyalar."""
from .models import AuditLog, Notification


def notify(users, title, message="", url="", level="info"):
    seen = set()
    items = []
    for user in users:
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        items.append(Notification(user=user, title=title, message=message, url=url, level=level))
    Notification.objects.bulk_create(items)


def role_users(role, faculty=None, department=None):
    from accounts.models import User

    qs = User.objects.filter(role=role, is_active=True)
    if faculty is not None:
        qs = qs.filter(faculty=faculty)
    if department is not None:
        qs = qs.filter(department=department)
    return qs


def audit(user, action, details=""):
    AuditLog.objects.create(user=user if user and user.is_authenticated else None, action=action, details=details)
