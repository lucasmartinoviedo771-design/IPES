from django.urls import reverse


def auth_urls(request):
    def safe_reverse(name, default):
        try:
            return reverse(name)
        except Exception:
            return default

    return {
        "login_url": safe_reverse("login", "/accounts/login/"),
        "logout_url": safe_reverse("logout", "/accounts/logout/"),
    }
