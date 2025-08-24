# academia_core/views_auth.py
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy


def _redirect_por_rol(user) -> str:
    """
    Redirección post-login:
      - Staff/Superuser o grupos SECRETARIA/ADMIN -> /panel/
      - Resto (estudiante/docente) -> /panel/estudiante/
    """
    if (
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name__in=["SECRETARIA", "ADMIN"]).exists()
    ):
        return str(reverse_lazy("panel"))
    return str(reverse_lazy("panel_estudiante"))


class RememberAuthenticationForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        label="Recordarme",
        help_text="Mantener la sesión abierta en este navegador.",
    )


class RoleAwareRememberLoginView(LoginView):
    """
    - Respeta ?next=
    - Si no hay ?next=, redirige según rol
    - “Recordarme”: controla el vencimiento de la sesión
      * Marcado  -> expira por inactividad según SESSION_COOKIE_AGE (2h en settings)
      * Desmarcado -> expira al cerrar el navegador
    """

    template_name = "registration/login.html"  # Ajustá si tu template está en otro path
    redirect_authenticated_user = True
    authentication_form = RememberAuthenticationForm

    def form_valid(self, form):
        # Autentica y crea la sesión
        response = super().form_valid(form)

        if form.cleaned_data.get("remember_me"):
            # 2 horas de INACTIVIDAD (sliding window con SESSION_SAVE_EVERY_REQUEST=True)
            self.request.session.set_expiry(
                getattr(settings, "SESSION_COOKIE_AGE", 7200)
            )
        else:
            # Expira al cerrar el navegador
            self.request.session.set_expiry(0)

        return response

    def get_success_url(self):
        # 1) Prioriza ?next=
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        # 2) Si no hay, redirige por rol
        return _redirect_por_rol(self.request.user)


@login_required
def root_redirect(request):
    """
    Raíz protegida:
      - Si NO está logueado -> Django redirige a LOGIN_URL con ?next=/
      - Si está logueado -> redirige por rol (panel / panel_estudiante)
    """
    return redirect(_redirect_por_rol(request.user))
