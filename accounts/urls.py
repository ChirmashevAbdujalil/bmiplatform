from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("chiqish/", auth_views.LogoutView.as_view(), name="logout"),
    path("parol/", views.password_change, name="password_change"),
    path("profil/", views.my_profile, name="my_profile"),
    path("profil/aloqa/", views.edit_contacts, name="edit_contacts"),

    path("oqituvchilar/", views.teacher_list, name="teacher_list"),
    path("oqituvchilar/yangi/", views.teacher_form, name="teacher_create"),
    path("oqituvchilar/import/", views.teacher_import, name="teacher_import"),
    path("oqituvchilar/<int:pk>/", views.teacher_detail, name="teacher_detail"),
    path("oqituvchilar/<int:pk>/tahrir/", views.teacher_form, name="teacher_edit"),
    path("oqituvchilar/<int:pk>/hisobot/", views.teacher_report, name="teacher_report"),

    path("talabalar/", views.student_list, name="student_list"),
    path("talabalar/yangi/", views.student_form, name="student_create"),
    path("talabalar/import/", views.student_import, name="student_import"),
    path("talabalar/<int:pk>/", views.student_detail, name="student_detail"),
    path("talabalar/<int:pk>/tahrir/", views.student_form, name="student_edit"),

    path("import/shablon/<str:kind>/", views.import_template, name="import_template"),
    path("import/parollar/", views.credentials_download, name="credentials_download"),
    path("foydalanuvchi/<int:pk>/parol-tiklash/", views.reset_password, name="reset_password"),
]
