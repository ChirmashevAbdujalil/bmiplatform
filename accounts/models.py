from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        KAFEDRA = "kafedra", "Kafedra"
        DEKANAT = "dekanat", "Dekanat"
        SIFAT = "sifat", "Ta’lim sifati bo‘limi"
        TEACHER = "teacher", "O‘qituvchi"
        STUDENT = "student", "Talaba"

    role = models.CharField("Rol", max_length=20, choices=Role.choices, default=Role.STUDENT)
    middle_name = models.CharField("Otasining ismi", max_length=150, blank=True)
    phone = models.CharField("Telefon", max_length=30, blank=True)
    faculty = models.ForeignKey(
        "core.Faculty", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users", verbose_name="Fakultet",
    )
    department = models.ForeignKey(
        "core.Department", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users", verbose_name="Kafedra",
    )
    must_change_password = models.BooleanField("Parolni almashtirishi shart", default=False)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name or self.username

    # --- Ism-familiya ---------------------------------------------------
    @property
    def full_name(self):
        return " ".join(p for p in [self.last_name, self.first_name, self.middle_name] if p).strip()

    @property
    def short_name(self):
        initials = "".join(f"{p[0]}." for p in [self.first_name, self.middle_name] if p)
        return f"{self.last_name} {initials}".strip() or self.username

    @property
    def initials(self):
        letters = (self.last_name[:1] + self.first_name[:1]).upper()
        return letters or self.username[:2].upper()

    # --- Rollar ---------------------------------------------------------
    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_kafedra(self):
        return self.role == self.Role.KAFEDRA

    @property
    def is_dekanat(self):
        return self.role == self.Role.DEKANAT

    @property
    def is_sifat(self):
        return self.role == self.Role.SIFAT

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_manager(self):
        """Boshqaruv rollari: kafedra, dekanat, ta’lim sifati, administrator."""
        return self.is_admin_role or self.role in (self.Role.KAFEDRA, self.Role.DEKANAT, self.Role.SIFAT)

    @property
    def unit_name(self):
        if self.role in (self.Role.KAFEDRA, self.Role.TEACHER, self.Role.STUDENT) and self.department:
            return self.department.name
        if self.faculty:
            return self.faculty.name
        return ""


class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    position = models.CharField("Lavozimi", max_length=150, blank=True)
    degree = models.CharField("Ilmiy darajasi", max_length=150, blank=True)
    academic_title = models.CharField("Ilmiy unvoni", max_length=150, blank=True)
    max_students = models.PositiveSmallIntegerField("Maksimal talabalar soni", default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "O‘qituvchi profili"
        verbose_name_plural = "O‘qituvchilar profillari"

    def __str__(self):
        return self.user.full_name


class StudentProfile(models.Model):
    class EducationForm(models.TextChoices):
        FULL = "kunduzgi", "Kunduzgi"
        PART = "sirtqi", "Sirtqi"
        EVENING = "kechki", "Kechki"
        DISTANCE = "masofaviy", "Masofaviy"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_id = models.CharField("Talaba ID (HEMIS)", max_length=50, unique=True)
    direction = models.ForeignKey(
        "core.Direction", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="students", verbose_name="Ta’lim yo‘nalishi",
    )
    course = models.PositiveSmallIntegerField("Kurs", default=4)
    group_name = models.CharField("Guruh", max_length=50, blank=True)
    education_form = models.CharField(
        "Ta’lim shakli", max_length=20, choices=EducationForm.choices, default=EducationForm.FULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Talaba profili"
        verbose_name_plural = "Talabalar profillari"

    def __str__(self):
        return f"{self.user.full_name} ({self.student_id})"
