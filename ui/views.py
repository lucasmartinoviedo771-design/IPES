# ui/views.py
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.utils.timezone import localdate

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
            return redirect("ui:estudiante_carton")
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
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, TemplateView

from .forms import (
    InscripcionCarreraForm,
    InscripcionMateriaForm,
    InscripcionFinalForm,
    CalificacionBorradorForm,
    NuevoEstudianteForm,
    NuevoDocenteForm,
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

def _safe(obj, attr, default="—"):
    try:
        val = getattr(obj, attr)
        if callable(val):
            val = val()
        return val if val not in (None, "") else default
    except Exception:
        return default

def _fmt_date(d):
    try:
        return d.strftime("%d/%m/%Y") if d else "—"
    except Exception:
        return "—"

class CartonEstudianteView(PermissionRequiredMixin, TemplateView):
    permission_required = "academia_core.view_any_student_record"
    template_name = "ui/estudiante/carton.html"

    def has_permission(self):
        # Si tiene el permiso (Bedel/Secretaría/Admin), ok
        if super().has_permission():
            return True
        # Si es el propio estudiante, también ok
        est = getattr(self, "_resolved_est", None) or self.resolve_estudiante()
        self._resolved_est = est
        if not self.request.user.is_authenticated or not est:
            return False

        UserProfile = m("academia_core", "Userprofile") or m("academia_core", "UserProfile")
        if not UserProfile:
            return False
        try:
            up = UserProfile.objects.select_related("estudiante").get(user=self.request.user)
            return bool(getattr(up, "estudiante_id", None) == getattr(est, "id", None))
        except UserProfile.DoesNotExist:
            return False
    """
    'Cartón' = trayectoria consolidada (Regular + Mesas Finales).
    Permisos: Bedel/Secretaría/Admin -> cualquier estudiante (via ?est=<id>)
              Estudiante -> el propio (si tiene perfil vinculado).
    """
    permission_required = "academia_core.view_any_student_record"
    template_name = "ui/estudiante/carton.html"

    def resolve_estudiante(self):
        Estudiante = m("academia_core", "Estudiante")
        UserProfile = m("academia_core", "Userprofile") or m("academia_core", "UserProfile")
        if not Estudiante:
            return None

        # 1) ?est=<id>
        est_id = self.request.GET.get("est")
        if est_id:
            return Estudiante.objects.filter(pk=est_id).first()

        # 2) ?dni=<dni>
        dni = self.request.GET.get("dni")
        if dni and hasattr(Estudiante, "_meta") and "dni" in [f.name for f in Estudiante._meta.fields]:
            est = Estudiante.objects.filter(dni=dni).first()
            if est:
                return est

        # 3) ?legajo=<legajo>
        legajo = self.request.GET.get("legajo")
        if legajo and hasattr(Estudiante, "_meta") and "legajo" in [f.name for f in Estudiante._meta.fields]:
            est = Estudiante.objects.filter(legajo=legajo).first()
            if est:
                return est

        # 4) Usuario Estudiante vinculado a su perfil
        if self.request.user.is_authenticated and UserProfile:
            try:
                up = UserProfile.objects.select_related("estudiante").get(user=self.request.user)
                return getattr(up, "estudiante", None)
            except UserProfile.DoesNotExist:
                return None

        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        est = self.resolve_estudiante()
        ctx["today"] = localdate()

        if not est:
            ctx["error"] = "No se pudo resolver el Estudiante. Pasá ?est=<ID> o vinculá el perfil."
            return ctx

        ctx["est"] = est

        # Modelos que intentamos usar
        InsEsp = m("academia_core", "Inscripcionespacio")
        InsFinal = m("academia_core", "Inscripcionfinal")
        Calif = m("academia_core", "Calificacion")
        Espacio = m("academia_core", "Espaciocurricular")

        # --- Regular (inscripciones a cursado / condición “Regular/Libre/Promo”, etc.)
        reg_rows = []
        if InsEsp:
            qs = (
                InsEsp.objects
                .select_related("espacio", "inscripcion__estudiante")  # traverse
                .filter(inscripcion__estudiante=est)                   # traverse
                .order_by("id")
            )
            for ins in qs:
                espacio = _safe(ins, "espacio")
                nombre = _safe(espacio, "nombre") if espacio != "—" else "—"
                # Campos tipo anio/cuatrimestre si existen; si no, vacíos
                anio = _safe(espacio, "anio", "")
                cuatri = _safe(espacio, "cuatrimestre", "")
                fecha = _fmt_date(_safe(ins, "fecha", None))
                condicion = _safe(ins, "estado", _safe(ins, "condicion", "—"))  # según tu modelo
                # si hay calificación (parcial/promoción) asociada
                nota = "—"
                if Calif:
                    try:
                        cal = Calif.objects.filter(inscripcion=ins).order_by("-id").first()
                        if cal:
                            nota = _safe(cal, "nota", "—")
                    except Exception:
                        pass

                reg_rows.append({
                    "anio": anio,
                    "cuatri": cuatri,
                    "espacio": nombre,
                    "fecha": fecha,
                    "condicion": condicion,
                    "nota": nota,
                })

        # --- Mesas Finales
        final_rows = []
        if InsFinal:
            qs = (
                InsFinal.objects
                .select_related("inscripcion_cursada__espacio", "inscripcion_cursada__inscripcion__estudiante")
                .filter(inscripcion_cursada__inscripcion__estudiante=est)
                .order_by("id")
            )
            for ins in qs:
                espacio = _safe(ins, "espacio")
                nombre = _safe(espacio, "nombre") if espacio != "—" else "—"
                anio = _safe(espacio, "anio", "")
                cuatri = _safe(espacio, "cuatrimestre", "")
                fecha = _fmt_date(_safe(ins, "fecha", None))
                condicion = _safe(ins, "condicion", _safe(ins, "estado", "—"))
                nota = _safe(ins, "nota", "—")

                # Folio/Libro si existen en el modelo de final o acta
                folio = _safe(ins, "folio", "—")
                libro = _safe(ins, "libro", "—")

                final_rows.append({
                    "anio": anio,
                    "cuatri": cuatri,
                    "espacio": nombre,
                    "fecha": fecha,
                    "condicion": condicion,
                    "nota": nota,
                    "folio": folio,
                    "libro": libro,
                })

        # Agrupación por año/cuatrimestre (sólo para separadores)
        def group(rows):
            out = {}
            for r in rows:
                key = (str(r.get("anio") or ""), str(r.get("cuatri") or ""))
                out.setdefault(key, []).append(r)
            return out

        ctx["regular_groups"] = group(reg_rows)   # dict[(anio,cuatri)] = [rows]
        ctx["final_groups"] = group(final_rows)

        # stats rápidos (por ahora simplificados)
        try:
            aprob = [r for r in final_rows if str(r["nota"]).strip() not in ("—", "Ausente", "A", "0")]
            ctx["stats"] = {"aprobadas": len(aprob), "cursando": len(reg_rows), "finales": len(final_rows)}
        except Exception:
            ctx["stats"] = {"aprobadas": 0, "cursando": len(reg_rows), "finales": len(final_rows)}

        return ctx

# ui/views.py  (solo el bloque nuevo)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import NuevoEstudianteForm, NuevoDocenteForm

# Si ya tenés RoleRequiredMixin y/o allowed(), seguimos usándolos:

class NuevoEstudianteView(LoginRequiredMixin, PermissionRequiredMixin, RoleRequiredMixin, CreateView):
    """Alta de estudiantes: Bedel, Secretaría, Admin."""
    permission_required = "academia_core.add_estudiante"
    allowed_roles = ["Bedel", "Secretaría", "Admin"]
    form_class = NuevoEstudianteForm
    template_name = "ui/personas/estudiante_form.html"
    # Redirigimos a la lista si la tenés, o quedamos en el alta:
    success_url = reverse_lazy("estudiante_nuevo")

    page_title = "Nuevo Estudiante"
    section = "personas"

    def form_valid(self, form):
        obj = form.save()
        messages.success(self.request, f"Estudiante creado: {obj}")
        # Podés cambiar a reverse_lazy("estudiantes") si ya existe esa vista/listado
        return super().form_valid(form)


class NuevoDocenteView(LoginRequiredMixin, PermissionRequiredMixin, RoleRequiredMixin, CreateView):
    """Alta de docentes: SOLO Secretaría y Admin."""
    permission_required = "academia_core.add_docente"
    allowed_roles = ["Secretaría", "Admin"]
    form_class = NuevoDocenteForm
    template_name = "ui/personas/docente_form.html"
    success_url = reverse_lazy("docente_nuevo")

    page_title = "Nuevo Docente"
    section = "personas"

    def form_valid(self, form):
        obj = form.save()
        messages.success(self.request, f"Docente creado: {obj}")
        return super().form_valid(form)