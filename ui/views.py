from django.views.generic import TemplateView
from django.http import HttpResponseForbidden
from .context_processors import role_from_request
from .mixins import RoleRequiredMixin # New import


class DashboardView(RoleRequiredMixin, TemplateView):
    template_name = "ui/dashboard.html"
    allowed_roles = ["Secretaría", "Admin", "Docente", "Estudiante"]


class PlaceholderView(TemplateView):
    template_name = "ui/placeholder.html"
    page_title = "Módulo"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.page_title
        return ctx


# --- Vistas con restricción por rol (el mixin va PRIMERO en el MRO) ---
class InscribirCarreraView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin", "Estudiante"]
    page_title = "Inscribir a Carrera"


class InscribirMateriaView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin", "Estudiante"]
    page_title = "Inscribir a Materias"


class InscribirMesaFinalView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin", "Estudiante"]
    page_title = "Inscribir a Mesa de Final"


class CargarNotasView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Docente", "Secretaría", "Admin"]
    page_title = "Cargar Notas"


class RegularidadesView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Regularidades"


class CorrelatividadesView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Correlatividades"


class HorariosView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Horarios"


class EspaciosView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Espacios Curriculares"


class PlanesView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Planes de Estudio"


class EstudiantesView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Estudiantes"


class DocentesView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Secretaría", "Admin"]
    page_title = "Docentes"


class PeriodosView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Admin"]
    page_title = "Periodos y Fechas"


class UsuariosView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Admin"]
    page_title = "Usuarios y Permisos"


class ParametrosView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Admin"]
    page_title = "Parámetros"


class AuditoriaView(RoleRequiredMixin, PlaceholderView):
    allowed_roles = ["Admin"]
    page_title = "Auditoría"


class AyudaView(PlaceholderView):
    page_title = "Ayuda"