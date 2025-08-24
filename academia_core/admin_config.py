# academia_core/admin.py
from datetime import date

from django.contrib import admin
from django.forms import ModelForm, ValidationError
from django.utils.html import format_html
from django.db.models import Q

from .models import (
    Profesorado,
    PlanEstudios,
    Estudiante,
    EstudianteProfesorado,
    EspacioCurricular,
    Movimiento,
    InscripcionEspacio,
    Docente,
    DocenteEspacio,
    UserProfile,
    EstadoInscripcion,
    Correlatividad,
    Horario,
    Condicion,
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


# ===================== Espacios =====================


class EspacioAdmin(admin.ModelAdmin):
    list_display = (
        "plan_en_dos_lineas",
        "anio",
        "cuatrimestre",
        "nombre",
        "horas",
        "formato",
    )
    list_filter = (
        "plan__profesorado",
        "plan__resolucion",
        "anio",
        "cuatrimestre",
        "formato",
    )
    search_fields = ("nombre", "plan__resolucion", "plan__nombre")
    autocomplete_fields = ("plan",)
    ordering = (
        "plan__profesorado__nombre",
        "plan__resolucion",
        "anio",
        "cuatrimestre",
        "nombre",
    )
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        profs = _profesorados_permitidos(request)
        if not request.user.is_superuser and profs.exists():
            qs = qs.filter(plan__profesorado__in=profs)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        profs = _profesorados_permitidos(request)
        if db_field.name == "plan":
            if not request.user.is_superuser and profs.exists():
                kwargs["queryset"] = (
                    kwargs.get("queryset") or PlanEstudios.objects
                ).filter(profesorado__in=profs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def plan_en_dos_lineas(self, obj):
        if not obj.plan:
            return "-"
        linea1 = f"Res. {obj.plan.resolucion}"
        linea2 = obj.plan.nombre or ""
        return format_html(
            '{}<br><small style="color:#6b7280;">{}</small>', linea1, linea2
        )

    plan_en_dos_lineas.short_description = "Plan"
    plan_en_dos_lineas.admin_order_field = "plan__resolucion"


# ===================== Movimientos inline (en inscripción) =====================


class MovimientoInline(admin.TabularInline):
    model = Movimiento
    extra = 0
    fields = (
        "tipo",
        "fecha",
        "espacio",
        "condicion",
        "nota_num",
        "nota_texto",
        "folio",
        "libro",
        "disposicion_interna",
    )
    autocomplete_fields = ("espacio",)
    ordering = ("-fecha", "-id")
    show_change_link = True

    # Limitar los espacios al profesorado de la inscripción
    def get_formset(self, request, obj=None, **kwargs):
        request._insc_obj = obj  # usamos en formfield_for_foreignkey
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (
            db_field.name == "espacio"
            and hasattr(request, "_insc_obj")
            and request._insc_obj
        ):
            kwargs["queryset"] = EspacioCurricular.objects.filter(
                plan=request._insc_obj.plan
            ).order_by("anio", "cuatrimestre", "nombre")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ===================== Inscripciones (Estudiante ↔ Profesorado) =====================


class EPAdmin(admin.ModelAdmin):
    list_display = (
        "estudiante",
        "profesorado",
        "cohorte",
        "libreta",
        "curso_introductorio",
        "legajo_estado",
        "promedio_general",
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
        return (
            False
            if _solo_lectura(request)
            else super().has_change_permission(request, obj)
        )

    def has_delete_permission(self, request, obj=None):
        return (
            False
            if _solo_lectura(request)
            else super().has_delete_permission(request, obj)
        )

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


# --- Admin Models ---
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ["apellido", "nombre", "dni", "email"]
    search_fields = ["apellido", "nombre", "dni", "email"]


class ProfesoradoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "plan_vigente", "slug"]
    search_fields = ["nombre", "plan_vigente"]
    prepopulated_fields = {"slug": ["nombre"]}


class PlanEstudiosAdmin(admin.ModelAdmin):
    list_display = ["profesorado", "resolucion", "nombre", "vigente"]
    list_filter = ["vigente", "profesorado"]
    search_fields = ["profesorado__nombre", "resolucion", "nombre"]
    prepopulated_fields = {"resolucion_slug": ["resolucion"]}


class InscripcionEspacioAdmin(admin.ModelAdmin):
    list_display = [
        "inscripcion",
        "espacio",
        "anio_academico",
        "fecha_inscripcion",
        "estado",
    ]
    list_filter = ["anio_academico", "estado", "espacio__plan__profesorado"]
    search_fields = [
        "inscripcion__estudiante__apellido",
        "inscripcion__estudiante__dni",
        "espacio__nombre",
    ]
    raw_id_fields = ["inscripcion", "espacio"]


class MovimientoAdmin(admin.ModelAdmin):
    list_display = ["inscripcion", "espacio", "tipo", "fecha", "condicion", "nota_num"]
    list_filter = ["tipo", "condicion", "espacio__plan__profesorado"]
    search_fields = [
        "inscripcion__estudiante__apellido",
        "inscripcion__estudiante__dni",
        "espacio__nombre",
    ]
    raw_id_fields = ["inscripcion", "espacio", "condicion"]


class CondicionAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "tipo"]
    list_filter = ["tipo"]
    search_fields = ["codigo", "nombre"]


class DocenteAdmin(admin.ModelAdmin):
    list_display = ["apellido", "nombre", "dni", "email", "activo"]
    list_filter = ["activo"]
    search_fields = ["apellido", "nombre", "dni", "email"]


class DocenteEspacioAdmin(admin.ModelAdmin):
    list_display = ["docente", "espacio", "desde", "hasta"]
    list_filter = ["espacio__plan__profesorado"]
    search_fields = ["docente__apellido", "espacio__nombre"]
    raw_id_fields = ["docente", "espacio"]


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "rol", "estudiante", "docente"]
    list_filter = ["rol", "profesorados_permitidos"]
    search_fields = ["user__username", "estudiante__apellido", "docente__apellido"]
    raw_id_fields = ["user", "estudiante", "docente"]


class HorarioAdmin(admin.ModelAdmin):
    list_display = ["espacio", "dia_semana", "hora_inicio", "hora_fin", "docente"]
    list_filter = ["dia_semana", "espacio__plan__profesorado", "docente"]
    search_fields = ["espacio__nombre", "docente__apellido"]
    raw_id_fields = ["espacio", "docente"]


# Register your models here.
admin.site.register(Profesorado, ProfesoradoAdmin)
admin.site.register(PlanEstudios, PlanEstudiosAdmin)
admin.site.register(Estudiante, EstudianteAdmin)
admin.site.register(EspacioCurricular, EspacioAdmin)
admin.site.register(EstudianteProfesorado, EPAdmin)
admin.site.register(InscripcionEspacio, InscripcionEspacioAdmin)
admin.site.register(Movimiento, MovimientoAdmin)
admin.site.register(Condicion, CondicionAdmin)
admin.site.register(Docente, DocenteAdmin)
admin.site.register(DocenteEspacio, DocenteEspacioAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Correlatividad)
admin.site.register(Horario, HorarioAdmin)
