# academia_core/urls.py
from django.urls import path

from .views import (
    carton_primaria_por_dni, carton_primaria_pdf, buscar_carton_primaria,
    carton_por_prof_y_plan, carton_generico_pdf,
)

from .views_panel import (
    # Paneles
    panel,
    panel_estudiante,
    panel_estudiante_carton,
    # APIs (AJAX)
    get_espacios_por_inscripcion,
    get_condiciones_por_espacio,
    get_correlatividades,
    get_situacion_academica,
)

from .views_cbv import (
    # Estudiantes
    EstudianteListView, EstudianteCreateView,
    EstudianteUpdateView, EstudianteDeleteView,
    # Docentes
    DocenteListView, DocenteCreateView,
    DocenteUpdateView, DocenteDeleteView,
    # Materias
    MateriaListView, MateriaCreateView,
    MateriaUpdateView, MateriaDeleteView,
    # Calificaciones
    CalificacionListView, CalificacionCreateView,
    CalificacionUpdateView, CalificacionDeleteView,
)

urlpatterns = [
    # Cartones
    path("carton/primaria/", buscar_carton_primaria, name="buscar_carton_primaria"),
    path("carton/primaria/<str:dni>/", carton_primaria_por_dni, name="carton_primaria"),
    path("carton/primaria/<str:dni>/pdf/", carton_primaria_pdf, name="carton_primaria_pdf"),
    path("carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/", carton_por_prof_y_plan, name="carton_generico"),
    path("carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/pdf/", carton_generico_pdf, name="carton_generico_pdf"),

    # Panel unificado
    path("panel/", panel, name="panel"),
    path("panel/home/", panel, name="panel_home"),

    # Panel de Estudiante
    path("panel/estudiante/", panel_estudiante, name="panel_estudiante"),
    path("panel/estudiante/carton/", panel_estudiante_carton, name="panel_estudiante_carton"),

    # ---- CBVs (Alumnos) ----
    path("alumnos/", EstudianteListView.as_view(), name="listado_alumnos"),
    path("alumnos/agregar/", EstudianteCreateView.as_view(), name="agregar_alumno"),
    path("alumnos/modificar/<int:pk>/", EstudianteUpdateView.as_view(), name="modificar_alumno"),
    path("alumnos/eliminar/<int:pk>/", EstudianteDeleteView.as_view(), name="eliminar_alumno"),

    # ---- CBVs (Docentes) ----
    path("docentes/", DocenteListView.as_view(), name="listado_docentes"),
    path("docentes/agregar/", DocenteCreateView.as_view(), name="agregar_docente"),
    path("docentes/modificar/<int:pk>/", DocenteUpdateView.as_view(), name="modificar_docente"),
    path("docentes/eliminar/<int:pk>/", DocenteDeleteView.as_view(), name="eliminar_docente"),

    # ---- CBVs (Materias) ----
    path("materias/", MateriaListView.as_view(), name="listado_materias"),
    path("materias/agregar/", MateriaCreateView.as_view(), name="agregar_materia"),
    path("materias/modificar/<int:pk>/", MateriaUpdateView.as_view(), name="modificar_materia"),
    path("materias/eliminar/<int:pk>/", MateriaDeleteView.as_view(), name="eliminar_materia"),

    # ---- APIs para el panel (AJAX) ----
    path("api/espacios-por-inscripcion/<int:insc_id>/", get_espacios_por_inscripcion, name="api_espacios_por_inscripcion"),
    path("api/condiciones-por-espacio/<int:espacio_id>/", get_condiciones_por_espacio, name="get_condiciones_por_espacio"),
    path("api/correlatividades/<int:espacio_id>/", get_correlatividades, name="api_correlatividades"),
    path("api/situacion-academica/<int:insc_id>/", get_situacion_academica, name="api_situacion_academica"),
]
