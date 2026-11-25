"""Fakultet / kafedra / kurs / yo‘nalish kesimidagi filtrlar."""
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Department, Direction, Faculty

STUDENT_LOOKUPS = {
    "faculty": "faculty_id",
    "department": "department_id",
    "direction": "student_profile__direction_id",
    "course": "student_profile__course",
    "group": "student_profile__group_name__iexact",
    "form": "student_profile__education_form",
}

THESIS_LOOKUPS = {
    "faculty": "department__faculty_id",
    "department": "department_id",
    "direction": "student__student_profile__direction_id",
    "course": "student__student_profile__course",
    "group": "student__student_profile__group_name__iexact",
    "supervisor": "supervisor_id",
    "status": "status",
    "year": "academic_year",
}

TEACHER_LOOKUPS = {
    "faculty": "department__faculty_id",
    "department": "department_id",
}

WORK_LOOKUPS = {
    "faculty": "teacher__department__faculty_id",
    "department": "teacher__department_id",
    "teacher": "teacher_id",
    "type": "work_type",
    "level": "level",
    "status": "status",
}


def apply_filters(qs, params, lookups):
    active = {}
    for key, lookup in lookups.items():
        value = (params.get(key) or "").strip()
        if value:
            qs = qs.filter(**{lookup: value})
            active[key] = value
    return qs, active


def search_people(qs, q, prefix=""):
    q = (q or "").strip()
    if not q:
        return qs
    cond = Q()
    for word in q.split():
        cond &= (
            Q(**{f"{prefix}last_name__icontains": word})
            | Q(**{f"{prefix}first_name__icontains": word})
            | Q(**{f"{prefix}middle_name__icontains": word})
            | Q(**{f"{prefix}username__icontains": word})
        )
    return qs.filter(cond)


def filter_options(user, params):
    faculties = Faculty.objects.all()
    departments = Department.objects.select_related("faculty")
    directions = Direction.objects.all()
    if user.is_dekanat and user.faculty_id:
        faculties = faculties.filter(pk=user.faculty_id)
        departments = departments.filter(faculty_id=user.faculty_id)
        directions = directions.filter(faculty_id=user.faculty_id)
    elif (user.is_kafedra or user.is_teacher) and user.department_id:
        faculties = faculties.filter(pk=user.department.faculty_id)
        departments = departments.filter(pk=user.department_id)
        directions = directions.filter(Q(department_id=user.department_id) | Q(faculty_id=user.department.faculty_id))
    faculty_id = (params.get("faculty") or "").strip()
    if faculty_id.isdigit():
        departments = departments.filter(faculty_id=faculty_id)
        directions = directions.filter(faculty_id=faculty_id)
    return {
        "faculties": faculties,
        "departments": departments,
        "directions": directions,
        "courses": range(1, 7),
    }


def filter_caption(params):
    """Eksport hujjati uchun filtrlarni matn ko‘rinishida tavsiflaydi."""
    parts = []
    if params.get("faculty", "").isdigit():
        f = Faculty.objects.filter(pk=params["faculty"]).first()
        if f:
            parts.append(f"Fakultet: {f.name}")
    if params.get("department", "").isdigit():
        d = Department.objects.filter(pk=params["department"]).first()
        if d:
            parts.append(f"Kafedra: {d.name}")
    if params.get("direction", "").isdigit():
        d = Direction.objects.filter(pk=params["direction"]).first()
        if d:
            parts.append(f"Yo‘nalish: {d}")
    if params.get("course"):
        parts.append(f"Kurs: {params['course']}")
    if params.get("group"):
        parts.append(f"Guruh: {params['group']}")
    if params.get("year"):
        parts.append(f"O‘quv yili: {params['year']}")
    return " • ".join(parts)


def paginate(request, qs, per_page=25):
    paginator = Paginator(qs, per_page)
    return paginator.get_page(request.GET.get("page"))
