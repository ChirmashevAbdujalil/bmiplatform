from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "BMI Platforma — boshqaruv"
admin.site.site_title = "BMI Platforma"
admin.site.index_title = "Ma’lumotlarni boshqarish"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("bmi/", include("theses.urls")),
    path("ilmiy-ishlar/", include("research.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
