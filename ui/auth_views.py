from django.contrib.auth.views import LoginView
from django.urls import reverse
from ui.context_processors import role_from_request

class RoleAwareLoginView(LoginView):
    template_name = "ui/auth/login.html"

    def get_success_url(self):
        role = role_from_request(self.request)
        if role == "Estudiante":
            return reverse("ui:carton_estudiante")
        return reverse("ui:dashboard")