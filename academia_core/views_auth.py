from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

def _redirect_por_rol(user) -> str:
    """
    Redirección post-login sin ?next= según tu handoff:
    - Estudiante -> /panel/estudiante/
    - Admin/Secretaría -> /panel/
    """
    # Admin/Secretaría por staff/superuser o por grupo explícito
    if user.is_staff or user.is_superuser or user.groups.filter(name__in=["SECRETARIA","ADMIN"]).exists():
        return str(reverse_lazy("panel"))
    # Resto (alumno/docente) → Panel estudiante
    return str(reverse_lazy("panel_estudiante"))


class RoleAwareLoginView(LoginView):
    """
    Login con:
      - expiración de sesión en 3 horas,
      - respeto de ?next= si viene en la request,
      - redirección automática según rol si no hay ?next=.
    """
    # Usa tu template actual (el que pegaste): templates/login.html
    template_name = "login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        # Autentica y crea la sesión
        response = super().form_valid(form)
        # ⏲️ expira a las 3 horas de inactividad
        self.request.session.set_expiry(10800)  # 3 * 60 * 60
        return response

    def get_success_url(self):
        # 1) si hay ?next=, priorizarlo
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        # 2) si no, redirigir por rol
        return _redirect_por_rol(self.request.user)