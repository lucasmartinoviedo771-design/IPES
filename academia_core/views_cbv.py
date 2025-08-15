from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import (
    Estudiante,
    Docente,          # ← modelo Docente
    Profesorado,
    Actividad,
)

# ---------------- helpers de contexto para usar panel.html ----------------
def _rol(user):
    perfil = getattr(user, "perfil", None)
    return getattr(perfil, "rol", None)

def _can_admin(user):
    return (
        getattr(user, "is_superuser", False)
        or user.has_perms((
            "academia_core.add_profesorado",
            "academia_core.change_planestudios",
            "academia_core.add_espaciocurricular",
        ))
    )

def _puede_editar(user) -> bool:
    if _can_admin(user):
        return True
    return _rol(user) in {"SECRETARIA", "BEDEL"}

def _profes_visibles(user):
    perfil = getattr(user, "perfil", None)
    if perfil and perfil.rol in {"BEDEL", "TUTOR"}:
        return perfil.profesorados_permitidos.all().order_by("nombre")
    return Profesorado.objects.all().order_by("nombre")

class PanelContextMixin:
    """Inyecta claves que espera panel.html para que quede integrado."""
    panel_action = ""
    panel_title = ""
    panel_subtitle = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        ctx.update({
            "rol": _rol(u),
            "puede_editar": _puede_editar(u),
            "puede_cargar": _puede_editar(u),
            "can_admin": _can_admin(u),
            "action": self.panel_action,
            "action_title": self.panel_title,
            "action_subtitle": self.panel_subtitle,
            "profesorados": _profes_visibles(u),
            "events": Actividad.objects.order_by("-creado")[:20],
            "logout_url": "/accounts/logout/",
            "login_url": "/accounts/login/",
        })
        ctx["busqueda"] = (self.request.GET.get("busqueda") or "").strip()
        return ctx

class SearchQueryMixin:
    search_param = "busqueda"
    search_fields = ()
    def apply_search(self, qs):
        term = (self.request.GET.get(self.search_param) or "").strip()
        if not term or not self.search_fields:
            return qs
        q = Q()
        for f in self.search_fields:
            q |= Q(**{f + "__icontains": term})
        return qs.filter(q)

# ============================== ESTUDIANTES ===============================

class EstudianteListView(LoginRequiredMixin, PermissionRequiredMixin, PanelContextMixin, SearchQueryMixin, ListView):
    model = Estudiante
    template_name = "panel.html"
    context_object_name = "alumnos"
    paginate_by = 25
    permission_required = "academia_core.view_estudiante"
    raise_exception = True
    panel_action = "alumnos_list"
    panel_title = "Listado de Alumnos"
    search_fields = ("apellido", "nombre", "dni", "email")

    def get_queryset(self):
        return self.apply_search(super().get_queryset().order_by("apellido", "nombre"))

class EstudianteCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView):
    model = Estudiante
    fields = ["dni","apellido","nombre","fecha_nacimiento","lugar_nacimiento","email","telefono","localidad","activo","foto"]
    template_name = "panel.html"
    success_url = reverse_lazy("listado_alumnos")
    success_message = "Estudiante «%(apellido)s, %(nombre)s» creado."
    permission_required = "academia_core.add_estudiante"
    raise_exception = True
    panel_action = "add_est"
    panel_title = "Alta de estudiante"
    panel_subtitle = "Carga rápida de datos básicos"

class EstudianteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView):
    model = Estudiante
    fields = ["dni","apellido","nombre","fecha_nacimiento","lugar_nacimiento","email","telefono","localidad","activo","foto"]
    template_name = "panel.html"
    success_url = reverse_lazy("listado_alumnos")
    success_message = "Estudiante «%(apellido)s, %(nombre)s» actualizado."
    permission_required = "academia_core.change_estudiante"
    raise_exception = True
    panel_action = "add_est"
    panel_title = "Editar estudiante"
    panel_subtitle = "Actualizá los datos y guardá"

class EstudianteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Estudiante
    template_name = "confirmar_eliminacion.html"
    success_url = reverse_lazy("listado_alumnos")
    permission_required = "academia_core.delete_estudiante"
    raise_exception = True

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        obj = ctx.get("object") or self.get_object()
        rotulo = f"{getattr(obj,'apellido','')}, {getattr(obj,'nombre','')}"
        if getattr(obj, "dni", None):
            rotulo += f" (DNI {obj.dni})"
        ctx.update({"titulo":"Eliminar estudiante","rotulo":rotulo,"cancel_url": reverse_lazy("listado_alumnos")})
        return ctx

    def delete(self, request, *a, **kw):
        self.object = self.get_object()
        nombre = f"{self.object.apellido}, {self.object.nombre}"
        try:
            messages.success(request, f"Estudiante «{nombre}» eliminado.")
            return super().delete(request, *a, **kw)
        except ProtectedError:
            if hasattr(self.object, "activo"):
                self.object.activo = False
                self.object.save(update_fields=["activo"])
                messages.success(request, f"«{nombre}» tenía datos vinculados: se marcó inactivo.")
                return super().get(request, *a, **kw)
            messages.error(request, f"No se pudo eliminar «{nombre}» por registros relacionados.")
            return super().get(request, *a, **kw)

# ================================ DOCENTES ================================

class DocenteListView(LoginRequiredMixin, PermissionRequiredMixin, PanelContextMixin, SearchQueryMixin, ListView):
    """Reemplaza listado_docentes."""
    model = Docente
    template_name = "panel.html"
    context_object_name = "docentes"
    paginate_by = 25
    permission_required = "academia_core.view_docente"
    raise_exception = True
    panel_action = "doc_list"
    panel_title = "Listado de Docentes"
    search_fields = ("apellido", "nombre", "dni", "email")

    def get_queryset(self):
        return self.apply_search(super().get_queryset().order_by("apellido", "nombre"))

class DocenteCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView):
    """Reemplaza agregar_docente."""
    model = Docente
    fields = "__all__"                 # usa tu DocenteForm si lo tenés: form_class = DocenteForm
    template_name = "panel.html"
    success_url = reverse_lazy("listado_docentes")
    success_message = "Docente «%(apellido)s, %(nombre)s» creado."
    permission_required = "academia_core.add_docente"
    raise_exception = True
    panel_action = "doc_add"
    panel_title = "Alta de docente"
    panel_subtitle = "Completá los datos y guardá"

class DocenteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView):
    """Reemplaza modificar_docente."""
    model = Docente
    fields = "__all__"
    template_name = "panel.html"
    success_url = reverse_lazy("listado_docentes")
    success_message = "Docente «%(apellido)s, %(nombre)s» actualizado."
    permission_required = "academia_core.change_docente"
    raise_exception = True
    panel_action = "doc_edit"
    panel_title = "Editar docente"
    panel_subtitle = "Actualizá los datos y guardá"

class DocenteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Reemplaza eliminar_docente."""
    model = Docente
    template_name = "confirmar_eliminacion.html"   # template unificado
    success_url = reverse_lazy("listado_docentes")
    permission_required = "academia_core.delete_docente"
    raise_exception = True

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        obj = ctx.get("object") or self.get_object()
        rotulo = f"{getattr(obj,'apellido','')}, {getattr(obj,'nombre','')}".strip(", ")
        ctx.update({"titulo":"Eliminar docente","rotulo": rotulo or str(obj), "cancel_url": reverse_lazy("listado_docentes")})
        return ctx

    def delete(self, request, *a, **kw):
        self.object = self.get_object()
        nombre = f"{getattr(self.object,'apellido','')}, {getattr(self.object,'nombre','')}".strip(", ")
        try:
            messages.success(request, f"Docente «{nombre}» eliminado.")
            return super().delete(request, *a, **kw)
        except ProtectedError:
            if hasattr(self.object, "activo"):
                self.object.activo = False
                self.object.save(update_fields=["activo"])
                messages.success(request, f"«{nombre}» tenía datos vinculados: se marcó inactivo.")
                return super().get(request, *a, **kw)
            messages.error(request, f"No se pudo eliminar «{nombre}» por registros relacionados.")
            return super().get(request, *a, **kw)
