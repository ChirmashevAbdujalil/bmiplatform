"""Foydalanuvchilarni Word fayldan import qilish va akkaunt yaratish."""
import re
import secrets
import string

from django.conf import settings
from django.db import transaction

from core.models import Department, Direction
from core.word_import import norm_key, normalize, parse_course, read_rows, split_full_name

from .models import StudentProfile, TeacherProfile, User

PASSWORD_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0OolI1")

LATIN_MAP = str.maketrans({"'": "", "‘": "", "’": "", "ʻ": "", "ʼ": "", "-": "", " ": ""})


def generate_password(length=None):
    length = length or settings.GENERATED_PASSWORD_LENGTH
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def make_username(last_name, first_name, middle_name=""):
    base = (last_name or "user").lower().translate(LATIN_MAP)
    base = re.sub(r"[^a-z0-9]", "", base) or "user"
    initials = re.sub(r"[^a-z]", "", ((first_name or "")[:1] + (middle_name or "")[:1]).lower())
    candidate = f"{base}.{initials}" if initials else base
    username, n = candidate, 1
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{candidate}{n}"
    return username


def find_department(text, faculty):
    key = norm_key(text)
    if not key:
        return None
    qs = Department.objects.filter(faculty=faculty) if faculty else Department.objects.all()
    for dept in qs:
        name = norm_key(dept.name)
        short = norm_key(dept.short_name)
        if key in (name, short) or key in name or name in key:
            return dept
    return None


EDU_FORMS = {norm_key(label): value for value, label in StudentProfile.EducationForm.choices}


class ImportResult:
    def __init__(self):
        self.created = 0
        self.updated = 0
        self.errors = []  # (qator, xabar)
        self.credentials = []  # {'name','username','password'}

    @property
    def total(self):
        return self.created + self.updated


@transaction.atomic
def import_teachers(file_obj, department):
    result = ImportResult()
    for row in read_rows(file_obj, "teachers"):
        full_name = normalize(row.get("full_name"))
        if not full_name:
            result.errors.append((row["_row"], "F.I.Sh. ko‘rsatilmagan"))
            continue
        last, first, middle = split_full_name(full_name)
        username = normalize(row.get("username"))

        user = None
        if username:
            user = User.objects.filter(username=username).first()
            if user and user.role != User.Role.TEACHER:
                result.errors.append((row["_row"], f"«{username}» logini boshqa rol uchun band"))
                continue
        if user is None:
            user = User.objects.filter(
                role=User.Role.TEACHER, last_name__iexact=last, first_name__iexact=first, department=department
            ).first()

        is_new = user is None
        if is_new:
            user = User(role=User.Role.TEACHER, username=username or make_username(last, first, middle))
            password = generate_password()
            user.set_password(password)
            user.must_change_password = True
            result.credentials.append({"name": full_name, "username": user.username, "password": password})

        user.last_name, user.first_name, user.middle_name = last, first, middle
        user.department = department
        user.faculty = department.faculty
        if row.get("phone"):
            user.phone = row["phone"]
        if row.get("email"):
            user.email = row["email"]
        user.save()

        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        for field in ("position", "degree", "academic_title"):
            if row.get(field):
                setattr(profile, field, row[field])
        profile.save()
        if is_new:
            result.created += 1
        else:
            result.updated += 1
    return result


@transaction.atomic
def import_students(file_obj, faculty):
    result = ImportResult()
    for row in read_rows(file_obj, "students"):
        full_name = normalize(row.get("full_name"))
        student_id = normalize(row.get("student_id")).replace(" ", "")
        if not full_name or not student_id:
            result.errors.append((row["_row"], "F.I.Sh. yoki Talaba ID ko‘rsatilmagan"))
            continue
        last, first, middle = split_full_name(full_name)

        department = find_department(row.get("department"), faculty)
        if row.get("department") and department is None:
            result.errors.append(
                (row["_row"], f"«{row['department']}» kafedrasi topilmadi — talaba kafedrasiz saqlandi")
            )

        direction = None
        code, dname = normalize(row.get("direction_code")), normalize(row.get("direction_name"))
        if code or dname:
            lookup = {"faculty": faculty}
            lookup.update({"code": code} if code else {"name__iexact": dname})
            direction = Direction.objects.filter(**lookup).first()
            if direction is None:
                direction = Direction.objects.create(
                    faculty=faculty, code=code, name=dname or code, department=department
                )
            elif department and direction.department is None:
                direction.department = department
                direction.save(update_fields=["department"])
        if department is None and direction is not None:
            department = direction.department

        profile = StudentProfile.objects.select_related("user").filter(student_id=student_id).first()
        is_new = profile is None
        if is_new:
            if User.objects.filter(username=student_id).exists():
                result.errors.append((row["_row"], f"«{student_id}» logini allaqachon band"))
                continue
            user = User(role=User.Role.STUDENT, username=student_id)
            password = generate_password()
            user.set_password(password)
            user.must_change_password = True
            result.credentials.append({"name": full_name, "username": student_id, "password": password})
        else:
            user = profile.user

        user.last_name, user.first_name, user.middle_name = last, first, middle
        user.faculty = faculty
        if department is not None:
            user.department = department
        if row.get("phone"):
            user.phone = row["phone"]
        user.save()

        if is_new:
            profile = StudentProfile(user=user, student_id=student_id)
        profile.direction = direction or profile.direction
        profile.course = parse_course(row.get("course"), profile.course or 4)
        if row.get("group"):
            profile.group_name = row["group"]
        form = EDU_FORMS.get(norm_key(row.get("education_form")))
        if form:
            profile.education_form = form
        profile.save()

        if is_new:
            result.created += 1
        else:
            result.updated += 1
    return result
