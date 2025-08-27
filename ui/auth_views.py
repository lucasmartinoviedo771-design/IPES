# ui/auth_views.py
from django.contrib.auth.views import LoginView
from django.urls import reverse

def resolve_role(user) -> str:
    """
    Devuelve el rol principal del usuario según superusuario y grupos.
    Posibles valores: 'Admin', 'Secretaría', 'Bedel', 'Docente', 'Estudiante'.
    """
    if not getattr(user, "is_authenticated", False):
        return "Estudiante"

    if user.is_superuser:
        return "Admin"

    names = set(user.groups.values_list("name", flat=True))
    if "Secretaría" in names:
        return "Secretaría"
    if "Bedel" in names:
        return "Bedel"
    if "Docente" in names:
        return "Docente"
    if "Estudiante" in names:
        return "Estudiante"

    return "Estudiante"


# A dónde redirigir luego de login según el rol
ROLE_HOME = {
    "Admin": "ui:dashboard",
    "Secretaría": "ui:dashboard",
    "Bedel": "ui:dashboard",
    "Docente": "ui:dashboard",
    # Cambia si más adelante tienes una vista específica para estudiantes:
    "Estudiante": "ui:dashboard",
}


class RoleAwareLoginView(LoginView):
    template_name = "ui/auth/login.html"

    def get_success_url(self):
        # 1) Respetar ?next= si viene de una página protegida
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to

        # 2) Determinar rol y guardarlo en sesión
        role = resolve_role(self.request.user)
        if hasattr(self.request, "session"):
            self.request.session["active_role"] = role

        # 3) Redirigir según rol
        return reverse(ROLE_HOME.get(role, "ui:dashboard"))