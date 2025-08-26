# ui/views.py
from django.shortcuts import redirect
from django.views.generic import TemplateView

from .mixins import RoleRequiredMixin
from .context_processors import role_from_request


class HomeView(RoleRequiredMixin, TemplateView):
    """
    Entrada principal: redirige según el rol.
    - Estudiante -> /mi/carton
    - Resto -> /dashboard
    """
    template_name = "ui/placeholder.html"  # no se usa, redirige
    allowed_roles = ["Secretaría", "Admin", "Docente", "Estudiante", "Bedel"]

    def dispatch(self, request, *args, **kwargs):
        role = role_from_request(request)
        if role == "Estudiante":
            return redirect("ui:carton_estudiante")
        return redirect("ui:dashboard")


class DashboardView(RoleRequiredMixin, TemplateView):
    """Dashboard general: NO lo ve Estudiante."""
    template_name = "ui/dashboard.html"
    allowed_roles = ["Secretaría", "Admin", "Docente", "Bedel"]


class PlaceholderView(RoleRequiredMixin, TemplateView):
    """
    Base para pantallas no implementadas aún.
    Renderiza ui/placeholder.html con el título en 'page_title'.
    """
    template_name = "ui/placeholder.html"
    page_title: str = ""
    allowed_roles = ["Secretaría", "Admin", "Docente", "Estudiante", "Bedel"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.page_title
        return ctx


# ========== MI TRAYECTORIA (Estudiante) ==========
class EstudianteHistoricoView(PlaceholderView):
    page_title = "Histórico de Movimientos"
    allowed_roles = ["Estudiante"]


class EstudianteCartonView(PlaceholderView):
    page_title = "Cartón / Trayectoria"
    allowed_roles = ["Estudiante"]


# ========== ACADÉMICO ==========
class InscribirCarreraView(PlaceholderView):
    page_title = "Inscribir a Carrera"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]  # 👈 agregado Bedel


class InscribirMateriaView(PlaceholderView):
    page_title = "Inscribir a Materias"
    allowed_roles = ["Secretaría", "Admin", "Bedel", "Estudiante"]  # 👈 agregado Bedel


class InscribirMesaFinalView(PlaceholderView):
    page_title = "Inscribir a Mesa de Final"
    allowed_roles = ["Secretaría", "Admin", "Bedel", "Estudiante"]  # 👈 agregado Bedel


class CargarNotasView(PlaceholderView):
    page_title = "Cargar Notas"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]  # 👈 Docente sale


class RegularidadesView(PlaceholderView):
    page_title = "Regularidades"
    allowed_roles = ["Secretaría", "Admin"]


class CorrelatividadesView(PlaceholderView):
    page_title = "Correlatividades"
    allowed_roles = ["Secretaría", "Admin"]


# ========== PLANIFICACIÓN ==========
class HorariosView(PlaceholderView):
    page_title = "Horarios"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]


class EspaciosView(PlaceholderView):
    page_title = "Espacios Curriculares"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]


class PlanesView(PlaceholderView):
    page_title = "Planes de Estudio"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]


# ========== PERSONAS ==========
class EstudiantesView(PlaceholderView):
    page_title = "Estudiantes"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]


class DocentesView(PlaceholderView):
    page_title = "Docentes"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]


class EstudianteNuevoView(PlaceholderView):
    page_title = "Nuevo Estudiante"
    allowed_roles = ["Secretaría", "Admin", "Bedel"]  # 👈 agregado Bedel


# ========== ADMINISTRACIÓN ==========
class PeriodosView(PlaceholderView):
    page_title = "Periodos y Fechas"
    allowed_roles = ["Secretaría", "Admin"]


class UsuariosPermisosView(PlaceholderView):
    page_title = "Usuarios y Permisos"
    allowed_roles = ["Admin"]


class ParametrosView(PlaceholderView):
    page_title = "Parámetros"
    allowed_roles = ["Admin"]


class AuditoriaView(PlaceholderView):
    page_title = "Auditoría"
    allowed_roles = ["Admin"]


# ========== AYUDA ==========
class AyudaView(PlaceholderView):
    page_title = "Documentación"
    allowed_roles = ["Secretaría", "Admin", "Docente", "Estudiante", "Bedel"]
