# academia_core/views_auth.py
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

def _redirect_por_rol(user) -> str:
    """
    Devuelve la URL de destino por rol de usuario cuando NO hay ?next=.
    - ESTUDIANTE -> búsqueda de cartón (no panel)
    - BEDEL / SECRETARIA -> panel con acción operativa por defecto
    - DOCENTE / admin / otros -> panel
    """
    rol = getattr(getattr(user, "perfil", None), "rol", None)

    if rol == "ESTUDIANTE":
        return str(reverse_lazy("buscar_carton_primaria"))

    if rol in {"BEDEL", "SECRETARIA"}:
        return f"{reverse_lazy('panel_home')}?action=cargar_mov"

    return str(reverse_lazy("panel_home"))


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
