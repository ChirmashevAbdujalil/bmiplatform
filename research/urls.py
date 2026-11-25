from django.urls import path

from . import views

app_name = "research"

urlpatterns = [
    path("", views.work_list, name="list"),
    path("yangi/", views.work_form, name="create"),
    path("mezonlar/", views.criteria_list, name="criteria"),
    path("mezonlar/<int:pk>/", views.criteria_list, name="criterion_edit"),
    path("<int:pk>/", views.work_detail, name="detail"),
    path("<int:pk>/tahrir/", views.work_form, name="edit"),
    path("<int:pk>/ochirish/", views.work_delete, name="delete"),
    path("<int:pk>/baholash/", views.work_evaluate, name="evaluate"),
    path("<int:pk>/fayl/", views.work_file, name="file"),
]
