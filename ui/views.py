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

# ui/views.py  (añadir al final del archivo)
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, TemplateView

from .forms import (
    EstudianteForm,
    InscripcionCarreraForm,
    InscripcionMateriaForm,
    InscripcionFinalForm,
    CalificacionBorradorForm,
)
from .context_processors import role_from_request
from .menu import demo  # para tarjetas del dashboard si lo necesitás

def m(app_label, model_name):
    """Obtiene un modelo o None sin romper la app."""
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

# ============ Personas ============

class EstudianteListView(PermissionRequiredMixin, ListView):
    permission_required = "academia_core.view_estudiante"
    model = m("academia_core", "Estudiante")
    template_name = "ui/estudiantes/list.html"
    context_object_name = "rows"
    paginate_by = 20

    def handle_no_permission(self):
        messages.error(self.request, "No tenés permiso para ver Estudiantes.")
        return redirect("/")

    def get_queryset(self):
        if not self.model:
            return []
        qs = self.model.objects.all().order_by("apellido", "nombre")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(apellido__icontains=q) | qs.filter(nombre__icontains=q) | qs.filter(dni__icontains=q)
        return qs

class EstudianteDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "academia_core.view_estudiante"
    model = m("academia_core", "Estudiante")
    template_name = "ui/estudiantes/detail.html"
    context_object_name = "obj"

class EstudianteCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "academia_core.add_estudiante"
    form_class = EstudianteForm
    template_name = "ui/generic_form.html"
    success_url = reverse_lazy("ui:estudiantes_list")

    def form_valid(self, form):
        messages.success(self.request, "Estudiante creado correctamente.")
        return super().form_valid(form)

# Docentes
class DocenteListView(PermissionRequiredMixin, ListView):
    permission_required = "academia_core.view_docente"
    model = m("academia_core", "Docente")
    template_name = "ui/docentes/list.html"
    context_object_name = "rows"
    paginate_by = 20

    def get_queryset(self):
        if not self.model:
            return []
        qs = self.model.objects.all().order_by("apellido", "nombre")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(apellido__icontains=q) | qs.filter(nombre__icontains=q)
        return qs

# ============ Inscripciones ============

class InscribirCarreraView(PermissionRequiredMixin, CreateView):
    """
    Secretaría/Admin/Bedel: pueden inscribir a carrera a terceros (según RBAC).
    """
    permission_required = ["academia_core.add_inscripcioncarrera", "academia_core.enroll_others"]
    form_class = InscripcionCarreraForm
    template_name = "ui/inscripciones/carrera_form.html"
    success_url = reverse_lazy("ui:dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Inscripción a Carrera generada.")
        return super().form_valid(form)

class InscribirMateriaView(PermissionRequiredMixin, CreateView):
    permission_required = ["academia_core.add_inscripcionespacio", "academia_core.enroll_others"]
    form_class = InscripcionMateriaForm
    template_name = "ui/inscripciones/materia_form.html"
    success_url = reverse_lazy("ui:dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Inscripción a Materia generada.")
        return super().form_valid(form)

class InscribirFinalView(PermissionRequiredMixin, CreateView):
    permission_required = ["academia_core.add_inscripcionfinal", "academia_core.enroll_others"]
    form_class = InscripcionFinalForm
    template_name = "ui/inscripciones/final_form.html"
    success_url = reverse_lazy("ui:dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Inscripción a Mesa de Final generada.")
        return super().form_valid(form)

# ============ Calificaciones (borrador) ============

class CargarNotasView(PermissionRequiredMixin, CreateView):
    """
    MVP: alta simple de calificaciones en estado 'BORRADOR'.
    Más adelante lo reemplazamos por grilla editable por comisión.
    """
    permission_required = "academia_core.add_calificacion"
    form_class = CalificacionBorradorForm
    template_name = "ui/calificaciones/cargar.html"
    success_url = reverse_lazy("ui:dashboard")

    def form_valid(self, form):
        try:
            estado_field = form.fields.get("estado")
            if estado_field and not form.cleaned_data.get("estado"):
                # si el modelo tiene campo estado, marcamos borrador por defecto
                form.instance.estado = "BORRADOR"
        except Exception:
            pass
        messages.success(self.request, "Calificación guardada en borrador.")
        return super().form_valid(form)

# ============ Estudiante - Histórico / Cartón ============

class HistoricoEstudianteView(PermissionRequiredMixin, TemplateView):
    """
    Cualquier Estudiante ve su histórico; Bedel/Secretaría/Admin pueden ver de terceros.
    (En la próxima iteración traemos la data real).
    """
    permission_required = "academia_core.view_any_student_record"
    template_name = "ui/estudiante/historico.html"

class CartonEstudianteView(PermissionRequiredMixin, TemplateView):
    """
    'Cartón' = trayectoria consolidada. De momento placeholder con estructura.
    """
    permission_required = "academia_core.view_any_student_record"
    template_name = "ui/estudiante/carton.html"