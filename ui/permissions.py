# ui/permissions.py
from functools import wraps
from django.core.exceptions import PermissionDenied
from .auth_views import resolve_role

def roles_allowed(*allowed):
    def deco(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied
            role = request.session.get("active_role") or resolve_role(request.user)
            if role not in allowed:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped
    return deco
