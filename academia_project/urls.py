# academia_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth: /accounts/login/ y /accounts/logout/
    path("accounts/", include("django.contrib.auth.urls")),

    # 1) Redirigir la raíz al panel (¡ponerlo ANTES del include!)
    path("", RedirectView.as_view(pattern_name="panel_home", permanent=False)),

    # 2) Resto de rutas de la app
    path("", include("academia_core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
