# academia_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ui.auth_views import RoleAwareLoginView  # 👈

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", RoleAwareLoginView.as_view(), name="login"),  # 👈
    path("accounts/logout/", __import__("django.contrib.auth.views", fromlist=["LogoutView"]).LogoutView.as_view(), name="logout"),
    path("", include("ui.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
