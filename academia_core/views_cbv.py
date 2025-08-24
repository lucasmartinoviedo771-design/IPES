from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from academia_core.auth_mixins import StaffOrGroupsRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import (
    Estudiante,
    Docente,
    Profesorado,
    Actividad,
    EspacioCurricular,  # ← Materias
    # === para Calificaciones (Movimiento) y alcances ===
    Movimiento,
    EstudianteProfesorado,
    DocenteEspacio,
)
from .forms_espacios import EspacioForm  # ← Form para Materias/Espacios

# ---------------- helpers de contexto para usar panel.html ----------------


def _rol(user):
    perfil = getattr(user, "perfil", None)
    return getattr(perfil, "rol", None)


def _can_admin(user):
    return getattr(user, "is_superuser", False) or user.has_perms(
        (
            "academia_core.add_profesorado",
            "academia_core.change_planestudios",
            "academia_core.add_espaciocurricular",
        )
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
        ctx.update(
            {
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
            }
        )
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


class EstudianteListView(
    LoginRequiredMixin, PanelContextMixin, SearchQueryMixin, ListView
):
    model = Estudiante
    template_name = "panel.html"
    context_object_name = "alumnos"
    paginate_by = 25
    panel_action = "alumnos_list"
    panel_title = "Listado de Alumnos"
    search_fields = ("apellido", "nombre", "dni", "email")

    def get_queryset(self):
        return self.apply_search(super().get_queryset().order_by("apellido", "nombre"))


class EstudianteCreateView(
    StaffOrGroupsRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView
):
    allowed_groups = ("SECRETARIA", "ADMIN")
    model = Estudiante
    fields = [
        "dni",
        "apellido",
        "nombre",
        "fecha_nacimiento",
        "lugar_nacimiento",
        "email",
        "telefono",
        "localidad",
        "activo",
        "foto",
    ]
    template_name = "academia_core/alumno_form.html"  # ← Asegurate de esta línea
    success_url = reverse_lazy("listado_alumnos")
    success_message = "Estudiante «%(apellido)s, %(nombre)s» creado."


class EstudianteUpdateView(
    StaffOrGroupsRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView
):
    allowed_groups = ("SECRETARIA", "ADMIN")
    model = Estudiante
    fields = [
        "dni",
        "apellido",
        "nombre",
        "fecha_nacimiento",
        "lugar_nacimiento",
        "email",
        "telefono",
        "localidad",
        "activo",
        "foto",
    ]
    template_name = "panel.html"
    success_url = reverse_lazy("listado_alumnos")
    success_message = "Estudiante «%(apellido)s, %(nombre)s» actualizado."
    panel_action = "add_est"
    panel_title = "Editar estudiante"
    panel_subtitle = "Actualizá los datos y guardá"


class EstudianteDeleteView(StaffOrGroupsRequiredMixin, DeleteView):
    allowed_groups = ("SECRETARIA", "ADMIN")
    model = Estudiante
    template_name = "confirmar_eliminacion.html"
    success_url = reverse_lazy("listado_alumnos")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        obj = ctx.get("object") or self.get_object()
        rotulo = f"{getattr(obj,'apellido','')}, {getattr(obj,'nombre','')}"
        if getattr(obj, "dni", None):
            rotulo += f" (DNI {obj.dni})"
        ctx.update(
            {
                "titulo": "Eliminar estudiante",
                "rotulo": rotulo,
                "cancel_url": reverse_lazy("listado_alumnos"),
            }
        )
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
                messages.success(
                    request, f"«{nombre}» tenía datos vinculados: se marcó inactivo."
                )
                return super().get(request, *a, **kw)
            messages.error(
                request, f"No se pudo eliminar «{nombre}» por registros relacionados."
            )
            return super().get(request, *a, **kw)


# ================================ DOCENTES ================================


class DocenteListView(
    LoginRequiredMixin, PanelContextMixin, SearchQueryMixin, ListView
):
    """Reemplaza listado_docentes."""

    model = Docente
    template_name = "panel.html"  # Podés cambiar a un template dedicado si querés tabla
    context_object_name = "docentes"
    paginate_by = 25
    panel_action = "doc_list"
    panel_title = "Listado de Docentes"
    panel_subtitle = "Búsqueda por nombre, apellido, DNI o email"
    search_fields = ("apellido", "nombre", "dni", "email")

    def get_queryset(self):
        return self.apply_search(super().get_queryset().order_by("apellido", "nombre"))


class DocenteCreateView(
    StaffOrGroupsRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView
):
    allowed_groups = ("SECRETARIA", "ADMIN")
    model = Docente
    fields = "__all__"  # si tenés DocenteForm: form_class = DocenteForm
    template_name = "panel.html"
    success_url = reverse_lazy("listado_docentes")
    success_message = "Docente «%(apellido)s, %(nombre)s» creado."
    panel_action = "doc_add"
    panel_title = "Alta de docente"
    panel_subtitle = "Completá los datos y guardá"


class DocenteUpdateView(
    StaffOrGroupsRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView
):
    allowed_groups = ("SECRETARIA", "ADMIN")
    model = Docente
    fields = "__all__"
    template_name = "panel.html"
    success_url = reverse_lazy("listado_docentes")
    success_message = "Docente «%(apellido)s, %(nombre)s» actualizado."
    panel_action = "doc_edit"
    panel_title = "Editar docente"
    panel_subtitle = "Actualizá los datos y guardá"


class DocenteDeleteView(StaffOrGroupsRequiredMixin, DeleteView):
    allowed_groups = ("SECRETARIA", "ADMIN")
    model = Docente
    template_name = "confirmar_eliminacion.html"
    success_url = reverse_lazy("listado_docentes")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        obj = ctx.get("object") or self.get_object()
        rotulo = f"{getattr(obj,'apellido','')}, {getattr(obj,'nombre','')}".strip(", ")
        ctx.update(
            {
                "titulo": "Eliminar docente",
                "rotulo": rotulo or str(obj),
                "cancel_url": reverse_lazy("listado_docentes"),
            }
        )
        return ctx

    def delete(self, request, *a, **kw):
        self.object = self.get_object()
        nombre = f"{getattr(self.object,'apellido','')}, {getattr(self.object,'nombre','')}".strip(
            ", "
        )
        try:
            messages.success(request, f"Docente «{nombre}» eliminado.")
            return super().delete(request, *a, **kw)
        except ProtectedError:
            if hasattr(self.object, "activo"):
                self.object.activo = False
                self.object.save(update_fields=["activo"])
                messages.success(
                    request, f"«{nombre}» tenía datos vinculados: se marcó inactivo."
                )
                return super().get(request, *a, **kw)
            messages.error(
                request, f"No se pudo eliminar «{nombre}» por registros relacionados."
            )
            return super().get(request, *a, **kw)


# ================================ MATERIAS ================================


class MateriaListView(
    LoginRequiredMixin, PanelContextMixin, SearchQueryMixin, ListView
):
    """Listado de Materias (Espacios curriculares)."""

    model = EspacioCurricular
    template_name = "materias_list.html"  # Template con tabla
    context_object_name = "materias"
    paginate_by = 25
    panel_action = "mat_list"
    panel_title = "Materias / Espacios"
    panel_subtitle = "Listado y búsqueda"
    search_fields = ("nombre", "plan__resolucion", "profesorado__nombre", "anio")

    def get_queryset(self):
        qs = super().get_queryset().select_related("plan", "profesorado")
        return self.apply_search(qs).order_by(
            "profesorado__nombre", "plan__resolucion", "anio", "cuatrimestre", "nombre"
        )


class MateriaCreateView(
    StaffOrGroupsRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView
):
    """Alta de Materia (Espacio curricular)."""

    allowed_groups = ("SECRETARIA", "ADMIN")
    model = EspacioCurricular
    form_class = EspacioForm
    template_name = "panel.html"  # Reutilizamos panel.html para el form
    success_url = reverse_lazy("listado_materias")
    success_message = "Materia «%(nombre)s» creada."
    panel_action = "mat_add"
    panel_title = "Nueva materia"
    panel_subtitle = "Completá los datos y guardá"


class MateriaUpdateView(
    StaffOrGroupsRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView
):
    """Edición de Materia."""

    allowed_groups = ("SECRETARIA", "ADMIN")
    model = EspacioCurricular
    form_class = EspacioForm
    template_name = "panel.html"
    success_url = reverse_lazy("listado_materias")
    success_message = "Materia «%(nombre)s» actualizada."
    panel_action = "mat_edit"
    panel_title = "Editar materia"
    panel_subtitle = "Actualizá los datos y guardá"


class MateriaDeleteView(StaffOrGroupsRequiredMixin, DeleteView):
    """Eliminación/archivado de Materia (soft-delete si está protegida)."""

    allowed_groups = ("SECRETARIA", "ADMIN")
    model = EspacioCurricular
    template_name = "confirmar_eliminacion.html"
    success_url = reverse_lazy("listado_materias")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        obj = ctx.get("object") or self.get_object()
        rot = f"{getattr(obj,'nombre','')} · {getattr(obj,'profesorado','')} – {getattr(obj,'plan','')}"
        ctx.update(
            {
                "titulo": "Eliminar materia",
                "rotulo": rot,
                "cancel_url": reverse_lazy("listado_materias"),
            }
        )
        return ctx

    def delete(self, request, *a, **kw):
        self.object = self.get_object()
        nombre = getattr(self.object, "nombre", "Materia")
        try:
            messages.success(request, f"Materia «{nombre}» eliminada.")
            return super().delete(request, *a, **kw)
        except ProtectedError:
            if hasattr(self.object, "activo"):
                self.object.activo = False
                self.object.save(update_fields=["activo"])
                messages.success(
                    request,
                    f"«{nombre}» tiene datos vinculados: se marcó como inactiva.",
                )
                return super().get(request, *a, **kw)
            messages.error(
                request, f"No se pudo eliminar «{nombre}» por registros relacionados."
            )
            return super().get(request, *a, **kw)
