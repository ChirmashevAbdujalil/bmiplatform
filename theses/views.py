from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import DOCX, XLSX, _import_view
from core import documents
from core.filters import THESIS_LOOKUPS, apply_filters, filter_caption, filter_options, paginate
from core.notify import audit
from core.permissions import require_unit, role_required, scope_students, scope_theses

from . import services
from .forms import DecisionForm, ThesisForm
from .models import Decision, Thesis


def _filtered(request):
    qs = scope_theses(request.user)
    qs, active = apply_filters(qs, request.GET, THESIS_LOOKUPS)
    q = (request.GET.get("q") or "").strip()
    if q:
        cond = Q(topic__icontains=q) | Q(student__student_profile__student_id__icontains=q)
        for word in q.split():
            cond |= Q(student__last_name__icontains=word) | Q(student__first_name__icontains=word)
        qs = qs.filter(cond)
    if request.GET.get("mine") == "1":
        if request.user.is_dekanat:
            qs = qs.filter(status=Thesis.Status.PENDING, dekanat_decision="")
        elif request.user.is_sifat:
            qs = qs.filter(status=Thesis.Status.PENDING, sifat_decision="")
    return qs, active


def _can_decide(user, thesis):
    if thesis.status != Thesis.Status.PENDING:
        return False
    return user.is_dekanat or user.is_sifat or user.is_admin_role


@login_required
def thesis_list(request):
    user = request.user
    if user.is_student:
        return redirect("accounts:student_detail", user.pk)
    qs, active = _filtered(request)
    qs = qs.order_by("department__name", "student__student_profile__course",
                     "student__student_profile__group_name", "student__last_name")
    counts = {s: scope_theses(user).filter(status=s).count() for s, _ in Thesis.Status.choices}
    unassigned = scope_students(user).filter(thesis__isnull=True).count() if user.is_kafedra else 0
    years = scope_theses(user).values_list("academic_year", flat=True).distinct().order_by("-academic_year")
    supervisors = User.objects.filter(role=User.Role.TEACHER)
    if user.is_kafedra:
        supervisors = supervisors.filter(department=user.department)
    elif user.is_dekanat:
        supervisors = supervisors.filter(department__faculty=user.faculty)
    return render(request, "theses/list.html", {
        "page": paginate(request, qs, 30),
        "active": active,
        "counts": counts,
        "statuses": Thesis.Status.choices,
        "unassigned": unassigned,
        "years": years,
        "supervisors": supervisors.order_by("last_name") if user.is_manager else [],
        **filter_options(user, request.GET),
    })


@login_required
def thesis_detail(request, pk):
    thesis = get_object_or_404(scope_theses(request.user), pk=pk)
    if request.user.is_student and thesis.status == Thesis.Status.DRAFT:
        raise Http404
    load = services.supervisor_load(thesis.supervisor) if thesis.supervisor else 0
    return render(request, "theses/detail.html", {
        "thesis": thesis,
        "logs": thesis.logs.select_related("user")[:30],
        "decision_form": DecisionForm() if _can_decide(request.user, thesis) else None,
        "supervisor_load": load,
        "supervisor_max": getattr(getattr(thesis.supervisor, "teacher_profile", None), "max_students", None),
        "verify_url": settings.SITE_URL.rstrip("/") + reverse("core:verify", args=[thesis.verification_code]),
    })


@role_required(User.Role.KAFEDRA)
def thesis_form(request, pk=None):
    if (resp := require_unit(request, "department")) is not None:
        return resp
    department = request.user.department
    instance = get_object_or_404(scope_theses(request.user), pk=pk) if pk else Thesis(department=department)
    if pk and not instance.is_editable:
        messages.error(request, "Kelishuvdagi yoki tasdiqlangan mavzuni tahrirlab bo‘lmaydi.")
        return redirect("theses:detail", pk)
    initial = {}
    if not pk and request.GET.get("student"):
        initial["student"] = request.GET["student"]
    form = ThesisForm(request.POST or None, instance=instance, department=department, initial=initial)
    if request.method == "POST" and form.is_valid():
        thesis = form.save(commit=False)
        if not thesis.pk:
            thesis.created_by = request.user
        thesis.department = thesis.student.department or department
        thesis.save()
        services._log(thesis, request.user, "Mavzu va ilmiy rahbar biriktirildi" if not pk else "Tahrirlandi")
        tp = getattr(thesis.supervisor, "teacher_profile", None)
        load = services.supervisor_load(thesis.supervisor)
        if tp and load > tp.max_students:
            messages.warning(request, f"Diqqat: {thesis.supervisor.short_name} ga {load} ta talaba biriktirilgan "
                                      f"(belgilangan me’yor: {tp.max_students}).")
        if request.POST.get("send") == "1":
            try:
                services.send_for_approval(thesis, request.user)
                services.notify_sent([thesis])
                messages.success(request, "Saqlandi va kelishuvga yuborildi.")
            except services.WorkflowError as exc:
                messages.error(request, str(exc))
        else:
            messages.success(request, "Saqlandi (loyiha holatida).")
        return redirect("theses:detail", thesis.pk)
    return render(request, "theses/form.html", {"form": form, "thesis": instance if pk else None})


