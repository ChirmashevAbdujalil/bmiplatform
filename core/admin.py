from django.contrib import admin

from .models import AuditLog, Department, Direction, Faculty, Notification


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 0


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name")
    search_fields = ("name",)
    inlines = [DepartmentInline]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty")
    list_filter = ("faculty",)
    search_fields = ("name",)


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "faculty", "department")
    list_filter = ("faculty",)
    search_fields = ("code", "name")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "details")
    search_fields = ("action", "details")
