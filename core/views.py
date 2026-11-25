from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import StyledFormMixin
from accounts.models import User
from accounts.services import generate_password
from research.models import ScientificWork
from research.services import evaluator_role
from theses.models import Thesis

from .filters import filter_options, paginate
from .models import AuditLog, Department, Direction, Faculty, Notification
from .notify import audit
from .permissions import role_required, scope_students, scope_teachers, scope_theses, scope_works
from .stats import annotate_teacher_stats


@login_required
def dashboard(request):
    user = request.user
    if user.is_student:
        return redirect("accounts:student_detail", user.pk)
    if user.is_teacher:
        return redirect("accounts:teacher_detail", user.pk)

    theses = scope_theses(user)
    works = scope_works(user)
    thesis_counts = dict(theses.values_list("status").annotate(c=Count("id")))
    role = evaluator_role(user)
    ctx = {
        "teachers_count": scope_teachers(user).count(),
        "students_count": scope_students(user).count(),
        "thesis_counts": {s: thesis_counts.get(s, 0) for s, _ in Thesis.Status.choices},
        "thesis_total": sum(thesis_counts.values()),
        "works_approved": works.filter(status=ScientificWork.Status.APPROVED).count(),
        "works_pending": works.filter(status=ScientificWork.Status.PENDING).count(),
        "works_awaiting_me": works.filter(status=ScientificWork.Status.PENDING).exclude(
            evaluations__role=role).count() if role else 0,
        "avg_score": works.filter(status=ScientificWork.Status.APPROVED).aggregate(a=Avg("final_score"))["a"],
        "recent_works": works.order_by("-submitted_at")[:6],
        "top_teachers": annotate_teacher_stats(scope_teachers(user)).order_by("-total_score")[:5],
    }
    if user.is_kafedra:
        ctx["unassigned"] = scope_students(user).filter(thesis__isnull=True).count()
        ctx["returned"] = theses.filter(status=Thesis.Status.RETURNED)[:6]
    if user.is_dekanat:
        ctx["awaiting_theses"] = theses.filter(status=Thesis.Status.PENDING, dekanat_decision="").count()
    elif user.is_sifat or user.is_admin_role:
        ctx["awaiting_theses"] = theses.filter(status=Thesis.Status.PENDING, sifat_decision="").count()
    ctx["pending_theses"] = theses.filter(status=Thesis.Status.PENDING).order_by("sent_at")[:6]
    return render(request, "core/dashboard.html", ctx)


