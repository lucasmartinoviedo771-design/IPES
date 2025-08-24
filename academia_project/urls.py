# academia_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from academia_core.views_auth import RoleAwareRememberLoginView, root_redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    # 1) Override del login (antes del include de auth)
    path("accounts/login/", RoleAwareRememberLoginView.as_view(), name="login"),
    # 2) Resto de URLs de auth (logout, password reset, etc.)
    path("accounts/", include("django.contrib.auth.urls")),
    # 3) Raíz -> requiere login y luego redirige por rol
    path("", root_redirect, name="root"),
    # 4) Rutas de tu app
    path("", include("academia_core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
