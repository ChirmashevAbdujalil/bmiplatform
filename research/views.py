from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from core.filters import WORK_LOOKUPS, apply_filters, filter_options, paginate
from core.notify import audit
from core.permissions import role_required, scope_teachers, scope_works

from . import services
from .forms import CriterionForm, EvaluationForm, WorkForm
from .models import Criterion, Evaluation, ScientificWork


@login_required
def work_list(request):
    user = request.user
    qs, active = apply_filters(scope_works(user), request.GET, WORK_LOOKUPS)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(publication__icontains=q) | Q(teacher__last_name__icontains=q))
    role = services.evaluator_role(user)
    if request.GET.get("mine") == "1" and role:
        qs = qs.filter(status=ScientificWork.Status.PENDING).exclude(evaluations__role=role)
    awaiting = 0
    if role:
        awaiting = scope_works(user).filter(status=ScientificWork.Status.PENDING).exclude(
            evaluations__role=role).count()
    teachers = scope_teachers(user).order_by("last_name") if user.is_manager else []
    return render(request, "research/list.html", {
        "page": paginate(request, qs.order_by("-submitted_at")),
        "active": active,
        "types": ScientificWork.WorkType.choices,
        "levels": ScientificWork.Level.choices,
        "statuses": ScientificWork.Status.choices,
        "teachers": teachers,
        "awaiting": awaiting,
        "role": role,
        **filter_options(user, request.GET),
    })


@login_required
def work_detail(request, pk):
    work = get_object_or_404(scope_works(request.user), pk=pk)
    criteria = list(Criterion.objects.filter(is_active=True))
    evaluations = {e.role: e for e in work.evaluations.select_related("evaluator").prefetch_related("scores")}
    role = services.evaluator_role(request.user)
    form = None
    if role and work.status == ScientificWork.Status.PENDING:
        form = EvaluationForm(criteria=criteria, instance=evaluations.get(role))

    # Mezonlar bo‘yicha matritsa: [mezon, kafedra, dekanat, sifat, o‘rtacha]
    matrix = []
    for c in criteria:
        row = [c]
        values = []
        for r in Evaluation.REQUIRED_ROLES:
            ev = evaluations.get(r)
            score = next((s.score for s in ev.scores.all() if s.criterion_id == c.pk), None) if ev else None
            row.append(score)
            if score is not None:
                values.append(score)
        row.append(round(sum(values) / len(values), 2) if values else None)
        matrix.append(row)

    return render(request, "research/detail.html", {
        "work": work,
        "criteria": criteria,
        "evaluations": [(r, label, evaluations.get(r)) for r, label in Evaluation.Role.choices],
        "matrix": matrix,
        "form": form,
        "my_role": role,
        "my_role_label": dict(Evaluation.Role.choices).get(role, ""),
        "logs": work.logs.select_related("user")[:30],
        "is_owner": request.user.pk == work.teacher_id,
    })


@login_required
def work_file(request, pk):
    work = get_object_or_404(scope_works(request.user), pk=pk)
    if not work.file:
        raise Http404
    return FileResponse(work.file.open("rb"), as_attachment=False, filename=work.file.name.rsplit("/", 1)[-1])


@role_required(User.Role.TEACHER)
def work_form(request, pk=None):
    teacher = request.user
    instance = None
    if pk:
        instance = get_object_or_404(ScientificWork, pk=pk, teacher=teacher)
        if instance.status == ScientificWork.Status.APPROVED:
            messages.error(request, "Tasdiqlangan ishni tahrirlab bo‘lmaydi.")
            return redirect("research:detail", pk)
    form = WorkForm(request.POST or None, request.FILES or None, instance=instance, teacher=teacher)
    if request.method == "POST" and form.is_valid():
        work = form.save(commit=False)
        work.teacher = teacher
        is_new = work.pk is None
        work.save()
        form.save_m2m()
        if is_new:
            services.log(work, teacher, "Baholash uchun yuborildi")
            services.notify_submitted(work)
            messages.success(request, "Ilmiy ish yuklandi va baholash uchun yuborildi.")
        else:
            services.resubmit(work, teacher)
            messages.success(request, "O‘zgartirishlar saqlandi va ish qayta baholashga yuborildi.")
        return redirect("research:detail", work.pk)
    return render(request, "research/form.html", {"form": form, "work": instance})


@require_POST
@role_required(User.Role.TEACHER)
def work_delete(request, pk):
    work = get_object_or_404(ScientificWork, pk=pk, teacher=request.user)
    if work.status == ScientificWork.Status.APPROVED:
        messages.error(request, "Tasdiqlangan ishni o‘chirib bo‘lmaydi.")
        return redirect("research:detail", pk)
    audit(request.user, "Ilmiy ish o‘chirildi", work.title)
    work.delete()
    messages.success(request, "Ilmiy ish o‘chirildi.")
    return redirect("research:list")


@require_POST
@role_required(User.Role.KAFEDRA, User.Role.DEKANAT, User.Role.SIFAT)
def work_evaluate(request, pk):
    work = get_object_or_404(scope_works(request.user), pk=pk)
    if work.status != ScientificWork.Status.PENDING:
        messages.error(request, "Bu ish hozir baholash jarayonida emas.")
        return redirect("research:detail", pk)
    criteria = list(Criterion.objects.filter(is_active=True))
    form = EvaluationForm(request.POST, criteria=criteria)
    if form.is_valid():
        services.save_evaluation(work, request.user, form)
        work.refresh_from_db()
        if work.status == ScientificWork.Status.APPROVED:
            messages.success(request, f"Baho saqlandi. Uchala tomon kelishdi — yakuniy ball: {work.final_score}.")
        else:
            messages.success(request, "Bahoingiz saqlandi.")
        return redirect("research:detail", pk)
    for field, errs in form.errors.items():
        label = form.fields[field].label if field in form.fields else ""
        messages.error(request, f"{label}: {' '.join(errs)}")
    return redirect("research:detail", pk)


# ---------------------------------------------------------------------------
# Baholash mezonlari (ta’lim sifati bo‘limi)
# ---------------------------------------------------------------------------
@role_required(User.Role.SIFAT)
def criteria_list(request, pk=None):
    instance = get_object_or_404(Criterion, pk=pk) if pk else None
    form = CriterionForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, "Baholash mezoni saqlandi", form.instance.name)
        messages.success(request, "Mezon saqlandi.")
        return redirect("research:criteria")
    criteria = Criterion.objects.all()
    return render(request, "research/criteria.html", {
        "criteria": criteria,
        "form": form,
        "editing": instance,
        "total": sum(c.max_score for c in criteria if c.is_active),
    })

