from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.shortcuts import redirect

ROLE_PRIORITY = ["Admin", "Secretaría", "Bedel", "Docente", "Estudiante"]
ROLE_HOME = {
    "Admin": "ui:dashboard",
    "Secretaría": "ui:dashboard",
    "Bedel": "ui:dashboard",
    "Docente": "ui:dashboard",      # ajustá si tenés un panel específico
    "Estudiante": "ui:carton_estudiante",
}

def resolve_role(user):
    """Devuelve el rol prioritario del usuario."""
    if user.is_superuser:
        return "Admin"
    names = set(user.groups.values_list("name", flat=True))
    for r in ROLE_PRIORITY:
        if r in names:
            return r
    # fallback sensato
    return "Estudiante"

class RoleAwareLoginView(LoginView):
    """
    Login que, al autenticar, fija el rol activo por prioridad y redirige
    a la home correspondiente.
    """
    def get_success_url(self):
        role = resolve_role(self.request.user)
        self.request.session["active_role"] = role
        return reverse(ROLE_HOME.get(role, "ui:dashboard"))
