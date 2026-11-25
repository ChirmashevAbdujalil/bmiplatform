from django.contrib import admin

from .models import Thesis, ThesisLog


class ThesisLogInline(admin.TabularInline):
    model = ThesisLog
    extra = 0
    readonly_fields = ("user", "action", "comment", "created_at")


@admin.register(Thesis)
class ThesisAdmin(admin.ModelAdmin):
    list_display = ("student", "topic", "supervisor", "department", "status", "academic_year")
    list_filter = ("status", "academic_year", "department__faculty", "department")
    search_fields = ("topic", "student__last_name", "student__first_name")
    raw_id_fields = ("student", "supervisor")
    inlines = [ThesisLogInline]
