from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.notify import notify, role_users

from .models import Criterion, Evaluation, EvaluationScore, ScientificWork, WorkLog

DEFAULT_CRITERIA = [
    ("Nashr darajasi va nufuzi", "Scopus/WoS, OAK ro‘yxati, respublika yoki OTM darajasidagi nashr.", 30),
    ("Ilmiy yangilik va dolzarblik", "Natijalarning ilmiy yangiligi, mavzuning dolzarbligi.", 20),
    ("Talabaning ishtirok darajasi", "Talabaning tadqiqotdagi real hissasi va mustaqilligi.", 20),
    ("Amaliy ahamiyati", "Natijalarning amaliyotga joriy etilishi, BMI bilan bog‘liqligi.", 15),
    ("Rasmiylashtirish sifati", "Talablarga muvofiqlik, iqtiboslar, akademik halollik.", 15),
]


def ensure_default_criteria():
    if not Criterion.objects.exists():
        Criterion.objects.bulk_create(
            Criterion(name=n, description=d, max_score=m, order=i) for i, (n, d, m) in enumerate(DEFAULT_CRITERIA, 1)
        )


def evaluator_role(user):
    if user.is_kafedra:
        return Evaluation.Role.KAFEDRA
    if user.is_dekanat:
        return Evaluation.Role.DEKANAT
    if user.is_sifat or user.is_admin_role:
        return Evaluation.Role.SIFAT
    return None


def log(work, user, action, comment=""):
    WorkLog.objects.create(work=work, user=user, action=action, comment=comment)


def evaluators_for(work):
    dept = work.teacher.department
    users = list(role_users(User.Role.SIFAT))
    if dept:
        users += list(role_users(User.Role.KAFEDRA, department=dept))
        users += list(role_users(User.Role.DEKANAT, faculty=dept.faculty))
    return users


def notify_submitted(work, resubmitted=False):
    title = ("Ilmiy ish qayta yuborildi: " if resubmitted else "Baholash uchun yangi ilmiy ish: ") + \
        work.teacher.short_name
    notify(evaluators_for(work), title, work.title[:200], reverse("research:detail", args=[work.pk]), "warning")


@transaction.atomic
def resubmit(work, user):
    work.evaluations.all().delete()
    work.status = ScientificWork.Status.PENDING
    work.final_score = None
    work.approved_at = None
    work.resubmitted_at = timezone.now()
    work.save()
    log(work, user, "Qayta ishlanib, baholashga yuborildi")
    notify_submitted(work, resubmitted=True)


@transaction.atomic
def save_evaluation(work, user, form):
    role = evaluator_role(user)
    evaluation, _ = Evaluation.objects.get_or_create(work=work, role=role, defaults={"evaluator": user})
    evaluation.evaluator = user
    evaluation.decision = form.cleaned_data["decision"]
    evaluation.comment = form.cleaned_data["comment"]
    total = Decimal("0")
    for criterion in form.criteria:
        score = form.cleaned_data[f"c_{criterion.pk}"]
        total += score
        EvaluationScore.objects.update_or_create(
            evaluation=evaluation, criterion=criterion, defaults={"score": score}
        )
    evaluation.scores.exclude(criterion__in=form.criteria).delete()
    evaluation.total = total
    evaluation.save()

    previous = work.status
    work.recompute()
    log(work, user, f"{evaluation.get_role_display()}: {evaluation.get_decision_display().lower()} "
                    f"({total} ball)", evaluation.comment)

    url = reverse("research:detail", args=[work.pk])
    if work.status == ScientificWork.Status.RETURNED and previous != ScientificWork.Status.RETURNED:
        notify([work.teacher], "Ilmiy ish qayta ishlashga qaytarildi", f"{evaluation.get_role_display()}: "
               f"{evaluation.comment}", url, "danger")
    elif work.status == ScientificWork.Status.APPROVED and previous != ScientificWork.Status.APPROVED:
        notify([work.teacher], f"Ilmiy ishingiz tasdiqlandi — {work.final_score} ball", work.title[:200], url,
               "success")
        notify(work.students.all(), "Hammualliflikdagi ilmiy ish tasdiqlandi",
               f"{work.title[:150]} — {work.final_score} ball", url, "success")
    return evaluation
