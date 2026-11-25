from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StudentProfile, TeacherProfile, User


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    extra = 0


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "last_name", "first_name", "role", "faculty", "department", "is_active")
    list_filter = ("role", "faculty", "department", "is_active")
    search_fields = ("username", "last_name", "first_name", "middle_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Platforma", {"fields": ("role", "middle_name", "phone", "faculty", "department", "must_change_password")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Platforma", {"fields": ("role", "last_name", "first_name", "faculty", "department")}),
    )
    inlines = [TeacherProfileInline, StudentProfileInline]
