"""Statistik hisob-kitoblar uchun umumiy annotatsiyalar."""
from decimal import Decimal

from django.db.models import Count, DecimalField, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce


def annotate_teacher_stats(qs):
    from research.models import ScientificWork
    from theses.models import Thesis

    approved = ScientificWork.objects.filter(teacher=OuterRef("pk"), status=ScientificWork.Status.APPROVED)
    score_sq = approved.values("teacher").annotate(s=Sum("final_score")).values("s")
    works_sq = approved.values("teacher").annotate(c=Count("id")).values("c")
    pending_sq = (
        ScientificWork.objects.filter(teacher=OuterRef("pk"), status=ScientificWork.Status.PENDING)
        .values("teacher").annotate(c=Count("id")).values("c")
    )
    students_sq = (
        Thesis.objects.filter(supervisor=OuterRef("pk")).values("supervisor").annotate(c=Count("id")).values("c")
    )
    return qs.annotate(
        total_score=Coalesce(
            Subquery(score_sq, output_field=DecimalField()), Value(Decimal("0")), output_field=DecimalField()
        ),
        works_count=Coalesce(Subquery(works_sq, output_field=IntegerField()), Value(0)),
        pending_count=Coalesce(Subquery(pending_sq, output_field=IntegerField()), Value(0)),
        students_count=Coalesce(Subquery(students_sq, output_field=IntegerField()), Value(0)),
    )