# ---------------------------------------------------------------------------
# Statistika
# ---------------------------------------------------------------------------
@login_required
def statistics(request):
    user = request.user
    if not user.is_manager:
        return redirect("core:dashboard")
    params = request.GET
    teachers = scope_teachers(user)
    theses = scope_theses(user)
    works = scope_works(user)
    students = scope_students(user)

    if params.get("faculty", "").isdigit():
        fid = params["faculty"]
        teachers = teachers.filter(department__faculty_id=fid)
        theses = theses.filter(department__faculty_id=fid)
        works = works.filter(teacher__department__faculty_id=fid)
        students = students.filter(faculty_id=fid)
    if params.get("department", "").isdigit():
        did = params["department"]
        teachers = teachers.filter(department_id=did)
        theses = theses.filter(department_id=did)
        works = works.filter(teacher__department_id=did)
        students = students.filter(department_id=did)
    if params.get("year"):
        theses = theses.filter(academic_year=params["year"])

    approved_works = works.filter(status=ScientificWork.Status.APPROVED)

    # Diagrammalar uchun ma’lumotlar
    status_counts = dict(theses.values_list("status").annotate(c=Count("id")))
    thesis_status = {
        "labels": [label for _, label in Thesis.Status.choices],
        "data": [status_counts.get(s, 0) for s, _ in Thesis.Status.choices],
    }

    dept_rows = (
        theses.values("department__name", "department__short_name")
        .annotate(
            approved=Count("id", filter=Q(status=Thesis.Status.APPROVED)),
            pending=Count("id", filter=Q(status=Thesis.Status.PENDING)),
            returned=Count("id", filter=Q(status=Thesis.Status.RETURNED)),
            draft=Count("id", filter=Q(status=Thesis.Status.DRAFT)),
        )
        .order_by("department__name")
    )
    thesis_by_dept = {
        "labels": [r["department__short_name"] or r["department__name"] or "—" for r in dept_rows],
        "full": [r["department__name"] or "—" for r in dept_rows],
        "approved": [r["approved"] for r in dept_rows],
        "pending": [r["pending"] for r in dept_rows],
        "returned": [r["returned"] for r in dept_rows],
        "draft": [r["draft"] for r in dept_rows],
    }

    type_map = dict(ScientificWork.WorkType.choices)
    type_rows = approved_works.values("work_type").annotate(c=Count("id"), s=Sum("final_score")).order_by("-c")
    works_by_type = {
        "labels": [type_map.get(r["work_type"], r["work_type"]) for r in type_rows],
        "data": [r["c"] for r in type_rows],
    }
    level_map = dict(ScientificWork.Level.choices)
    level_rows = approved_works.values("level").annotate(c=Count("id")).order_by("-c")
    works_by_level = {
        "labels": [level_map.get(r["level"], r["level"]) for r in level_rows],
        "data": [r["c"] for r in level_rows],
    }

    since = timezone.now() - timedelta(days=365)
    month_rows = (
        works.filter(submitted_at__gte=since).annotate(m=TruncMonth("submitted_at")).values("m")
        .annotate(total=Count("id"), approved=Count("id", filter=Q(status=ScientificWork.Status.APPROVED)))
        .order_by("m")
    )
    monthly = {
        "labels": [r["m"].strftime("%m.%Y") for r in month_rows],
        "total": [r["total"] for r in month_rows],
        "approved": [r["approved"] for r in month_rows],
    }

    ranked = list(annotate_teacher_stats(teachers).order_by("-total_score", "last_name"))
    top = [t for t in ranked if t.total_score][:10]
    top_teachers = {
        "labels": [t.short_name for t in top],
        "data": [float(t.total_score) for t in top],
    }

    departments = {}
    for t in ranked:
        key = t.department.name if t.department else "—"
        d = departments.setdefault(key, {"name": key, "teachers": 0, "works": 0, "score": Decimal("0"),
                                         "students": 0})
        d["teachers"] += 1
        d["works"] += t.works_count
        d["score"] += t.total_score or 0
        d["students"] += t.students_count
    dept_ranking = sorted(departments.values(), key=lambda d: -d["score"])
    for d in dept_ranking:
        d["avg"] = (d["score"] / d["teachers"]) if d["teachers"] else 0

    participating = students.filter(
        coauthored_works__status=ScientificWork.Status.APPROVED).distinct().count()
    students_total = students.count()

    charts = {
        "thesisStatus": thesis_status,
        "thesisByDept": thesis_by_dept,
        "worksByType": works_by_type,
        "worksByLevel": works_by_level,
        "monthly": monthly,
        "topTeachers": top_teachers,
    }
    return render(request, "core/statistics.html", {
        "charts_json": charts,
        "kpi": {
            "teachers": len(ranked),
            "students": students_total,
            "theses": sum(status_counts.values()),
            "theses_approved": status_counts.get(Thesis.Status.APPROVED, 0),
            "works_approved": approved_works.count(),
            "works_pending": works.filter(status=ScientificWork.Status.PENDING).count(),
            "score_sum": approved_works.aggregate(s=Sum("final_score"))["s"] or 0,
            "score_avg": approved_works.aggregate(a=Avg("final_score"))["a"] or 0,
            "participation": round(participating * 100 / students_total, 1) if students_total else 0,
        },
        "ranked": ranked,
        "dept_ranking": dept_ranking,
        "years": Thesis.objects.values_list("academic_year", flat=True).distinct().order_by("-academic_year"),
        "active": {k: v for k, v in params.items() if v},
        **filter_options(user, params),
    })


# ---------------------------------------------------------------------------
# Bildirishnomalar
# ---------------------------------------------------------------------------
@login_required
def notifications(request):
    qs = request.user.notifications.all()
    return render(request, "core/notifications.html", {"page": paginate(request, qs, 30)})


@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=["is_read"])
    return redirect(n.url or "core:notifications")


@require_POST
@login_required
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect(request.POST.get("next") or "core:notifications")


