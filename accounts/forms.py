from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from core.models import Department, Direction, Faculty

from .models import StudentProfile, TeacherProfile, User


class StyledFormMixin:
    """Barcha maydonlarga Bootstrap klasslarini qo‘shadi."""

    def _style(self):
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Login"
        self.fields["password"].label = "Parol"
        self.fields["username"].widget.attrs["placeholder"] = "Login yoki Talaba ID"
        self.fields["password"].widget.attrs["placeholder"] = "Parol"
        self._style()


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Joriy parol"
        self.fields["new_password1"].label = "Yangi parol"
        self.fields["new_password2"].label = "Yangi parolni takrorlang"
        self.fields["new_password1"].help_text = "Kamida 8 ta belgi."
        self._style()


class ImportForm(StyledFormMixin, forms.Form):
    file = forms.FileField(label="Word fayl (.docx)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["accept"] = ".docx"
        self._style()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".docx"):
            raise forms.ValidationError("Faqat .docx formatidagi fayl qabul qilinadi.")
        return f


class BaseUserForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["last_name", "first_name", "middle_name", "phone", "email"]
        labels = {"last_name": "Familiya", "first_name": "Ism", "email": "E-mail"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["last_name"].required = True
        self.fields["first_name"].required = True


class TeacherForm(BaseUserForm):
    position = forms.CharField(label="Lavozimi", required=False)
    degree = forms.CharField(label="Ilmiy darajasi", required=False)
    academic_title = forms.CharField(label="Ilmiy unvoni", required=False)
    max_students = forms.IntegerField(label="Maksimal talabalar soni", min_value=1, max_value=50, initial=10)
    department = forms.ModelChoiceField(label="Kafedra", queryset=Department.objects.all(), required=False)

    def __init__(self, *args, manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(self.instance, "teacher_profile", None) if self.instance.pk else None
        if profile:
            for f in ("position", "degree", "academic_title", "max_students"):
                self.fields[f].initial = getattr(profile, f)
        if manager is not None and manager.is_kafedra:
            del self.fields["department"]
        else:
            self.fields["department"].required = True
            self.fields["department"].initial = self.instance.department_id
        self._style()

    def save_profile(self, user):
        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        for f in ("position", "degree", "academic_title", "max_students"):
            setattr(profile, f, self.cleaned_data[f])
        profile.save()
        return profile


class StudentForm(BaseUserForm):
    student_id = forms.CharField(label="Talaba ID (HEMIS)")
    direction = forms.ModelChoiceField(label="Ta’lim yo‘nalishi", queryset=Direction.objects.all(), required=False)
    department = forms.ModelChoiceField(label="Bitiruvchi kafedra", queryset=Department.objects.all(), required=False)
    course = forms.IntegerField(label="Kurs", min_value=1, max_value=6, initial=4)
    group_name = forms.CharField(label="Guruh", required=False)
    education_form = forms.ChoiceField(label="Ta’lim shakli", choices=StudentProfile.EducationForm.choices)
    faculty = forms.ModelChoiceField(label="Fakultet", queryset=Faculty.objects.all(), required=False)

    def __init__(self, *args, manager=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(self.instance, "student_profile", None) if self.instance.pk else None
        if profile:
            self.fields["student_id"].initial = profile.student_id
            self.fields["direction"].initial = profile.direction_id
            self.fields["course"].initial = profile.course
            self.fields["group_name"].initial = profile.group_name
            self.fields["education_form"].initial = profile.education_form
        self.fields["department"].initial = self.instance.department_id
        self.fields["faculty"].initial = self.instance.faculty_id
        self.profile = profile
        if manager is not None and manager.is_dekanat:
            del self.fields["faculty"]
            self.fields["direction"].queryset = Direction.objects.filter(faculty=manager.faculty)
            self.fields["department"].queryset = Department.objects.filter(faculty=manager.faculty)
        else:
            self.fields["faculty"].required = True
        self._style()

    def clean_student_id(self):
        sid = self.cleaned_data["student_id"].strip()
        qs = StudentProfile.objects.filter(student_id=sid)
        if self.profile:
            qs = qs.exclude(pk=self.profile.pk)
        if qs.exists():
            raise forms.ValidationError("Bu ID bilan talaba allaqachon mavjud.")
        if not self.profile and User.objects.filter(username=sid).exists():
            raise forms.ValidationError("Bu ID login sifatida band.")
        return sid

    def save_profile(self, user):
        profile = self.profile or StudentProfile(user=user)
        profile.student_id = self.cleaned_data["student_id"]
        profile.direction = self.cleaned_data["direction"]
        profile.course = self.cleaned_data["course"]
        profile.group_name = self.cleaned_data["group_name"]
        profile.education_form = self.cleaned_data["education_form"]
        profile.save()
        return profile


class OwnProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["phone", "email"]
        labels = {"email": "E-mail"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
