from decimal import Decimal

from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import User

from .models import Criterion, Evaluation, ScientificWork


class WorkForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScientificWork
        fields = [
            "title", "work_type", "level", "publication", "publication_date", "link",
            "students", "other_authors", "annotation", "file",
        ]
        widgets = {
            "publication_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "annotation": forms.Textarea(attrs={"rows": 3}),
            "students": forms.CheckboxSelectMultiple,
        }
        help_texts = {
            "students": "Ilmiy rahbarligingizdagi talabalardan hammualliflarni belgilang.",
            "other_authors": "Masalan: Karimov A.B., Toshpulatov D.",
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        students = User.objects.filter(role=User.Role.STUDENT, thesis__supervisor=teacher).order_by("last_name")
        self.fields["students"].queryset = students
        self.fields["students"].label_from_instance = lambda u: (
            f"{u.full_name} ({getattr(getattr(u, 'student_profile', None), 'group_name', '')})"
        )
        self._style()
        self.fields["students"].widget.attrs["class"] = "form-check-input"


class CriterionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ["name", "description", "max_score", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class EvaluationForm(forms.Form):
    decision = forms.ChoiceField(label="Qaror", choices=Evaluation.Decision.choices, widget=forms.RadioSelect)
    comment = forms.CharField(label="Izoh / tavsiya", required=False,
                              widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))

    def __init__(self, *args, criteria=(), instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.criteria = list(criteria)
        existing = {s.criterion_id: s.score for s in instance.scores.all()} if instance else {}
        for c in self.criteria:
            self.fields[f"c_{c.pk}"] = forms.DecimalField(
                label=c.name, min_value=Decimal("0"), max_value=Decimal(c.max_score), decimal_places=2,
                max_digits=5, help_text=c.description, initial=existing.get(c.pk),
                widget=forms.NumberInput(attrs={
                    "class": "form-control score-input", "step": "0.5", "min": 0, "max": c.max_score,
                }),
            )
        if instance:
            self.fields["decision"].initial = instance.decision
            self.fields["comment"].initial = instance.comment
        else:
            self.fields["decision"].initial = Evaluation.Decision.APPROVED

    def score_fields(self):
        return [(c, self[f"c_{c.pk}"]) for c in self.criteria]

    def clean(self):
        data = super().clean()
        if data.get("decision") == Evaluation.Decision.RETURNED and not (data.get("comment") or "").strip():
            self.add_error("comment", "Qaytarish sababini yozing.")
        return data
