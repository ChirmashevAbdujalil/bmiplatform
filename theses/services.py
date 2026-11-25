"""BMI kelishuv jarayoni (workflow) mantiqi."""
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.notify import notify, role_users
from core.word_import import normalize, read_rows, split_full_name

from .models import Decision, Thesis, ThesisLog


class WorkflowError(Exception):
    pass


def _log(thesis, user, action, comment=""):
    ThesisLog.objects.create(thesis=thesis, user=user, action=action, comment=comment)


def send_for_approval(thesis, user):
    if not thesis.is_editable:
        raise WorkflowError("Faqat loyiha yoki qaytarilgan holatdagi mavzuni yuborish mumkin.")
    if not thesis.supervisor_id:
        raise WorkflowError(f"{thesis.student.full_name}: ilmiy rahbar biriktirilmagan.")
    thesis.reset_approvals()
    thesis.status = Thesis.Status.PENDING
    thesis.sent_by = user
    thesis.sent_at = timezone.now()
    thesis.save()
    _log(thesis, user, "Kelishuvga yuborildi")
    return thesis


def notify_sent(theses):
    """Yuborilgan mavzular haqida dekanat va ta’lim sifati bo‘limini xabardor qilish."""
    by_faculty = {}
    for t in theses:
        faculty = t.department.faculty if t.department else None
        by_faculty.setdefault(faculty, []).append(t)
    url = reverse("theses:list") + "?status=pending"
    for faculty, items in by_faculty.items():
        title = f"Kelishuv uchun {len(items)} ta BMI mavzusi yuborildi"
        dept = items[0].department.name if items[0].department else ""
        notify(role_users(User.Role.DEKANAT, faculty=faculty) if faculty else [], title, dept, url, "warning")
        notify(role_users(User.Role.SIFAT), title, dept, url, "warning")


@transaction.atomic
def decide(thesis, user, decision, comment=""):
    if thesis.status != Thesis.Status.PENDING:
        raise WorkflowError("Bu mavzu kelishuv jarayonida emas.")
    if user.is_dekanat:
        prefix = "dekanat"
    elif user.is_sifat or user.is_admin_role:
        prefix = "sifat"
    else:
        raise WorkflowError("Sizda qaror qabul qilish huquqi yo‘q.")
    if decision == Decision.RETURNED and not comment.strip():
        raise WorkflowError("Qaytarish sababini izohda ko‘rsating.")

    setattr(thesis, f"{prefix}_decision", decision)
    setattr(thesis, f"{prefix}_by", user)
    setattr(thesis, f"{prefix}_at", timezone.now())
    setattr(thesis, f"{prefix}_comment", comment)
    label = "Dekanat" if prefix == "dekanat" else "Ta’lim sifati bo‘limi"
    url = reverse("theses:detail", args=[thesis.pk])
    kafedra = role_users(User.Role.KAFEDRA, department=thesis.department) if thesis.department else []

    if decision == Decision.RETURNED:
        thesis.status = Thesis.Status.RETURNED
        thesis.save()
        _log(thesis, user, f"{label}: qayta ishlashga qaytarildi", comment)
        notify(kafedra, f"BMI mavzusi qaytarildi: {thesis.student.short_name}", f"{label}: {comment}", url,
               "danger")
        return thesis

    _log(thesis, user, f"{label}: kelishildi", comment)
    if thesis.dekanat_decision == Decision.APPROVED and thesis.sifat_decision == Decision.APPROVED:
        thesis.status = Thesis.Status.APPROVED
        thesis.approved_at = timezone.now()
        thesis.save()
        _log(thesis, None, "Hujjat to‘liq tasdiqlandi")
        notify(list(kafedra) + [thesis.supervisor], f"BMI mavzusi tasdiqlandi: {thesis.student.short_name}",
               thesis.topic[:200], url, "success")
        notify([thesis.student], "Diplom ishi mavzusi va ilmiy rahbaringiz tasdiqlandi",
               "Tasdiqlangan hujjatni profilingizdan yuklab olishingiz mumkin.",
               reverse("accounts:student_detail", args=[thesis.student_id]), "success")
    else:
        thesis.save()
    return thesis


def supervisor_load(teacher):
    return Thesis.objects.filter(supervisor=teacher).count()


@transaction.atomic
def import_theses(file_obj, department, user):
    """Kafedra: Word fayldan talabalarga mavzu va ilmiy rahbar biriktirish."""
    from accounts.services import ImportResult

    result = ImportResult()
    teachers = list(User.objects.filter(role=User.Role.TEACHER, department=department))
    students = User.objects.filter(role=User.Role.STUDENT, department=department)

    def find_teacher(text):
        last, first, _ = split_full_name(text)
        if not last:
            return None
        for t in teachers:
            if t.last_name.lower() == last.lower() and (not first or t.first_name.lower().startswith(
                    first.lower().rstrip("."))):
                return t
        return None

    for row in read_rows(file_obj, "theses"):
        topic = normalize(row.get("topic"))
        if not topic:
            result.errors.append((row["_row"], "Mavzu ko‘rsatilmagan"))
            continue
        student = None
        sid = normalize(row.get("student_id")).replace(" ", "")
        if sid:
            student = students.filter(student_profile__student_id=sid).first()
        if student is None and row.get("full_name"):
            last, first, middle = split_full_name(row["full_name"])
            matches = students.filter(last_name__iexact=last, first_name__iexact=first)
            if middle:
                matches = matches.filter(middle_name__iexact=middle) or matches
            student = matches.first() if matches.count() == 1 else None
        if student is None:
            result.errors.append((row["_row"], f"Talaba topilmadi: {row.get('full_name') or sid}"))
            continue

        supervisor = find_teacher(row.get("supervisor", ""))
        if row.get("supervisor") and supervisor is None:
            result.errors.append((row["_row"], f"Ilmiy rahbar kafedrada topilmadi: {row['supervisor']}"))

        thesis = Thesis.objects.filter(student=student).first()
        if thesis and not thesis.is_editable:
            result.errors.append((row["_row"], f"{student.full_name}: mavzu kelishuvda yoki tasdiqlangan"))
            continue
        is_new = thesis is None
        if is_new:
            thesis = Thesis(student=student, created_by=user)
        thesis.topic = topic
        thesis.supervisor = supervisor or thesis.supervisor
        thesis.department = department
        thesis.save()
        _log(thesis, user, "Word fayldan biriktirildi" if is_new else "Word fayldan yangilandi")
        if is_new:
            result.created += 1
        else:
            result.updated += 1
    return result
