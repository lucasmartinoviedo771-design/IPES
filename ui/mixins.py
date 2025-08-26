from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from .context_processors import role_from_request  # lo usamos para centralizar

class RoleRequiredMixin(LoginRequiredMixin):
    """
    - Obliga a login (LoginRequiredMixin)
    - Si 'allowed_roles' está definido, valida el rol lógico (UI_ROLE)
    """
    allowed_roles: list[str] | None = None

    def dispatch(self, request, *args, **kwargs):
        role = role_from_request(request)  # "Admin", "Secretaría", "Docente", "Estudiante", "Invitado"
        if self.allowed_roles and role not in self.allowed_roles:
            return HttpResponseForbidden("No tenés permiso para ver esta pantalla.")
        return super().dispatch(request, *args, **kwargs)