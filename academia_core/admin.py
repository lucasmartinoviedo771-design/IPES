# academia_core/admin.py
from datetime import date

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q

from .models import (
    Profesorado, PlanEstudios, Estudiante, EstudianteProfesorado,
    EspacioCurricular, Movimiento, InscripcionEspacio,
    Docente, DocenteEspacio, UserProfile, EstadoInscripcion,
)

# ===================== Helpers de rol/alcance =====================

def _rol(request):
    try:
        return request.user.perfil.rol
    except Exception:
        return None

def _profesorados_permitidos(request):
    """
    Devuelve queryset de Profesorado permitidos.
    - BEDEL / TUTOR: sus profesorados_permitidos
    - SECRETARIA / superuser: todos
    - Otros (DOCENTE/ESTUDIANTE/sin perfil): ninguno (no deberían usar admin)
    """
    user = getattr(request, "user", None)
    if not user:
        return Profesorado.objects.none()
    if getattr(user, "is_superuser", False):
        return Profesorado.objects.all()
    perfil = getattr(user, "perfil", None)
    if not perfil:
        return Profesorado.objects.none()
    if perfil.rol == "SECRETARIA":
        return Profesorado.objects.all()
    if perfil.rol in ("BEDEL", "TUTOR"):
        return perfil.profesorados_permitidos.all()
    # Para DOCENTE/ESTUDIANTE dejamos sin alcance en admin
    return Profesorado.objects.none()

def _solo_lectura(request):
    """
    En admin: TUTOR es solo-lectura.
    También DOCENTE/ESTUDIANTE si llegaran a entrar.
    """
    return _rol(request) in ("TUTOR", "DOCENTE", "ESTUDIANTE")


# ===================== Catálogos básicos =====================

@admin.register(Profesorado)
class ProfesoradoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "plan_vigente")
    search_fields = ("nombre",)
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(id__in=profs.values("id"))
        return qs


@admin.register(PlanEstudios)
class PlanEstudiosAdmin(admin.ModelAdmin):
    list_display = ("profesorado", "resolucion", "nombre", "vigente")
    list_filter = ("profesorado", "vigente")
    search_fields = ("resolucion", "nombre", "profesorado__nombre")
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(profesorado__in=profs)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "profesorado":
            profs = _profesorados_permitidos(request)
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = profs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ===================== Estudiantes =====================

@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = (
        "apellido", "nombre", "dni", "email", "telefono", "localidad", "activo",
        "materias_total", "materias_anio_actual", "materias_en_curso",
    )
    search_fields = ("apellido", "nombre", "dni", "email")
    list_filter = ("activo",)
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(inscripciones__profesorado__in=profs).distinct()

        # Anotaciones de conteo (no cambian el esquema)
        anio_actual = date.today().year
        qs = qs.annotate(
            _mat_total=Count("inscripciones__cursadas__espacio", distinct=True),
            _mat_anio=Count(
                "inscripciones__cursadas",
                filter=Q(inscripciones__cursadas__anio_academico=anio_actual),
                distinct=True,
            ),
            _mat_en_curso=Count(
                "inscripciones__cursadas",
                filter=Q(inscripciones__cursadas__estado="EN_CURSO"),
                distinct=True,
            ),
        )
        return qs

    # Columnas calculadas
    def materias_total(self, obj):
        return getattr(obj, "_mat_total", 0)
    materias_total.short_description = "Materias (total)"
    materias_total.admin_order_field = "_mat_total"

    def materias_anio_actual(self, obj):
        return getattr(obj, "_mat_anio", 0)
    materias_anio_actual.short_description = f"Materias ({date.today().year})"
    materias_anio_actual.admin_order_field = "_mat_anio"

    def materias_en_curso(self, obj):
        return getattr(obj, "_mat_en_curso", 0)
    materias_en_curso.short_description = "Materias (en curso)"
    materias_en_curso.admin_order_field = "_mat_en_curso"

    # Solo-lectura para TUTOR / DOCENTE / ESTUDIANTE
    def has_add_permission(self, request):
        return False if _solo_lectura(request) else super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_delete_permission(request, obj)


