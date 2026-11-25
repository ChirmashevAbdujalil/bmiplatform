from django.urls import path

from theses.views import verify

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("statistika/", views.statistics, name="statistics"),
    path("bildirishnomalar/", views.notifications, name="notifications"),
    path("bildirishnomalar/<int:pk>/", views.notification_open, name="notification_open"),
    path("bildirishnomalar/oqildi/", views.notifications_read_all, name="notifications_read_all"),
    path("tuzilma/", views.structure, name="structure"),
    path("tuzilma/<str:kind>/<int:pk>/ochirish/", views.structure_delete, name="structure_delete"),
    path("hisoblar/", views.staff_accounts, name="staff"),
    path("hisoblar/<int:pk>/parol/", views.staff_reset, name="staff_reset"),
    path("hisoblar/<int:pk>/holat/", views.staff_toggle, name="staff_toggle"),
    path("jurnal/", views.audit_log, name="audit"),
    path("tekshirish/<uuid:code>/", verify, name="verify"),
]
