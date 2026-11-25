import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


def current_academic_year():
    from django.utils import timezone

    today = timezone.localdate()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"


class Decision(models.TextChoices):
    NONE = "", "Kutilmoqda"
    APPROVED = "approved", "Tasdiqlandi"
    RETURNED = "returned", "Qaytarildi"


class Thesis(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Loyiha"
        PENDING = "pending", "Kelishuvda"
        APPROVED = "approved", "Tasdiqlangan"
        RETURNED = "returned", "Qaytarilgan"

    student = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thesis",
        verbose_name="Talaba", limit_choices_to={"role": "student"},
    )
    topic = models.TextField("Diplom ishi mavzusi")
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="supervised_theses", verbose_name="Ilmiy rahbar", limit_choices_to={"role": "teacher"},
    )
    department = models.ForeignKey(
        "core.Department", on_delete=models.SET_NULL, null=True, related_name="theses", verbose_name="Kafedra"
    )
    academic_year = models.CharField("O‘quv yili", max_length=9, default=current_academic_year)
    status = models.CharField("Holati", max_length=20, choices=Status.choices, default=Status.DRAFT)

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    sent_at = models.DateTimeField(null=True, blank=True)

    dekanat_decision = models.CharField(max_length=20, choices=Decision.choices, blank=True, default="")
    dekanat_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    dekanat_at = models.DateTimeField(null=True, blank=True)
    dekanat_comment = models.TextField(blank=True)

    sifat_decision = models.CharField(max_length=20, choices=Decision.choices, blank=True, default="")
    sifat_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    sifat_at = models.DateTimeField(null=True, blank=True)
    sifat_comment = models.TextField(blank=True)

    approved_at = models.DateTimeField("Tasdiqlangan sana", null=True, blank=True)
    verification_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bitiruv malakaviy ishi"
        verbose_name_plural = "Bitiruv malakaviy ishlari"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.student.full_name}: {self.topic[:60]}"

    def get_absolute_url(self):
        return reverse("theses:detail", args=[self.pk])

    @property
    def is_editable(self):
        return self.status in (self.Status.DRAFT, self.Status.RETURNED)

    @property
    def status_color(self):
        return {
            self.Status.DRAFT: "secondary",
            self.Status.PENDING: "warning",
            self.Status.APPROVED: "success",
            self.Status.RETURNED: "danger",
        }.get(self.status, "secondary")

    @property
    def short_code(self):
        return str(self.verification_code).split("-")[0].upper()

    def reset_approvals(self):
        for prefix in ("dekanat", "sifat"):
            setattr(self, f"{prefix}_decision", "")
            setattr(self, f"{prefix}_by", None)
            setattr(self, f"{prefix}_at", None)
            setattr(self, f"{prefix}_comment", "")
        self.approved_at = None


class ThesisLog(models.Model):
    thesis = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.action