# ===================== Espacios =====================

@admin.register(EspacioCurricular)
class EspacioAdmin(admin.ModelAdmin):
    list_display = ("profesorado", "plan_en_dos_lineas", "anio", "cuatrimestre", "nombre", "horas", "formato")
    list_filter = ("profesorado", "plan__resolucion", "anio", "cuatrimestre", "formato")
    search_fields = ("nombre", "plan__resolucion", "plan__nombre")
    autocomplete_fields = ("profesorado", "plan")
    ordering = ("profesorado__nombre", "plan__resolucion", "anio", "cuatrimestre", "nombre")
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(profesorado__in=profs)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        profs = _profesorados_permitidos(request)
        if db_field.name == "profesorado":
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = profs
        if db_field.name == "plan":
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = (kwargs.get("queryset") or PlanEstudios.objects).filter(profesorado__in=profs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def plan_en_dos_lineas(self, obj):
        if not obj.plan:
            return "-"
        linea1 = f"Res. {obj.plan.resolucion}"
        linea2 = obj.plan.nombre or ""
        return format_html('{}<br><small style="color:#6b7280;">{}</small>', linea1, linea2)
    plan_en_dos_lineas.short_description = "Plan"
    plan_en_dos_lineas.admin_order_field = "plan__resolucion"


# ===================== Movimientos inline (en inscripción) =====================

class MovimientoInline(admin.TabularInline):
    model = Movimiento
    extra = 0
    fields = ("tipo", "fecha", "espacio", "condicion", "nota_num", "nota_texto", "folio", "libro", "disposicion_interna")
    autocomplete_fields = ("espacio",)
    ordering = ("-fecha", "-id")
    show_change_link = True

    # Limitar los espacios al profesorado de la inscripción
    def get_formset(self, request, obj=None, **kwargs):
        request._insc_obj = obj  # usamos en formfield_for_foreignkey
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "espacio" and hasattr(request, "_insc_obj") and request._insc_obj:
            kwargs["queryset"] = EspacioCurricular.objects.filter(
                profesorado=request._insc_obj.profesorado
            ).order_by("anio", "cuatrimestre", "nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ===================== Inscripciones (Estudiante ↔ Profesorado) =====================

@admin.register(EstudianteProfesorado)
class EPAdmin(admin.ModelAdmin):
    list_display = (
        "estudiante", "profesorado", "cohorte", "libreta",
        "curso_introductorio", "legajo_estado", "promedio_general",
    )
    list_filter = ("profesorado", "cohorte", "curso_introductorio", "legajo_estado")
    search_fields = ("estudiante__apellido", "estudiante__dni", "profesorado__nombre")
    readonly_fields = ("legajo_estado", "promedio_general")
    autocomplete_fields = ("estudiante", "profesorado")
    list_per_page = 25
    inlines = [MovimientoInline]
    actions = ["recalcular_promedios", "recalcular_legajo_estado"]
    list_select_related = ("estudiante", "profesorado")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(profesorado__in=profs)
        return qs

    # Limitar selección de profesorado a los permitidos (Bedel/Tutor)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "profesorado":
            profs = _profesorados_permitidos(request)
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = profs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Solo-lectura para TUTOR / DOCENTE / ESTUDIANTE
    def has_add_permission(self, request):
        return False if _solo_lectura(request) else super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        obj.legajo_estado = obj.calcular_legajo_estado()
        super().save_model(request, obj, form, change)

    def recalcular_promedios(self, request, queryset):
        n = 0
        for ins in queryset:
            ins.recalcular_promedio()
            n += 1
        self.message_user(request, f"Promedio recalculado para {n} inscripciones.")
    recalcular_promedios.short_description = "Recalcular promedio"

    def recalcular_legajo_estado(self, request, queryset):
        n = 0
        for ins in queryset:
            ins.legajo_estado = ins.calcular_legajo_estado()
            ins.save(update_fields=["legajo_estado"])
            n += 1
        self.message_user(request, f"Legajo recalculado para {n} inscripciones.")
    recalcular_legajo_estado.short_description = "Recalcular estado de legajo"


# ===================== Cursadas (Inscripción a espacios) =====================

@admin.action(description="Dar de baja cursadas seleccionadas (hoy)")
def accion_marcar_baja(modeladmin, request, queryset):
    updated = queryset.update(estado=EstadoInscripcion.BAJA, fecha_baja=date.today())
    modeladmin.message_user(request, f"{updated} cursadas marcadas como BAJA")

@admin.register(InscripcionEspacio)
class InscripcionEspacioAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "profesorado", "espacio", "anio_academico", "estado", "fecha")
    list_filter = ("anio_academico", "estado", "espacio__profesorado", "espacio__anio", "espacio__cuatrimestre")
    search_fields = ("inscripcion__estudiante__apellido", "inscripcion__estudiante__dni", "espacio__nombre")
    autocomplete_fields = ("inscripcion", "espacio")
    date_hierarchy = "fecha"
    ordering = ("-anio_academico", "-fecha", "-id")
    list_per_page = 50
    list_select_related = ("inscripcion__estudiante", "inscripcion__profesorado", "espacio")
    actions = ["accion_marcar_baja"]

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(
            "inscripcion__estudiante", "inscripcion__profesorado", "espacio"
        )
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(espacio__profesorado__in=profs)
        return qs

    # columnas helper
    def estudiante(self, obj):
        return obj.inscripcion.estudiante
    estudiante.admin_order_field = "inscripcion__estudiante__apellido"

    def profesorado(self, obj):
        return obj.inscripcion.profesorado
    profesorado.admin_order_field = "inscripcion__profesorado__nombre"

    # Solo-lectura para TUTOR / DOCENTE / ESTUDIANTE
    def has_add_permission(self, request):
        return False if _solo_lectura(request) else super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_delete_permission(request, obj)


# ===================== Movimientos =====================

@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo", "condicion", "nota_resumen", "fecha",
        "estudiante_apellido", "estudiante_dni",
        "profesorado", "espacio", "anio", "cuatrimestre",
        "folio", "libro",
    )
    list_filter = (
        "tipo", "condicion",
        "espacio__profesorado", "espacio__anio", "espacio__cuatrimestre",
        "fecha",
    )
    search_fields = (
        "inscripcion__estudiante__apellido",
        "inscripcion__estudiante__nombre",
        "inscripcion__estudiante__dni",
        "espacio__nombre",
    )
    date_hierarchy = "fecha"
    ordering = ("-fecha", "-id")
    autocomplete_fields = ("inscripcion", "espacio")
    list_per_page = 50
    list_select_related = ("inscripcion__estudiante", "inscripcion__profesorado", "espacio")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(espacio__profesorado__in=profs)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        profs = _profesorados_permitidos(request)
        if db_field.name == "espacio" and not request.user.is_superuser and profs.exists():
            kwargs["queryset"] = EspacioCurricular.objects.filter(profesorado__in=profs)
        if db_field.name == "inscripcion" and not request.user.is_superuser and profs.exists():
            kwargs["queryset"] = EstudianteProfesorado.objects.filter(profesorado__in=profs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Solo-lectura para TUTOR / DOCENTE / ESTUDIANTE
    def has_add_permission(self, request):
        return False if _solo_lectura(request) else super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False if _solo_lectura(request) else super().has_delete_permission(request, obj)

    # Columnas auxiliares
    def estudiante_apellido(self, obj):
        return f"{obj.inscripcion.estudiante.apellido}, {obj.inscripcion.estudiante.nombre}"
    estudiante_apellido.admin_order_field = "inscripcion__estudiante__apellido"
    estudiante_apellido.short_description = "Estudiante"

    def estudiante_dni(self, obj):
        return obj.inscripcion.estudiante.dni
    estudiante_dni.admin_order_field = "inscripcion__estudiante__dni"
    estudiante_dni.short_description = "DNI"

    def profesorado(self, obj):
        return obj.inscripcion.profesorado
    profesorado.admin_order_field = "inscripcion__profesorado__nombre"

    def anio(self, obj):
        return obj.espacio.anio
    anio.admin_order_field = "espacio__anio"

    def cuatrimestre(self, obj):
        return obj.espacio.cuatrimestre
    cuatrimestre.admin_order_field = "espacio__cuatrimestre"

    def nota_resumen(self, obj):
        if obj.nota_num is not None:
            return obj.nota_num
        return obj.nota_texto or ""
    nota_resumen.short_description = "Nota"


# ===================== Docentes / Asignaciones / Perfil =====================

class DocenteEspacioInline(admin.TabularInline):
    model = DocenteEspacio
    extra = 1
    autocomplete_fields = ("espacio",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # limitar espacios por profesorados permitidos
        if db_field.name == "espacio":
            profs = _profesorados_permitidos(request)
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = EspacioCurricular.objects.filter(profesorado__in=profs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display = ("apellido", "nombre", "dni", "email", "activo")
    search_fields = ("apellido", "nombre", "dni", "email")
    list_filter = ("activo",)
    inlines = [DocenteEspacioInline]
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            # Docentes que tengan asignaciones en profesorados permitidos
            qs = qs.filter(docenteespacio__espacio__profesorado__in=profs).distinct()
        return qs


@admin.register(DocenteEspacio)
class DocenteEspacioAdmin(admin.ModelAdmin):
    list_display = ("docente", "espacio", "desde", "hasta")
    search_fields = ("docente__apellido", "docente__nombre", "docente__dni", "espacio__nombre")
    autocomplete_fields = ("docente", "espacio")
    list_filter = ("espacio__profesorado", "espacio__plan", "espacio__anio", "espacio__cuatrimestre")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(espacio__profesorado__in=profs)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "espacio":
            profs = _profesorados_permitidos(request)
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = EspacioCurricular.objects.filter(profesorado__in=profs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "rol", "estudiante", "docente")
    list_filter = ("rol",)
    search_fields = ("user__username", "user__email", "estudiante__dni", "docente__dni")
    filter_horizontal = ("profesorados_permitidos",)

    # Sólo SECRETARIA o superuser pueden modificar perfiles desde el admin
    def has_add_permission(self, request):
        if getattr(request.user, "is_superuser", False):
            return True
        return _rol(request) == "SECRETARIA"

    def has_change_permission(self, request, obj=None):
        if getattr(request.user, "is_superuser", False):
            return True
        return _rol(request) == "SECRETARIA"

    def has_delete_permission(self, request, obj=None):
        if getattr(request.user, "is_superuser", False):
            return True
        return _rol(request) == "SECRETARIA"


# --- Correlatividades ---
from .models import Correlatividad  # (lo dejamos separado para respetar tu organización)

@admin.register(Correlatividad)
class CorrelatividadAdmin(admin.ModelAdmin):
    list_display = ("plan", "espacio", "tipo", "requisito", "detalle")
    list_filter = ("plan", "tipo", "requisito", "espacio__anio", "espacio__cuatrimestre")
    search_fields = ("espacio__nombre", "plan__resolucion")
    autocomplete_fields = ("plan", "espacio", "requiere_espacio")

    def detalle(self, obj):
        if obj.requiere_espacio:
            return obj.requiere_espacio.nombre
        return f"Todos hasta {obj.requiere_todos_hasta_anio}°"
