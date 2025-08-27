# ui/signals.py
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .auth_views import resolve_role

@receiver(user_logged_in)
def set_active_role(sender, user, request, **kwargs):
    role = resolve_role(user)
    request.session["active_role"] = role

@receiver(user_logged_out)
def clear_active_role(sender, user, request, **kwargs):
    if hasattr(request, "session"):
        request.session.pop("active_role", None)