@require_POST
@role_required(User.Role.KAFEDRA)
def thesis_delete(request, pk):
    thesis = get_object_or_404(scope_theses(request.user), pk=pk)
    if thesis.status != Thesis.Status.DRAFT:
        messages.error(request, "Faqat loyiha holatidagi yozuvni o‘chirish mumkin.")
        return redirect("theses:detail", pk)
    audit(request.user, "BMI loyihasi o‘chirildi", str(thesis))
    thesis.delete()
    messages.success(request, "Yozuv o‘chirildi.")
    return redirect("theses:list")


@require_POST
@login_required
def thesis_bulk(request):
    """Ro‘yxatdan tanlanganlar ustida ommaviy amal: yuborish (kafedra) yoki kelishish (dekanat/sifat)."""
    action = request.POST.get("action")
    ids = request.POST.getlist("ids")
    theses = list(scope_theses(request.user).filter(pk__in=ids))
    if not theses:
        messages.warning(request, "Hech narsa tanlanmagan.")
        return redirect(request.POST.get("next") or "theses:list")
    done, errors = [], []
    for thesis in theses:
        try:
            if action == "send" and request.user.is_kafedra:
                services.send_for_approval(thesis, request.user)
            elif action == "approve" and _can_decide(request.user, thesis):
                services.decide(thesis, request.user, Decision.APPROVED, "Ommaviy kelishildi")
            else:
                continue
            done.append(thesis)
        except services.WorkflowError as exc:
            errors.append(str(exc))
    if action == "send" and done:
        services.notify_sent(done)
    if done:
        messages.success(request, f"{len(done)} ta yozuv bo‘yicha amal bajarildi.")
    for e in errors[:10]:
        messages.warning(request, e)
    return redirect(request.POST.get("next") or "theses:list")


@require_POST
@role_required(User.Role.KAFEDRA)
def thesis_send(request, pk):
    thesis = get_object_or_404(scope_theses(request.user), pk=pk)
    try:
        services.send_for_approval(thesis, request.user)
        services.notify_sent([thesis])
        messages.success(request, "Kelishuvga yuborildi. Dekanat va ta’lim sifati bo‘limi xabardor qilindi.")
    except services.WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("theses:detail", pk)


@require_POST
@role_required(User.Role.DEKANAT, User.Role.SIFAT)
def thesis_decide(request, pk):
    thesis = get_object_or_404(scope_theses(request.user), pk=pk)
    form = DecisionForm(request.POST)
    if form.is_valid():
        try:
            services.decide(thesis, request.user, form.cleaned_data["decision"], form.cleaned_data["comment"])
            messages.success(request, "Qaroringiz qayd etildi.")
        except services.WorkflowError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Qarorni tanlang.")
    return redirect("theses:detail", pk)


@login_required
def thesis_document(request, pk):
    thesis = get_object_or_404(scope_theses(request.user), pk=pk)
    if thesis.status != Thesis.Status.APPROVED:
        messages.error(request, "Hujjat faqat to‘liq tasdiqlangandan so‘ng shakllanadi.")
        return redirect("theses:detail", pk)
    verify_url = settings.SITE_URL.rstrip("/") + reverse("core:verify", args=[thesis.verification_code])
    buffer = documents.thesis_certificate(thesis, verify_url)
    name = thesis.student.student_profile.student_id if hasattr(thesis.student, "student_profile") else thesis.pk
    return FileResponse(buffer, as_attachment=True, filename=f"BMI_tasdiqlangan_{name}.docx", content_type=DOCX)


@role_required(User.Role.KAFEDRA, User.Role.DEKANAT, User.Role.SIFAT)
def thesis_export(request):
    """Tasdiqlangan mavzular ro‘yxati — fakultet/kafedra/kurs/yo‘nalish kesimida Word yoki Excel."""
    qs, _ = _filtered(request)
    if request.GET.get("all") != "1":
        qs = qs.filter(status=Thesis.Status.APPROVED)
    qs = qs.order_by("department__faculty__name", "department__name", "student__student_profile__direction__code",
                     "student__student_profile__course", "student__student_profile__group_name", "student__last_name")
    audit(request.user, "BMI ro‘yxati yuklab olindi", filter_caption(request.GET))
    if request.GET.get("format") == "xlsx":
        return FileResponse(documents.theses_list_xlsx(qs), as_attachment=True, filename="BMI_royxat.xlsx",
                            content_type=XLSX)
    caption = filter_caption(request.GET) or "Barcha tasdiqlangan mavzular"
    return FileResponse(documents.theses_list_docx(qs, caption), as_attachment=True,
                        filename="BMI_tasdiqlangan_royxat.docx", content_type=DOCX)


@role_required(User.Role.KAFEDRA)
def thesis_import(request):
    if (resp := require_unit(request, "department")) is not None:
        return resp
    return _import_view(request, "theses",
                        lambda f: services.import_theses(f, request.user.department, request.user))


def verify(request, code):
    """Ochiq sahifa: QR-kod orqali hujjat haqiqiyligini tekshirish."""
    thesis = Thesis.objects.select_related(
        "student", "supervisor", "department", "department__faculty", "student__student_profile"
    ).filter(verification_code=code).first()
    valid = thesis is not None and thesis.status == Thesis.Status.APPROVED
    return render(request, "theses/verify.html", {"thesis": thesis if valid else None, "valid": valid})
