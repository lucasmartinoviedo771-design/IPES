# academia_core/admin.py
from datetime import date

from django.contrib import admin
from django.forms import ModelForm, ValidationError
from django.utils.html import format_html
from django.db.models import Count, Q

from .models import (
    Profesorado, PlanEstudios, Estudiante, EstudianteProfesorado,
    EspacioCurricular, Movimiento, InscripcionEspacio,
    Docente, DocenteEspacio, UserProfile, EstadoInscripcion,
    Correlatividad, Horario, Condicion,
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

class InscripcionEspacioAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "profesorado", "espacio", "anio_academico", "estado",
                    "fecha_inscripcion", "fecha_baja")  # <- antes 'fecha'
    list_filter = ("anio_academico", "estado", "espacio__profesorado",
                   "espacio__anio", "espacio__cuatrimestre",
                   "fecha_inscripcion", "fecha_baja")
    search_fields = ("inscripcion__estudiante__apellido",
                     "inscripcion__estudiante__dni", "espacio__nombre")
    autocomplete_fields = ("inscripcion", "espacio")
    date_hierarchy = "fecha_inscripcion"   # <- antes 'fecha'
    ordering = ("-anio_academico", "-fecha_inscripcion", "-id")  # <- antes 'fecha'
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



class CorrelatividadAdminForm(ModelForm):
    class Meta:
        model = Correlatividad
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        requiere_espacio = cleaned_data.get("requiere_espacio")
        requiere_todos_hasta_anio = cleaned_data.get("requiere_todos_hasta_anio")

        if requiere_espacio and requiere_todos_hasta_anio:
            raise ValidationError(
                "No puedes especificar un espacio requerido y 'todos hasta año' al mismo tiempo."
            )
        if not requiere_espacio and not requiere_todos_hasta_anio:
            raise ValidationError(
                "Debes especificar un espacio requerido o 'todos hasta año'."
            )
        return cleaned_data


# --- Inlines ---
class CorrelatividadInline(admin.TabularInline):
    model = Correlatividad
    form = CorrelatividadAdminForm  # Usamos nuestro formulario personalizado
    extra = 0
    fields = ["tipo", "requisito", "requiere_espacio", "requiere_todos_hasta_anio", "observaciones"]
    autocomplete_fields = ["requiere_espacio"]
    # Añadimos help_text para mayor claridad
    fieldsets = (
        (None, {
            'fields': (
                ("tipo", "requisito"),
                ("requiere_espacio", "requiere_todos_hasta_anio"),
                "observaciones",
            ),
            'description': (
                "Define la condición para cursar o rendir este espacio. "
                "Debes elegir un 'Espacio requerido' O 'Todos hasta año', pero no ambos."
            )
        }),
    )


class DocenteEspacioInline(admin.TabularInline):
    model = DocenteEspacio
    extra = 0
    autocomplete_fields = ["docente"]


class InscripcionEspacioInline(admin.TabularInline):
    model = InscripcionEspacio
    extra = 0
    fields = ["espacio", "anio_academico", "fecha_inscripcion", "estado", "fecha_baja", "motivo_baja"]
    readonly_fields = ["fecha_inscripcion"]
    autocomplete_fields = ["espacio"]





# --- Admin Models ---
class ProfesoradoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "plan_vigente", "slug"]
    search_fields = ["nombre", "plan_vigente"]
    prepopulated_fields = {"slug": ["nombre"]}


class PlanEstudiosAdmin(admin.ModelAdmin):
    list_display = ["profesorado", "resolucion", "nombre", "vigente"]
    list_filter = ["vigente", "profesorado"]
    search_fields = ["profesorado__nombre", "resolucion", "nombre"]
    prepopulated_fields = {"resolucion_slug": ["resolucion"]}


class EspacioCurricularAdmin(admin.ModelAdmin):
    list_display = ["nombre", "profesorado", "plan", "anio", "cuatrimestre", "horas"]
    list_filter = ["profesorado", "plan", "anio", "cuatrimestre"]
    search_fields = ["nombre", "profesorado__nombre", "plan__nombre"]
    inlines = [DocenteEspacioInline, CorrelatividadInline]


class EstudianteAdmin(admin.ModelAdmin):
    list_display = ["apellido", "nombre", "dni", "email", "activo"]
    list_filter = ["activo"]
    search_fields = ["apellido", "nombre", "dni", "email"]


class EstudianteProfesoradoAdmin(admin.ModelAdmin):
    list_display = ["estudiante", "profesorado", "cohorte", "legajo_estado", "condicion_admin", "promedio_general"]
    list_filter = ["profesorado", "cohorte", "legajo_estado", "condicion_admin"]
    search_fields = ["estudiante__apellido", "estudiante__nombre", "estudiante__dni", "profesorado__nombre"]
    inlines = [InscripcionEspacioInline]
    raw_id_fields = ["estudiante", "profesorado"]


class InscripcionEspacioAdmin(admin.ModelAdmin):
    list_display = ["inscripcion", "espacio", "anio_academico", "fecha_inscripcion", "estado"]
    list_filter = ["anio_academico", "estado", "espacio__profesorado"]
    search_fields = ["inscripcion__estudiante__apellido", "inscripcion__estudiante__dni", "espacio__nombre"]
    inlines = [MovimientoInline]
    raw_id_fields = ["inscripcion", "espacio"]


class MovimientoAdmin(admin.ModelAdmin):
    list_display = ["inscripcion", "espacio", "tipo", "fecha", "condicion", "nota_num"]
    list_filter = ["tipo", "condicion", "espacio__profesorado"]
    search_fields = ["inscripcion__estudiante__apellido", "inscripcion__estudiante__dni", "espacio__nombre"]
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
    list_filter = ["espacio__profesorado"]
    search_fields = ["docente__apellido", "espacio__nombre"]
    raw_id_fields = ["docente", "espacio"]


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "rol", "estudiante", "docente"]
    list_filter = ["rol", "profesorados_permitidos"]
    search_fields = ["user__username", "estudiante__apellido", "docente__apellido"]
    raw_id_fields = ["user", "estudiante", "docente"]


class HorarioAdmin(admin.ModelAdmin):
    list_display = ["espacio", "dia_semana", "hora_inicio", "hora_fin", "docente"]
    list_filter = ["dia_semana", "espacio__profesorado", "docente"]
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