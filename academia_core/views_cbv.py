from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
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
    EspacioCurricular,   # ← Materias
    # === para Calificaciones (Movimiento) y alcances ===
    Movimiento,
    EstudianteProfesorado,
    DocenteEspacio,
)
from .forms_espacios import EspacioForm   # ← Form para Materias/Espacios

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
    template_name = "alumno_form.html"
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
    template_name = "panel.html"  # Podés cambiar a un template dedicado si querés tabla
    context_object_name = "docentes"
    paginate_by = 25
    permission_required = "academia_core.view_docente"
    raise_exception = True
    panel_action = "doc_list"
    panel_title = "Listado de Docentes"
    panel_subtitle = "Búsqueda por nombre, apellido, DNI o email"
    search_fields = ("apellido", "nombre", "dni", "email")

    def get_queryset(self):
        return self.apply_search(super().get_queryset().order_by("apellido", "nombre"))


class DocenteCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView):
    model = Docente
    fields = "__all__"                 # si tenés DocenteForm: form_class = DocenteForm
    template_name = "panel.html"
    success_url = reverse_lazy("listado_docentes")
    success_message = "Docente «%(apellido)s, %(nombre)s» creado."
    permission_required = "academia_core.add_docente"
    raise_exception = True
    panel_action = "doc_add"
    panel_title = "Alta de docente"
    panel_subtitle = "Completá los datos y guardá"


class DocenteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView):
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
    model = Docente
    template_name = "confirmar_eliminacion.html"
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


# ================================ MATERIAS ================================

class MateriaListView(LoginRequiredMixin, PermissionRequiredMixin, PanelContextMixin, SearchQueryMixin, ListView):
    """Listado de Materias (Espacios curriculares)."""
    model = EspacioCurricular
    template_name = "materias_list.html"     # Template con tabla
    context_object_name = "materias"
    paginate_by = 25
    permission_required = "academia_core.view_espaciocurricular"
    raise_exception = True
    panel_action = "mat_list"
    panel_title = "Materias / Espacios"
    panel_subtitle = "Listado y búsqueda"
    search_fields = ("nombre", "plan__resolucion", "profesorado__nombre", "anio")

    def get_queryset(self):
        qs = super().get_queryset().select_related("plan", "profesorado")
        return self.apply_search(qs).order_by("profesorado__nombre", "plan__resolucion", "anio", "cuatrimestre", "nombre")


class MateriaCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, CreateView):
    """Alta de Materia (Espacio curricular)."""
    model = EspacioCurricular
    form_class = EspacioForm
    template_name = "panel.html"             # Reutilizamos panel.html para el form
    success_url = reverse_lazy("listado_materias")
    success_message = "Materia «%(nombre)s» creada."
    permission_required = "academia_core.add_espaciocurricular"
    raise_exception = True
    panel_action = "mat_add"
    panel_title = "Nueva materia"
    panel_subtitle = "Completá los datos y guardá"


class MateriaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, PanelContextMixin, UpdateView):
    """Edición de Materia."""
    model = EspacioCurricular
    form_class = EspacioForm
    template_name = "panel.html"
    success_url = reverse_lazy("listado_materias")
    success_message = "Materia «%(nombre)s» actualizada."
    permission_required = "academia_core.change_espaciocurricular"
    raise_exception = True
    panel_action = "mat_edit"
    panel_title = "Editar materia"
    panel_subtitle = "Actualizá los datos y guardá"


class MateriaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Eliminación/archivado de Materia (soft-delete si está protegida)."""
    model = EspacioCurricular
    template_name = "confirmar_eliminacion.html"
    success_url = reverse_lazy("listado_materias")
    permission_required = "academia_core.delete_espaciocurricular"
    raise_exception = True

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        obj = ctx.get("object") or self.get_object()
        rot = f"{getattr(obj,'nombre','')} · {getattr(obj,'profesorado','')} – {getattr(obj,'plan','')}"
        ctx.update({"titulo": "Eliminar materia", "rotulo": rot, "cancel_url": reverse_lazy("listado_materias")})
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
                messages.success(request, f"«{nombre}» tiene datos vinculados: se marcó como inactiva.")
                return super().get(request, *a, **kw)
            messages.error(request, f"No se pudo eliminar «{nombre}» por registros relacionados.")
            return super().get(request, *a, **kw)


# ===================== CALIFICACIONES (Movimiento) =======================

class RoleAccessMixin(LoginRequiredMixin):
    """
    Limita qué ve/edita cada rol:
      - superuser / SECRETARIA: todo
      - BEDEL / TUTOR: solo profesorados permitidos
      - DOCENTE: solo espacios asignados al docente
      - ESTUDIANTE: solo sus propias calificaciones
    """
    def user_role(self):
        return getattr(getattr(self.request.user, "perfil", None), "rol", None)

    def perfil(self):
        return getattr(self.request.user, "perfil", None)

    # ¿puede crear/editar/eliminar?
    def can_edit(self) -> bool:
        r = self.user_role()
        return bool(
            getattr(self.request.user, "is_superuser", False)
            or getattr(self.request.user, "is_staff", False)
            or r in {"SECRETARIA", "BEDEL"}
        )

    # Alcance de profesorados según rol
    def allowed_profesorados_qs(self):
        user = self.request.user
        r = self.user_role()
        if getattr(user, "is_superuser", False) or r == "SECRETARIA":
            return Profesorado.objects.all()
        perf = self.perfil()
        if r in {"BEDEL", "TUTOR"} and perf:
            return perf.profesorados_permitidos.all()
        if r == "DOCENTE" and perf and perf.docente_id:
            return Profesorado.objects.filter(
                espacios__asignaciones_docentes__docente=perf.docente
            ).distinct()
        if r == "ESTUDIANTE" and perf and perf.estudiante_id:
            return Profesorado.objects.filter(
                inscripciones__estudiante=perf.estudiante
            ).distinct()
        return Profesorado.objects.none()

    # Alcance de espacios según rol
    def allowed_espacios_qs(self):
        r = self.user_role()
        perf = self.perfil()
        if getattr(self.request.user, "is_superuser", False) or r == "SECRETARIA":
            return EspacioCurricular.objects.all()
        if r in {"BEDEL", "TUTOR"}:
            return EspacioCurricular.objects.filter(
                profesorado__in=self.allowed_profesorados_qs()
            )
        if r == "DOCENTE" and perf and perf.docente_id:
            return EspacioCurricular.objects.filter(
                asignaciones_docentes__docente=perf.docente
            ).distinct()
        if r == "ESTUDIANTE" and perf and perf.estudiante_id:
            return EspacioCurricular.objects.filter(
                cursadas__inscripcion__estudiante=perf.estudiante
            ).distinct()
        return EspacioCurricular.objects.none()

    # Alcance de inscripciones Estudiante↔Profesorado
    def allowed_inscripciones_qs(self):
        r = self.user_role()
        perf = self.perfil()
        if getattr(self.request.user, "is_superuser", False) or r == "SECRETARIA":
            return EstudianteProfesorado.objects.select_related("estudiante", "profesorado")
        if r in {"BEDEL", "TUTOR"}:
            return EstudianteProfesorado.objects.filter(
                profesorado__in=self.allowed_profesorados_qs()
            ).select_related("estudiante", "profesorado")
        if r == "DOCENTE" and perf and perf.docente_id:
            profs = self.allowed_profesorados_qs()
            return EstudianteProfesorado.objects.filter(
                profesorado__in=profs
            ).select_related("estudiante", "profesorado")
        if r == "ESTUDIANTE" and perf and perf.estudiante_id:
            return EstudianteProfesorado.objects.filter(
                estudiante=perf.estudiante
            ).select_related("estudiante", "profesorado")
        return EstudianteProfesorado.objects.none()

    # chequeo de acceso a un objeto Movimiento puntual
    def has_object_access(self, obj: Movimiento) -> bool:
        r = self.user_role()
        if getattr(self.request.user, "is_superuser", False) or r == "SECRETARIA":
            return True
        if r in {"BEDEL", "TUTOR"}:
            return self.allowed_profesorados_qs().filter(
                id=obj.inscripcion.profesorado_id
            ).exists()
        if r == "DOCENTE" and self.perfil() and self.perfil().docente_id:
            return self.allowed_espacios_qs().filter(id=obj.espacio_id).exists()
        if r == "ESTUDIANTE" and self.perfil() and self.perfil().estudiante_id:
            return obj.inscripcion.estudiante_id == self.perfil().estudiante_id
        return False


class RoleFilteredFormMixin(RoleAccessMixin):
    """
    Filtra los querysets de los campos del formulario según el rol.
    Aplica a Create/Update.
    """
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrar 'inscripcion'
        if "inscripcion" in form.fields:
            form.fields["inscripcion"].queryset = self.allowed_inscripciones_qs()
        # Filtrar 'espacio'
        if "espacio" in form.fields:
            form.fields["espacio"].queryset = self.allowed_espacios_qs().order_by("anio", "cuatrimestre", "nombre")
        # Si no puede editar, bloquear
        if not self.can_edit():
            for f in form.fields.values():
                f.disabled = True
        return form


# Intentamos usar tu form existente para validar negocio;
# si no está, usamos un ModelForm fallback.
try:
    from .forms_carga import CargarMovimientoForm as MovimientoForm
except Exception:
    from django import forms
    class MovimientoForm(forms.ModelForm):
        class Meta:
            model = Movimiento
            fields = [
                "inscripcion", "espacio", "tipo", "fecha",
                "condicion", "nota_num", "nota_texto",
                "folio", "libro", "disposicion_interna",
            ]


class CalificacionListView(RoleAccessMixin, ListView):
    """Listado con búsqueda y filtros, acotado al alcance del usuario."""
    model = Movimiento
    template_name = "calificaciones_list.html"
    context_object_name = "movimientos"
    paginate_by = 25
    ordering = ["-fecha", "-id"]

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "inscripcion__estudiante", "inscripcion__profesorado", "espacio"
        )
        r = self.user_role()
        # Alcance por rol
        if r in {"BEDEL", "TUTOR"}:
            qs = qs.filter(espacio__profesorado__in=self.allowed_profesorados_qs())
        elif r == "DOCENTE":
            qs = qs.filter(espacio__in=self.allowed_espacios_qs())
        elif r == "ESTUDIANTE" and self.perfil() and self.perfil().estudiante_id:
            qs = qs.filter(inscripcion__estudiante=self.perfil().estudiante)

        # Búsqueda y filtros
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(inscripcion__estudiante__apellido__icontains=q) |
                Q(inscripcion__estudiante__nombre__icontains=q) |
                Q(inscripcion__estudiante__dni__icontains=q) |
                Q(espacio__nombre__icontains=q)
            )
        tipo = self.request.GET.get("tipo")
        if tipo in {"REG", "FIN"}:
            qs = qs.filter(tipo=tipo)
        condicion = self.request.GET.get("condicion")
        if condicion:
            qs = qs.filter(condicion=condicion)
        anio = self.request.GET.get("anio")
        if anio and anio.isdigit():
            qs = qs.filter(fecha__year=int(anio))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Calificaciones"
        ctx["subtitulo"] = "Movimientos REG/FIN con búsqueda y filtros."
        ctx["q"] = self.request.GET.get("q", "")
        ctx["tipo_sel"] = self.request.GET.get("tipo", "")
        ctx["cond_sel"] = self.request.GET.get("condicion", "")
        ctx["anio_sel"] = self.request.GET.get("anio", "")
        ctx["can_edit"] = self.can_edit()
        return ctx


class CalificacionCreateView(RoleFilteredFormMixin, CreateView):
    model = Movimiento
    form_class = MovimientoForm
    template_name = "calificacion_form.html"
    success_url = reverse_lazy("listado_calificaciones")

    def dispatch(self, request, *args, **kwargs):
        if not self.can_edit():
            raise PermissionDenied("No tenés permisos para crear calificaciones.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Nueva calificación"
        ctx["subtitulo"] = "Cargá una Regularidad o un Final (validaciones automáticas)."
        ctx["can_edit"] = True
        return ctx


class CalificacionUpdateView(RoleFilteredFormMixin, UpdateView):
    model = Movimiento
    form_class = MovimientoForm
    template_name = "calificacion_form.html"
    success_url = reverse_lazy("listado_calificaciones")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not self.can_edit() or not self.has_object_access(obj):
            raise PermissionDenied("No tenés permisos para editar esta calificación.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Editar calificación"
        ctx["subtitulo"] = "Actualizá un movimiento existente."
        ctx["can_edit"] = True
        return ctx


class CalificacionDeleteView(RoleAccessMixin, DeleteView):
    model = Movimiento
    template_name = "confirmar_eliminacion.html"
    success_url = reverse_lazy("listado_calificaciones")

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not self.can_edit() or not self.has_object_access(obj):
            raise PermissionDenied("No tenés permisos para eliminar esta calificación.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titulo"] = "Eliminar calificación"
        ctx["subtitulo"] = "Esta acción es permanente."
        return ctx
