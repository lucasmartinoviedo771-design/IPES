# academia_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth "clásico" de Django, con nuestros templates
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="ui/auth/login.html"
    ), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),

    # UI
    path("", include("ui.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
