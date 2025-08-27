from django.core.exceptions import PermissionDenied
from .auth_views import resolve_role

class RolesAllowedMixin:
    allowed_roles = tuple()
    def dispatch(self, request, *args, **kwargs):
        role = request.session.get("active_role") or resolve_role(request.user)
        if role not in self.allowed_roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)