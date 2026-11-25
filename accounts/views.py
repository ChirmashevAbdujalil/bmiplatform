from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import documents
from core.filters import (
    STUDENT_LOOKUPS, TEACHER_LOOKUPS, apply_filters, filter_options, paginate, search_people,
)
from core.notify import audit
from core.permissions import require_unit, role_required, scope_students, scope_teachers, scope_works
from core.stats import annotate_teacher_stats
from core.word_import import ImportFormatError
from research.models import ScientificWork
from theses.models import Thesis

from . import services
from .forms import ImportForm, LoginForm, OwnProfileForm, StudentForm, StyledPasswordChangeForm, TeacherForm
from .models import StudentProfile, User

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def password_change(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Parol muvaffaqiyatli almashtirildi.")
        return redirect("core:dashboard")
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def my_profile(request):
    user = request.user
    if user.is_teacher:
        return redirect("accounts:teacher_detail", user.pk)
    if user.is_student:
        return redirect("accounts:student_detail", user.pk)
    form = OwnProfileForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ma’lumotlar saqlandi.")
        return redirect("accounts:my_profile")
    return render(request, "accounts/manager_profile.html", {"form": form})


@login_required
def edit_contacts(request):
    form = OwnProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Aloqa ma’lumotlari yangilandi.")
        return redirect("accounts:my_profile")
    return render(request, "accounts/contacts_form.html", {"form": form})


# ---------------------------------------------------------------------------
# O‘qituvchilar
# ---------------------------------------------------------------------------
@role_required(User.Role.KAFEDRA, User.Role.DEKANAT, User.Role.SIFAT)
def teacher_list(request):
    qs = scope_teachers(request.user)
    qs, active = apply_filters(qs, request.GET, TEACHER_LOOKUPS)
    qs = search_people(qs, request.GET.get("q"))
    qs = annotate_teacher_stats(qs)
    order = request.GET.get("order", "name")
    qs = qs.order_by("-total_score", "last_name") if order == "score" else qs.order_by("last_name", "first_name")
    return render(request, "accounts/teacher_list.html", {
        "page": paginate(request, qs),
        "active": active,
        "order": order,
        **filter_options(request.user, request.GET),
    })


def _get_teacher(request, pk):
    teacher = get_object_or_404(User.objects.select_related("department", "teacher_profile"), pk=pk,
                                role=User.Role.TEACHER)
    if request.user.pk != teacher.pk and not scope_teachers(request.user).filter(pk=pk).exists():
        raise PermissionDenied
    return teacher


@login_required
def teacher_detail(request, pk):
    teacher = _get_teacher(request, pk)
    theses = (
        Thesis.objects.filter(supervisor=teacher)
        .select_related("student", "student__student_profile", "student__student_profile__direction")
        .order_by("student__last_name")
    )
    works = ScientificWork.objects.filter(teacher=teacher).prefetch_related("students", "evaluations")
    approved = [w for w in works if w.status == ScientificWork.Status.APPROVED]
    total = sum((w.final_score or 0) for w in approved)
    by_type = {}
    for w in approved:
        by_type.setdefault(w.get_work_type_display(), [0, 0])
        by_type[w.get_work_type_display()][0] += 1
        by_type[w.get_work_type_display()][1] += float(w.final_score or 0)
    stats = annotate_teacher_stats(User.objects.filter(role=User.Role.TEACHER, department=teacher.department))
    ranking = list(stats.order_by("-total_score").values_list("pk", flat=True))
    rank = ranking.index(teacher.pk) + 1 if teacher.pk in ranking else None
    return render(request, "accounts/teacher_detail.html", {
        "teacher": teacher,
        "profile": getattr(teacher, "teacher_profile", None),
        "theses": theses,
        "works": works,
        "approved_count": len(approved),
        "pending_count": sum(1 for w in works if w.status == ScientificWork.Status.PENDING),
        "total_score": total,
        "by_type": sorted(by_type.items(), key=lambda x: -x[1][1]),
        "rank": rank,
        "rank_total": len(ranking),
        "avg_pct": round(float(total) / len(approved)) if approved else 0,
        "is_self": request.user.pk == teacher.pk,
    })


@login_required
def teacher_report(request, pk):
    teacher = _get_teacher(request, pk)
    works = list(ScientificWork.objects.filter(teacher=teacher).prefetch_related("students"))
    theses = list(Thesis.objects.filter(supervisor=teacher).select_related("student", "student__student_profile"))
    buffer = documents.teacher_report_docx(teacher, works, theses)
    return FileResponse(buffer, as_attachment=True, filename=f"ilmiy_faoliyat_{teacher.username}.docx",
                        content_type=DOCX)


@role_required(User.Role.KAFEDRA)
def teacher_form(request, pk=None):
    if (resp := require_unit(request, "department")) is not None:
        return resp
    instance = _get_teacher(request, pk) if pk else User(role=User.Role.TEACHER)
    form = TeacherForm(request.POST or None, instance=instance, manager=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            department = form.cleaned_data.get("department") or request.user.department
            user.department, user.faculty = department, department.faculty
            password = None
            if not user.pk:
                user.username = services.make_username(user.last_name, user.first_name, user.middle_name)
                password = services.generate_password()
                user.set_password(password)
                user.must_change_password = True
            user.save()
            form.save_profile(user)
        audit(request.user, "O‘qituvchi ma’lumotlari saqlandi", user.full_name)
        if password:
            messages.success(request, f"O‘qituvchi qo‘shildi. Login: {user.username}  •  Parol: {password}")
        else:
            messages.success(request, "O‘qituvchi ma’lumotlari yangilandi.")
        return redirect("accounts:teacher_detail", user.pk)
    return render(request, "accounts/person_form.html", {
        "form": form, "title": "O‘qituvchini tahrirlash" if pk else "Yangi o‘qituvchi",
        "back": "accounts:teacher_list",
    })


@role_required(User.Role.KAFEDRA)
def teacher_import(request):
    if (resp := require_unit(request, "department")) is not None:
        return resp
    return _import_view(request, "teachers", lambda f: services.import_teachers(f, request.user.department))


# ---------------------------------------------------------------------------
# Talabalar
# ---------------------------------------------------------------------------
@role_required(User.Role.KAFEDRA, User.Role.DEKANAT, User.Role.SIFAT)
def student_list(request):
    qs = scope_students(request.user)
    qs, active = apply_filters(qs, request.GET, STUDENT_LOOKUPS)
    qs = search_people(qs, request.GET.get("q"))
    thesis_state = request.GET.get("thesis", "")
    if thesis_state == "none":
        qs = qs.filter(thesis__isnull=True)
    elif thesis_state:
        qs = qs.filter(thesis__status=thesis_state)
    qs = qs.select_related("thesis", "thesis__supervisor").order_by(
        "student_profile__course", "student_profile__group_name", "last_name"
    )
    if request.GET.get("export") == "xlsx":
        return _students_xlsx(qs)
    return render(request, "accounts/student_list.html", {
        "page": paginate(request, qs),
        "active": active,
        "thesis_state": thesis_state,
        "thesis_statuses": Thesis.Status.choices,
        "forms": StudentProfile.EducationForm.choices,
        **filter_options(request.user, request.GET),
    })


def _students_xlsx(qs):
    import io

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Talabalar"
    ws.append(["№", "F.I.Sh.", "Talaba ID", "Fakultet", "Kafedra", "Yo‘nalish", "Kurs", "Guruh", "Ta’lim shakli",
               "BMI mavzusi", "Ilmiy rahbar", "BMI holati"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0B2E59")
    for i, s in enumerate(qs, start=1):
        p = getattr(s, "student_profile", None)
        t = getattr(s, "thesis", None) if hasattr(s, "thesis") else None
        ws.append([
            i, s.full_name, p.student_id if p else "", s.faculty.name if s.faculty else "",
            s.department.name if s.department else "", str(p.direction) if p and p.direction else "",
            p.course if p else "", p.group_name if p else "", p.get_education_form_display() if p else "",
            t.topic if t else "", t.supervisor.full_name if t and t.supervisor else "",
            t.get_status_display() if t else "Biriktirilmagan",
        ])
    for col, w in zip("ABCDEFGHIJKL", [5, 32, 14, 28, 28, 30, 6, 10, 12, 60, 30, 14]):
        ws.column_dimensions[col].width = w
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="talabalar.xlsx", content_type=XLSX)


def _get_student(request, pk):
    student = get_object_or_404(
        User.objects.select_related("faculty", "department", "student_profile", "student_profile__direction"),
        pk=pk, role=User.Role.STUDENT,
    )
    if request.user.pk != student.pk and not scope_students(request.user).filter(pk=pk).exists():
        raise PermissionDenied
    return student


@login_required
def student_detail(request, pk):
    student = _get_student(request, pk)
    thesis = Thesis.objects.filter(student=student).select_related(
        "supervisor", "supervisor__teacher_profile", "sent_by", "dekanat_by", "sifat_by", "department"
    ).first()
    viewer = request.user
    if thesis and viewer.is_student and thesis.status == Thesis.Status.DRAFT:
        thesis = None  # talaba loyiha holatidagi ma’lumotni ko‘rmaydi
    if viewer.is_student:
        works = ScientificWork.objects.filter(students=student, status=ScientificWork.Status.APPROVED)
    else:
        works = scope_works(viewer).filter(students=student) if not viewer.is_teacher else \
            ScientificWork.objects.filter(students=student, teacher=viewer)
    works = works.select_related("teacher").prefetch_related("students")
    return render(request, "accounts/student_detail.html", {
        "student": student,
        "profile": getattr(student, "student_profile", None),
        "thesis": thesis,
        "works": works,
        "works_score": sum((w.final_score or 0) for w in works if w.status == ScientificWork.Status.APPROVED),
        "is_self": viewer.pk == student.pk,
    })


@role_required(User.Role.DEKANAT)
def student_form(request, pk=None):
    if (resp := require_unit(request, "faculty")) is not None:
        return resp
    instance = _get_student(request, pk) if pk else User(role=User.Role.STUDENT)
    form = StudentForm(request.POST or None, instance=instance, manager=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.faculty = form.cleaned_data.get("faculty") or request.user.faculty
            user.department = form.cleaned_data.get("department") or (
                form.cleaned_data["direction"].department if form.cleaned_data.get("direction") else None
            )
            password = None
            if not user.pk:
                user.username = form.cleaned_data["student_id"]
                password = services.generate_password()
                user.set_password(password)
                user.must_change_password = True
            user.save()
            form.save_profile(user)
            if hasattr(user, "thesis") and user.department_id and user.thesis.department_id != user.department_id:
                Thesis.objects.filter(pk=user.thesis.pk).update(department=user.department)
        audit(request.user, "Talaba ma’lumotlari saqlandi", user.full_name)
        if password:
            messages.success(request, f"Talaba qo‘shildi. Login: {user.username}  •  Parol: {password}")
        else:
            messages.success(request, "Talaba ma’lumotlari yangilandi.")
        return redirect("accounts:student_detail", user.pk)
    return render(request, "accounts/person_form.html", {
        "form": form, "title": "Talabani tahrirlash" if pk else "Yangi talaba",
        "back": "accounts:student_list",
    })


@role_required(User.Role.DEKANAT)
def student_import(request):
    if (resp := require_unit(request, "faculty")) is not None:
        return resp
    return _import_view(request, "students", lambda f: services.import_students(f, request.user.faculty))


# ---------------------------------------------------------------------------
# Import, shablonlar, parollar
# ---------------------------------------------------------------------------
IMPORT_META = {
    "teachers": {"title": "O‘qituvchilarni Word fayldan biriktirish", "back": "accounts:teacher_list"},
    "students": {"title": "Talabalarni Word fayldan biriktirish", "back": "accounts:student_list"},
    "theses": {"title": "BMI mavzulari va ilmiy rahbarlarni Word fayldan biriktirish", "back": "theses:list"},
}


def _import_view(request, kind, handler):
    form = ImportForm(request.POST or None, request.FILES or None)
    result = None
    if request.method == "POST" and form.is_valid():
        try:
            result = handler(form.cleaned_data["file"])
        except ImportFormatError as exc:
            messages.error(request, str(exc))
        else:
            audit(request.user, f"Word import: {kind}", f"yangi: {result.created}, yangilangan: {result.updated}")
            if result.credentials:
                request.session["import_credentials"] = {"kind": kind, "rows": result.credentials}
            if result.total:
                messages.success(request, f"Import yakunlandi: {result.created} ta yangi, "
                                          f"{result.updated} ta yangilandi.")
    return render(request, "accounts/import.html", {
        "form": form, "result": result, "kind": kind, **IMPORT_META[kind],
        "template_spec": documents.TEMPLATES[kind],
    })


@login_required
def import_template(request, kind):
    if kind not in documents.TEMPLATES:
        raise Http404
    return FileResponse(documents.import_template(kind), as_attachment=True,
                        filename=f"shablon_{kind}.docx", content_type=DOCX)


@login_required
def credentials_download(request):
    data = request.session.get("import_credentials")
    if not data:
        raise Http404
    title = {"teachers": "O‘qituvchilar uchun login-parollar", "students": "Talabalar uchun login-parollar"}.get(
        data["kind"], "Login-parollar")
    return FileResponse(documents.credentials_docx(data["rows"], title), as_attachment=True,
                        filename="login_parollar.docx", content_type=DOCX)


@require_POST
@role_required(User.Role.KAFEDRA, User.Role.DEKANAT)
def reset_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    allowed = request.user.is_admin_role or (
        (request.user.is_kafedra and target.is_teacher and scope_teachers(request.user).filter(pk=pk).exists())
        or (request.user.is_dekanat and target.is_student and scope_students(request.user).filter(pk=pk).exists())
    )
    if not allowed:
        raise PermissionDenied
    password = services.generate_password()
    target.set_password(password)
    target.must_change_password = True
    target.save(update_fields=["password", "must_change_password"])
    audit(request.user, "Parol tiklandi", target.full_name)
    messages.success(request, f"{target.full_name} uchun yangi parol: {password}  (login: {target.username})")
    return redirect(request.POST.get("next") or "core:dashboard")
