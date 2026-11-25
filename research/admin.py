from django.contrib import admin

from .models import Criterion, Evaluation, EvaluationScore, ScientificWork


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ("name", "max_score", "order", "is_active")
    list_editable = ("max_score", "order", "is_active")


class EvaluationScoreInline(admin.TabularInline):
    model = EvaluationScore
    extra = 0


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("work", "role", "evaluator", "decision", "total")
    inlines = [EvaluationScoreInline]


@admin.register(ScientificWork)
class ScientificWorkAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "work_type", "level", "status", "final_score")
    list_filter = ("status", "work_type", "level")
    search_fields = ("title", "teacher__last_name")
    filter_horizontal = ("students",)
