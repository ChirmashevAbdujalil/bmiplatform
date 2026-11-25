from django.conf import settings


def platform(request):
    ctx = {"PLATFORM_NAME": settings.PLATFORM_NAME, "UNIVERSITY_NAME": settings.UNIVERSITY_NAME}
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return ctx
    unread = user.notifications.filter(is_read=False)
    ctx["unread_count"] = unread.count()
    ctx["latest_notifications"] = user.notifications.all()[:6]

    # Yon paneldagi "kutilayotgan vazifalar" belgilari
    from research.models import ScientificWork
    from research.services import evaluator_role
    from theses.models import Thesis

    from .permissions import scope_theses, scope_works

    badges = {}
    if user.is_dekanat:
        badges["theses"] = scope_theses(user).filter(status=Thesis.Status.PENDING, dekanat_decision="").count()
    elif user.is_sifat or user.is_admin_role:
        badges["theses"] = scope_theses(user).filter(status=Thesis.Status.PENDING, sifat_decision="").count()
    elif user.is_kafedra:
        badges["theses"] = scope_theses(user).filter(status=Thesis.Status.RETURNED).count()
    role = evaluator_role(user)
    if role:
        badges["works"] = scope_works(user).filter(status=ScientificWork.Status.PENDING).exclude(
            evaluations__role=role).count()
    elif user.is_teacher:
        badges["works"] = scope_works(user).filter(status=ScientificWork.Status.RETURNED).count()
    ctx["badges"] = badges
    return ctx
