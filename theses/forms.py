from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import User

from .models import Decision, Thesis


class ThesisForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Thesis
        fields = ["student", "topic", "supervisor", "academic_year"]
        widgets = {"topic": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, department=None, **kwargs):
        super().__init__(*args, **kwargs)
        students = User.objects.filter(role=User.Role.STUDENT).select_related("student_profile")
        teachers = User.objects.filter(role=User.Role.TEACHER, is_active=True)
        if department is not None:
            students = students.filter(department=department)
            teachers = teachers.filter(department=department)
        free = students.filter(thesis__isnull=True)
        if self.instance.pk:
            free = students.filter(pk=self.instance.student_id) | free
            self.fields["student"].disabled = True
        self.fields["student"].queryset = free.order_by("last_name", "first_name")
        self.fields["student"].label_from_instance = lambda u: (
            f"{u.full_name} — {getattr(getattr(u, 'student_profile', None), 'group_name', '')}"
        )
        self.fields["supervisor"].queryset = teachers.order_by("last_name")
        self.fields["supervisor"].label_from_instance = lambda u: u.full_name
        self.fields["supervisor"].required = True
        self._style()


class DecisionForm(StyledFormMixin, forms.Form):
    decision = forms.ChoiceField(
        label="Qaror", choices=[(Decision.APPROVED, "Kelishaman"), (Decision.RETURNED, "Qayta ishlashga qaytaraman")],
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(label="Izoh", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comment"].widget.attrs["class"] = "form-control"
