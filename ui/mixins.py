# ui/mixins.py
from django.core.exceptions import PermissionDenied
from .auth_views import resolve_role

class RolesAllowedMixin:
    allowed_roles = tuple()  # ("Admin", "Secretaría", "Bedel", "Docente", "Estudiante")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        role = request.session.get("active_role") or resolve_role(request.user)
        if self.allowed_roles and role not in self.allowed_roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
