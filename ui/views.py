# ui/views.py
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    CreateView,
    FormView,
    TemplateView,
    ListView,
    DetailView,
)
from django.shortcuts import redirect
from django.db.models import Q
from django.views import View
from django.http import HttpResponseForbidden

# Modelos del core
from academia_core.models import Estudiante, Docente, EstudianteProfesorado

# Formularios de la app UI
# NOTA: asegúrate de que estos nombres existan tal cual en ui/forms.py
from .forms import (
    EstudianteNuevoForm,
    InscripcionProfesoradoForm,
    NuevoDocenteForm,
    CERT_DOCENTE_LABEL,
)

# Mixin de permisos por rol
from .mixins import RolesAllowedMixin
from .auth_views import ROLE_HOME # Importar ROLE_HOME


# ---------- Dashboard ----------
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "ui/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        # Redirección suave si el rol es Estudiante
        role = request.session.get("active_role") # Usar el rol de la sesión
        if role and role.lower().startswith("estudiante"):
            try:
                return redirect(reverse("ui:carton_estudiante"))
            except Exception:
                pass
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, "userprofile", None)
        ctx["current_role"] = getattr(profile, "rol", "") or ""
        ctx["current_user"] = self.request.user
        return ctx


# ---------- Estudiantes: listado / detalle ----------
class EstudianteListView(LoginRequiredMixin, ListView):
    """
    Listado de estudiantes con buscador simple.
    """
    model = Estudiante
    template_name = "ui/personas/estudiantes_list.html"
    context_object_name = "items"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("apellido", "nombre")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(apellido__icontains=q)
                | Q(nombre__icontains=q)
                | Q(dni__icontains=q)
                | Q(email__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class EstudianteDetailView(LoginRequiredMixin, DetailView):
    """
    Ficha básica (solo lectura) del estudiante.
    """
    model = Estudiante
    template_name = "ui/personas/estudiantes_detail.html"
    context_object_name = "obj"


# ---------- Estudiantes: alta ----------
class NuevoEstudianteView(LoginRequiredMixin, RolesAllowedMixin, CreateView):
    """
    Alta de estudiantes — autorizado para Bedel / Secretaría / Admin.
    """
    permission_required = "academia_core.add_estudiante"
    allowed_roles = ["Bedel", "Secretaría", "Admin"]

    form_class = EstudianteNuevoForm
    template_name = "ui/personas/estudiante_form.html"

    # Dejamos el mismo flujo: al guardar, volver a la misma vista para cargar varios
    success_url = reverse_lazy("ui:estudiante_nuevo")


# ---------- Docentes: listado (por si lo necesitás) ----------
class DocenteListView(LoginRequiredMixin, ListView):
    model = Docente
    template_name = "ui/personas/docentes_list.html"
    context_object_name = "items"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().order_by("apellido", "nombre")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(apellido__icontains=q)
                | Q(nombre__icontains=q)
                | Q(dni__icontains=q)
                | Q(email__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


# ---------- Docentes: alta ----------
class NuevoDocenteView(LoginRequiredMixin, RolesAllowedMixin, CreateView):
    """
    Alta de docentes — SOLO Secretaría y Admin.
    """
    permission_required = "academia_core.add_docente"
    allowed_roles = ["Secretaría", "Admin"]

    form_class = NuevoDocenteForm
    template_name = "ui/personas/docente_form.html"

    success_url = reverse_lazy("ui:docente_nuevo")


# ---------- Inscripciones ----------
class InscribirCarreraView(LoginRequiredMixin, RolesAllowedMixin, TemplateView):
    """
    Pantalla de Inscripción a Carrera (placeholder).
    Restringida a Secretaría / Admin / Bedel.
    """
    allowed_roles = ["Secretaría", "Admin", "Bedel"]
    permission_required = "academia_core.add_estudianteprofesorado"
    template_name = "ui/inscripciones/carrera.html"
    extra_context = {"page_title": "Inscribir a Carrera"}


class InscribirMateriaView(LoginRequiredMixin, RolesAllowedMixin, TemplateView):
    """
    Pantalla de Inscripción a Materias/Comisiones (placeholder).
    Restringida a Secretaría / Admin / Bedel (inscripción de terceros).
    """
    allowed_roles = ["Secretaría", "Admin", "Bedel"]
    permission_required = "academia_core.enroll_others"
    template_name = "ui/inscripciones/materia.html"
    extra_context = {"page_title": "Inscribir a Materia"}


class InscribirFinalView(LoginRequiredMixin, RolesAllowedMixin, TemplateView):
    """
    Pantalla de Inscripción a Mesas de Final (inscribir terceros).
    Habilitada para Secretaría / Admin / Bedel.
    """
    allowed_roles = ["Secretaría", "Admin", "Bedel"]
    permission_required = "academia_core.enroll_others"
    template_name = "ui/inscripciones/final.html"
    extra_context = {"page_title": "Inscribir a Mesa de Final"}


class InscripcionProfesoradoView(LoginRequiredMixin, RolesAllowedMixin, CreateView):
    permission_required = "academia_core.add_estudianteprofesorado"
    allowed_roles = ["Bedel", "Secretaría", "Admin"]

    template_name = "ui/inscripciones/inscripcion_profesorado_form.html"
    form_class = InscripcionProfesoradoForm
    success_url = reverse_lazy("ui:dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        est = self.request.GET.get("est")
        if est:
            kwargs["initial_estudiante"] = est
        return kwargs

    def form_valid(self, form):
        estado, _ = form.compute_estado_admin()
        # Si tu modelo tiene un campo 'condicion_admin', podés setearlo:
        obj = form.save(commit=False)
        if hasattr(obj, "condicion_admin"):
            obj.condicion_admin = estado
        obj.save()
        form.save_m2m() # por si acaso

        # Placeholder: guardar y seguir
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx.get("form")
        estado = None
        is_cert = False
        if form and form.is_bound and form.is_valid():
            estado, is_cert = form.compute_estado_admin()
        ctx["estado_admin"] = estado  # "REGULAR" / "CONDICIONAL" / None
        ctx["is_cert_docente"] = is_cert
        ctx["CERT_DOCENTE_LABEL"] = CERT_DOCENTE_LABEL
        return ctx


# --- Cartón e Histórico del Estudiante ---
class CartonEstudianteView(LoginRequiredMixin, RolesAllowedMixin, TemplateView):
    template_name = "ui/estudiante/carton.html"
    allowed_roles = ["Estudiante", "Bedel", "Secretaría", "Admin"]


class HistoricoEstudianteView(LoginRequiredMixin, RolesAllowedMixin, TemplateView):
    template_name = "ui/estudiante/historico.html"
    allowed_roles = ["Estudiante", "Bedel", "Secretaría", "Admin"]


# --- Opcional: Vista para cambiar de rol --- 
class SwitchRoleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        new_role = request.POST.get("role")
        allowed = set(request.user.groups.values_list("name", flat=True))
        if request.user.is_superuser:
            allowed.add("Admin")
        if new_role not in allowed:
            return HttpResponseForbidden("No tenés ese rol.")
        request.session["active_role"] = new_role
        return redirect(reverse(ROLE_HOME.get(new_role, "ui:dashboard")))