# ---------------------------------------------------------------------------
# Tuzilma va boshqaruv hisoblari (administrator)
# ---------------------------------------------------------------------------
class FacultyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ["name", "short_name"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["faculty", "name", "short_name"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class DirectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Direction
        fields = ["faculty", "department", "code", "name"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class StaffForm(StyledFormMixin, forms.ModelForm):
    role = forms.ChoiceField(label="Rol", choices=[
        (User.Role.KAFEDRA, "Kafedra (mudir)"), (User.Role.DEKANAT, "Dekanat"),
        (User.Role.SIFAT, "Ta’lim sifati bo‘limi"), (User.Role.ADMIN, "Administrator"),
    ])

    class Meta:
        model = User
        fields = ["role", "username", "last_name", "first_name", "middle_name", "phone", "faculty", "department"]
        labels = {"last_name": "Familiya", "first_name": "Ism", "username": "Login"}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["last_name"].required = True
        self.fields["first_name"].required = True
        self._style()

    def clean(self):
        data = super().clean()
        role = data.get("role")
        if role == User.Role.KAFEDRA and not data.get("department"):
            self.add_error("department", "Kafedra hisobiga kafedra biriktirilishi shart.")
        if role == User.Role.DEKANAT and not data.get("faculty"):
            self.add_error("faculty", "Dekanat hisobiga fakultet biriktirilishi shart.")
        if role == User.Role.KAFEDRA and data.get("department"):
            data["faculty"] = data["department"].faculty
        return data


STRUCTURE_FORMS = {"faculty": FacultyForm, "department": DepartmentForm, "direction": DirectionForm}
STRUCTURE_MODELS = {"faculty": Faculty, "department": Department, "direction": Direction}


@role_required(User.Role.ADMIN)
def structure(request):
    forms_ = {k: f(prefix=k) for k, f in STRUCTURE_FORMS.items()}
    if request.method == "POST":
        kind = request.POST.get("kind")
        if kind in STRUCTURE_FORMS:
            form = STRUCTURE_FORMS[kind](request.POST, prefix=kind)
            if form.is_valid():
                obj = form.save()
                audit(request.user, "Tuzilma elementi qo‘shildi", str(obj))
                messages.success(request, f"Qo‘shildi: {obj}")
                return redirect("core:structure")
            forms_[kind] = form
    faculties = Faculty.objects.prefetch_related("departments", "directions").annotate(
        students=Count("users", filter=Q(users__role=User.Role.STUDENT)))
    return render(request, "core/structure.html", {"forms": forms_, "faculties": faculties})


@require_POST
@role_required(User.Role.ADMIN)
def structure_delete(request, kind, pk):
    model = STRUCTURE_MODELS.get(kind)
    if model is None:
        return redirect("core:structure")
    obj = get_object_or_404(model, pk=pk)
    audit(request.user, "Tuzilma elementi o‘chirildi", str(obj))
    obj.delete()
    messages.success(request, "O‘chirildi.")
    return redirect("core:structure")


@role_required(User.Role.ADMIN)
def staff_accounts(request):
    form = StaffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        password = generate_password()
        user.set_password(password)
        user.must_change_password = True
        user.faculty = form.cleaned_data.get("faculty")
        user.save()
        audit(request.user, "Boshqaruv hisobi yaratildi", f"{user.username} ({user.get_role_display()})")
        messages.success(request, f"Hisob yaratildi. Login: {user.username}  •  Parol: {password}")
        return redirect("core:staff")
    staff = User.objects.filter(role__in=[User.Role.KAFEDRA, User.Role.DEKANAT, User.Role.SIFAT, User.Role.ADMIN]) \
        .select_related("faculty", "department").order_by("role", "last_name")
    return render(request, "core/staff.html", {"form": form, "staff": staff})


@require_POST
@role_required(User.Role.ADMIN)
def staff_reset(request, pk):
    target = get_object_or_404(User, pk=pk)
    password = generate_password()
    target.set_password(password)
    target.must_change_password = True
    target.save(update_fields=["password", "must_change_password"])
    audit(request.user, "Parol tiklandi", target.username)
    messages.success(request, f"{target.username} uchun yangi parol: {password}")
    return redirect(request.POST.get("next") or "core:staff")


@require_POST
@role_required(User.Role.ADMIN)
def staff_toggle(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "O‘z hisobingizni bloklay olmaysiz.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        messages.success(request, f"{target.username}: {'faollashtirildi' if target.is_active else 'bloklandi'}.")
    return redirect("core:staff")


@role_required(User.Role.SIFAT)
def audit_log(request):
    qs = AuditLog.objects.select_related("user")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(action__icontains=q) | Q(details__icontains=q) | Q(user__username__icontains=q))
    return render(request, "core/audit.html", {"page": paginate(request, qs, 50)})
