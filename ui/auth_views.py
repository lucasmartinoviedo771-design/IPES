from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.shortcuts import redirect

ROLE_PRIORITY = ["Admin", "Secretaría", "Bedel", "Docente", "Estudiante"]
ROLE_HOME = {
    "Admin": "ui:dashboard",
    "Secretaría": "ui:dashboard",
    "Bedel": "ui:dashboard",
    "Docente": "ui:dashboard",      # ajustá si tenés un panel específico
    ROLE_HOME = {
    "Admin": "ui:dashboard",
    "Secretaría": "ui:dashboard",
    "Bedel": "ui:dashboard",
    "Docente": "ui:dashboard",
    "Estudiante": "ui:dashboard",  # cámbialo cuando tengas la vista específica
}

class RoleAwareLoginView(LoginView):
    template_name = "ui/auth/login.html"

    def get_success_url(self):
        # 1) Si hay ?next=, respétalo
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to

        # 2) Si no hay next, redirige por rol
        user = self.request.user
        role = resolve_role(user)  # reutiliza tu función para evitar duplicar lógica
        self.request.session["active_role"] = role
        return reverse(ROLE_HOME.get(role, "ui:dashboard"))

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
    template_name = "ui/auth/login.html"

    def get_success_url(self):
        user = self.request.user

        # resolución robusta del rol (coincide con CP)
        if user.is_superuser:
            role = "Admin"
        else:
            names = set(user.groups.values_list("name", flat=True))
            if "Secretaría" in names:
                role = "Secretaría"
            elif "Bedel" in names:
                role = "Bedel"
            elif "Docente" in names:
                role = "Docente"
            elif "Estudiante" in names:
                role = "Estudiante"
            else:
                role = "Estudiante"

        self.request.session["active_role"] = role
        return reverse(ROLE_HOME.get(role, "ui:dashboard"))
