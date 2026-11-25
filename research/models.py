from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse


class Criterion(models.Model):
    """Ilmiy ishni baholash mezoni (ta’lim sifati bo‘limi boshqaradi)."""

    name = models.CharField("Mezon nomi", max_length=255)
    description = models.TextField("Izoh", blank=True)
    max_score = models.PositiveSmallIntegerField("Maksimal ball", default=20)
    order = models.PositiveSmallIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True)

    class Meta:
        verbose_name = "Baholash mezoni"
        verbose_name_plural = "Baholash mezonlari"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} (max {self.max_score})"


class ScientificWork(models.Model):
    class WorkType(models.TextChoices):
        ARTICLE = "article", "Ilmiy maqola"
        THESIS = "thesis", "Tezis (konferensiya)"
        MONOGRAPH = "monograph", "Monografiya"
        MANUAL = "manual", "O‘quv-uslubiy qo‘llanma"
        PATENT = "patent", "Patent / DGU guvohnomasi"
        PROJECT = "project", "Ilmiy loyiha / grant"
        OTHER = "other", "Boshqa ilmiy ish"

    class Level(models.TextChoices):
        SCOPUS = "scopus", "Xalqaro (Scopus / Web of Science)"
        INTERNATIONAL = "international", "Xalqaro"
        OAK = "oak", "OAK ro‘yxatidagi nashr"
        REPUBLIC = "republic", "Respublika miqyosida"
        LOCAL = "local", "OTM miqyosida"

    class Status(models.TextChoices):
        PENDING = "pending", "Baholashda"
        APPROVED = "approved", "Tasdiqlangan"
        RETURNED = "returned", "Qaytarilgan"

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scientific_works",
        verbose_name="O‘qituvchi", limit_choices_to={"role": "teacher"},
    )
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="coauthored_works", blank=True,
        verbose_name="Hammualliflar (talabalar)", limit_choices_to={"role": "student"},
    )
    title = models.CharField("Ish nomi", max_length=500)
    work_type = models.CharField("Ish turi", max_length=20, choices=WorkType.choices, default=WorkType.ARTICLE)
    level = models.CharField("Nashr darajasi", max_length=20, choices=Level.choices, default=Level.REPUBLIC)
    publication = models.CharField("Jurnal / konferensiya / nashriyot", max_length=500, blank=True)
    publication_date = models.DateField("Nashr sanasi", null=True, blank=True)
    link = models.URLField("Havola (DOI / URL)", blank=True)
    other_authors = models.CharField("Boshqa hammualliflar", max_length=500, blank=True)
    annotation = models.TextField("Annotatsiya", blank=True)
    file = models.FileField(
        "Fayl (PDF / Word)", upload_to="works/%Y/%m/",
        validators=[FileExtensionValidator(["pdf", "doc", "docx", "jpg", "jpeg", "png", "zip"])],
    )

    status = models.CharField("Holati", max_length=20, choices=Status.choices, default=Status.PENDING)
    final_score = models.DecimalField("Yakuniy ball", max_digits=6, decimal_places=2, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ilmiy ish"
        verbose_name_plural = "Ilmiy ishlar"
        ordering = ["-submitted_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("research:detail", args=[self.pk])

    @property
    def status_color(self):
        return {"pending": "warning", "approved": "success", "returned": "danger"}.get(self.status, "secondary")

    @property
    def max_total(self):
        return sum(c.max_score for c in Criterion.objects.filter(is_active=True)) or 100

    def recompute(self):
        """Uchala tomon baholasa — yakuniy ball (o‘rtacha) va holat hisoblanadi."""
        evaluations = list(self.evaluations.all())
        roles = {e.role for e in evaluations}
        if any(e.decision == Evaluation.Decision.RETURNED for e in evaluations):
            self.status = self.Status.RETURNED
            self.final_score = None
            self.approved_at = None
        elif roles >= set(Evaluation.REQUIRED_ROLES):
            from django.utils import timezone

            total = sum((e.total for e in evaluations), Decimal("0"))
            self.final_score = (total / len(evaluations)).quantize(Decimal("0.01"))
            self.status = self.Status.APPROVED
            self.approved_at = timezone.now()
        else:
            self.status = self.Status.PENDING
            self.final_score = None
        self.save(update_fields=["status", "final_score", "approved_at", "updated_at"])


class Evaluation(models.Model):
    class Role(models.TextChoices):
        KAFEDRA = "kafedra", "Kafedra mudiri"
        DEKANAT = "dekanat", "Dekanat"
        SIFAT = "sifat", "Ta’lim sifati bo‘limi"

    class Decision(models.TextChoices):
        APPROVED = "approved", "Tasdiqlayman"
        RETURNED = "returned", "Qayta ishlashga qaytaraman"

    REQUIRED_ROLES = ("kafedra", "dekanat", "sifat")

    work = models.ForeignKey(ScientificWork, on_delete=models.CASCADE, related_name="evaluations")
    role = models.CharField(max_length=20, choices=Role.choices)
    evaluator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.APPROVED)
    total = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    comment = models.TextField("Izoh", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("work", "role")
        ordering = ["role"]
        verbose_name = "Baholash"
        verbose_name_plural = "Baholashlar"

    def __str__(self):
        return f"{self.get_role_display()}: {self.total}"


class EvaluationScore(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="scores")
    criterion = models.ForeignKey(Criterion, on_delete=models.PROTECT)
    score = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ("evaluation", "criterion")


class WorkLog(models.Model):
    work = models.ForeignKey(ScientificWork, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
