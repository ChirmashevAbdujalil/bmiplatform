from django.urls import path

from . import views

app_name = "theses"

urlpatterns = [
    path("", views.thesis_list, name="list"),
    path("biriktirish/", views.thesis_form, name="create"),
    path("import/", views.thesis_import, name="import"),
    path("ommaviy/", views.thesis_bulk, name="bulk"),
    path("eksport/", views.thesis_export, name="export"),
    path("<int:pk>/", views.thesis_detail, name="detail"),
    path("<int:pk>/tahrir/", views.thesis_form, name="edit"),
    path("<int:pk>/ochirish/", views.thesis_delete, name="delete"),
    path("<int:pk>/yuborish/", views.thesis_send, name="send"),
    path("<int:pk>/qaror/", views.thesis_decide, name="decide"),
    path("<int:pk>/hujjat/", views.thesis_document, name="document"),
]
