"""Rollar bo‘yicha ruxsatlar va ma’lumotlar ko‘lami (scope)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def role_required(*roles):
    """Faqat ko‘rsatilgan rollarga ruxsat beradi. Administrator har doim kira oladi."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if user.is_admin_role or user.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied("Bu sahifaga kirish huquqingiz yo‘q.")

        return wrapper

    return decorator


def require_unit(request, field):
    """Kafedra/dekanat foydalanuvchisi o‘z bo‘linmasiga biriktirilganini tekshiradi."""
    if getattr(request.user, field) is None and not request.user.is_admin_role:
        messages.error(
            request,
            "Hisobingiz hali kafedra/fakultetga biriktirilmagan. Administratorga murojaat qiling.",
        )
        return redirect("core:dashboard")
    return None


def _is_global(user):
    return user.is_admin_role or user.is_sifat


def scope_students(user):
    from accounts.models import User

    qs = User.objects.filter(role=User.Role.STUDENT).select_related(
        "faculty", "department", "student_profile", "student_profile__direction"
    )
    if _is_global(user):
        return qs
    if user.is_dekanat:
        return qs.filter(faculty=user.faculty)
    if user.is_kafedra:
        return qs.filter(department=user.department)
    if user.is_teacher:
        return qs.filter(thesis__supervisor=user)
    return qs.none()


def scope_teachers(user):
    from accounts.models import User

    qs = User.objects.filter(role=User.Role.TEACHER).select_related(
        "department", "department__faculty", "teacher_profile"
    )
    if _is_global(user):
        return qs
    if user.is_dekanat:
        return qs.filter(department__faculty=user.faculty)
    if user.is_kafedra:
        return qs.filter(department=user.department)
    return qs.none()


def scope_theses(user):
    from theses.models import Thesis

    qs = Thesis.objects.select_related(
        "student", "student__student_profile", "student__student_profile__direction",
        "student__faculty", "supervisor", "department", "department__faculty",
    )
    if _is_global(user):
        return qs if user.is_admin_role else qs.exclude(status=Thesis.Status.DRAFT)
    if user.is_dekanat:
        return qs.filter(department__faculty=user.faculty).exclude(status=Thesis.Status.DRAFT)
    if user.is_kafedra:
        return qs.filter(department=user.department)
    if user.is_teacher:
        return qs.filter(supervisor=user)
    if user.is_student:
        return qs.filter(student=user)
    return qs.none()


def scope_works(user):
    from research.models import ScientificWork

    qs = ScientificWork.objects.select_related(
        "teacher", "teacher__department", "teacher__department__faculty"
    ).prefetch_related("students")
    if _is_global(user):
        return qs
    if user.is_dekanat:
        return qs.filter(teacher__department__faculty=user.faculty)
    if user.is_kafedra:
        return qs.filter(teacher__department=user.department)
    if user.is_teacher:
        return qs.filter(teacher=user)
    if user.is_student:
        return qs.filter(students=user, status=ScientificWork.Status.APPROVED)
    return qs.none()
