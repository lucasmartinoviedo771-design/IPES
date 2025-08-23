# academia_core/urls.py
from django.urls import path

# Vistas de "cartones" existentes
from .views import (
    carton_primaria_por_dni, carton_primaria_pdf, buscar_carton_primaria,
    carton_por_prof_y_plan, carton_generico_pdf,
)

# Panel y APIs (ajustado a views_panel.py actualizado)
from .views_panel import (
    # Paneles
    panel,
    panel_correlatividades,
    panel_horarios,
    panel_docente,
    # APIs (AJAX)
    get_espacios_por_inscripcion,
    get_correlatividades,
    # Guardados (POST)
    crear_inscripcion_cursada,
    crear_movimiento,
    # Redirecciones utilitarias
    redir_estudiante,
    redir_inscripcion,
)

# CBVs ya existentes
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
    
)

urlpatterns = [
    # ---------------- Cartones ----------------
    path("carton/primaria/", buscar_carton_primaria, name="buscar_carton_primaria"),
    path("carton/primaria/<str:dni>/", carton_primaria_por_dni, name="carton_primaria"),
    path("carton/primaria/<str:dni>/pdf/", carton_primaria_pdf, name="carton_primaria_pdf"),
    path("carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/", carton_por_prof_y_plan, name="carton_generico"),
    path("carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/pdf/", carton_generico_pdf, name="carton_generico_pdf"),

    # ---------------- Panel -------------------
    path("panel/", panel, name="panel"),
    path("panel/home/", panel, name="panel_home"),

    # Panel de Estudiante (cartón por inscripción)
    # Nota: el view espera <int:insc_id>
    path("panel/estudiante/<int:insc_id>/", panel, name="estudiante_panel"),
    path("panel/correlatividades/", panel_correlatividades, name="panel_correlatividades"),
    path("panel/horarios/", panel_horarios, name="panel_horarios"),
    path("panel/docente/", panel_docente, name="panel_docente"),

    # ---------------- CBVs (Alumnos) ----------
    path("alumnos/", EstudianteListView.as_view(), name="listado_alumnos"),
    path("alumnos/agregar/", EstudianteCreateView.as_view(), name="agregar_alumno"),
    path("alumnos/modificar/<int:pk>/", EstudianteUpdateView.as_view(), name="modificar_alumno"),
    path("alumnos/eliminar/<int:pk>/", EstudianteDeleteView.as_view(), name="eliminar_alumno"),

    # ---------------- CBVs (Docentes) ---------
    path("docentes/", DocenteListView.as_view(), name="listado_docentes"),
    path("docentes/agregar/", DocenteCreateView.as_view(), name="agregar_docente"),
    path("docentes/modificar/<int:pk>/", DocenteUpdateView.as_view(), name="modificar_docente"),
    path("docentes/eliminar/<int:pk>/", DocenteDeleteView.as_view(), name="eliminar_docente"),

    # ---------------- CBVs (Materias) ---------
    path("materias/", MateriaListView.as_view(), name="listado_materias"),
    path("materias/agregar/", MateriaCreateView.as_view(), name="agregar_materia"),
    path("materias/modificar/<int:pk>/", MateriaUpdateView.as_view(), name="modificar_materia"),
    path("materias/eliminar/<int:pk>/", MateriaDeleteView.as_view(), name="eliminar_materia"),

    # ---------------- APIs para el panel (AJAX) ----
    path("api/espacios-por-inscripcion/<int:insc_id>/",
         get_espacios_por_inscripcion,
         name="api_espacios_por_inscripcion"),

    # Dos rutas para correlatividades:
    # - Solo espacio (sin inscripción -> devuelve requisitos)
    path("api/correlatividades/<int:espacio_id>/",
         get_correlatividades,
         name="api_correlatividades"),
    # - Espacio + inscripción (evalúa si puede cursar)
    path("api/correlatividades/<int:espacio_id>/<int:insc_id>/",
         get_correlatividades,
         name="api_correlatividades_con_insc"),

    # ---------------- Guardados (POST) --------------
    path("panel/inscripciones/<int:insc_prof_id>/cursadas/crear/",
         crear_inscripcion_cursada,
         name="crear_inscripcion_cursada"),
    path("panel/cursadas/<int:insc_cursada_id>/movimientos/crear/",
         crear_movimiento,
         name="crear_movimiento"),

    # ---------------- Redirecciones utilitarias -----
    path("redir/estudiante/<int:est_id>/", redir_estudiante, name="redir_estudiante"),
    path("redir/inscripcion/<int:insc_id>/", redir_inscripcion, name="redir_inscripcion"),
]
