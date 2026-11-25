from django.conf import settings
from django.db import models


class Faculty(models.Model):
    name = models.CharField("Fakultet nomi", max_length=255, unique=True)
    short_name = models.CharField("Qisqa nomi", max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fakultet"
        verbose_name_plural = "Fakultetlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="departments", verbose_name="Fakultet")
    name = models.CharField("Kafedra nomi", max_length=255)
    short_name = models.CharField("Qisqa nomi", max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kafedra"
        verbose_name_plural = "Kafedralar"
        ordering = ["faculty__name", "name"]
        unique_together = ("faculty", "name")

    def __str__(self):
        return self.name


class Direction(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="directions", verbose_name="Fakultet")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="directions", verbose_name="Bitiruvchi kafedra",
    )
    code = models.CharField("Shifr", max_length=30, blank=True)
    name = models.CharField("Yo‘nalish nomi", max_length=255)

    class Meta:
        verbose_name = "Ta’lim yo‘nalishi"
        verbose_name_plural = "Ta’lim yo‘nalishlari"
        ordering = ["code", "name"]

    def __str__(self):
        return f"{self.code} — {self.name}" if self.code else self.name


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    level = models.CharField(max_length=20, default="info")  # info / success / warning / danger
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"

    def __str__(self):
        return self.title


class AuditLog(models.Model):
    """Platformadagi muhim harakatlar jurnali (kim, qachon, nima qildi)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Harakatlar jurnali"
        verbose_name_plural = "Harakatlar jurnali"

    def __str__(self):
        return self.action
