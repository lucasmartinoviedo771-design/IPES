# academia_core/urls.py
from django.urls import path, include

from .views import (
    carton_primaria_por_dni,
    carton_primaria_pdf,
    buscar_carton_primaria,
    carton_por_prof_y_plan,
    carton_generico_pdf,
    home_router,
    alumno_home,
    docente_espacio_detalle,
)
from .views_panel import (
    panel,
    panel_correlatividades,
    panel_horarios,
    panel_docente,
    # Guardados (POST)
    crear_inscripcion_cursada,
    crear_movimiento,
    cargar_nota,
    # Redirecciones utilitarias
    redir_estudiante,
    redir_inscripcion,
    # NUEVO: Vista para el formulario de correlatividades
    correlatividades_form_view,
)

from .views_api import (
    api_listar_estudiantes,
    api_listar_docentes,
    api_listar_profesorados,
    api_listar_planes_estudios,
    api_get_estudiante_detalle,
    api_get_docente_detalle,
    api_get_espacio_curricular_detalle,
    api_get_movimientos_estudiante,
    api_espacios_habilitados,
    api_inscribir_espacio,
    api_get_correlatividades,
    api_get_planes_for_profesorado,
    api_get_espacios_for_plan,
    api_correlatividades_por_materia, # NEW IMPORT
)

# CBVs ya existentes
from .views_cbv import (
    # Estudiantes
    EstudianteListView,
    EstudianteCreateView,
    EstudianteUpdateView,
    EstudianteDeleteView,
    # Docentes
    DocenteListView,
    DocenteCreateView,
    DocenteUpdateView,
    DocenteDeleteView,
    # Materias
    MateriaListView,
    MateriaCreateView,
    MateriaUpdateView,
    MateriaDeleteView,
)

urlpatterns = [
    # ---------------- Vistas principales (NUEVO) ----------------
    path("", home_router, name="home_router"), # Ruta principal para el router de home
    path("alumno/home/", alumno_home, name="alumno_home"), # Home del alumno
    path("docente/espacio/<int:espacio_id>/", docente_espacio_detalle, name="docente_espacio_detalle"), # Detalle de espacio para docente

    # ---------------- Cartones ----------------
    path("carton/primaria/", buscar_carton_primaria, name="buscar_carton_primaria"),
    path("carton/primaria/<str:dni>/", carton_primaria_por_dni, name="carton_primaria"),
    path(
        "carton/primaria/<str:dni>/pdf/",
        carton_primaria_pdf,
        name="carton_primaria_pdf",
    ),
    path(
        "carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/",
        carton_por_prof_y_plan,
        name="carton_generico",
    ),
    path(
        "carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/pdf/",
        carton_generico_pdf,
        name="carton_generico_pdf",
    ),
    # ---------------- Panel -------------------
    path("panel/", panel, name="panel"),
    path("panel/home/", panel, name="panel_home"),
    # Panel de Estudiante (cartón por inscripción)
    # Nota: el view espera <int:insc_id>
    path("panel/estudiante/<int:insc_id>/", panel, name="estudiante_panel"),
    path(
        "panel/correlatividades/", panel_correlatividades, name="panel_correlatividades"
    ),
    path("panel/horarios/", panel_horarios, name="panel_horarios"),
    path("panel/docente/", panel_docente, name="panel_docente"),
    # NUEVO: Ruta para el formulario de correlatividades
    path("panel/correlatividades/form/", correlatividades_form_view, name="correlatividades_form"),
    # ---------------- CBVs (Alumnos) ----------
    path("alumnos/", EstudianteListView.as_view(), name="listado_alumnos"),
    path("alumnos/agregar/", EstudianteCreateView.as_view(), name="agregar_alumno"),
    path(
        "alumnos/modificar/<int:pk>/",
        EstudianteUpdateView.as_view(),
        name="modificar_alumno",
    ),
    path(
        "alumnos/eliminar/<int:pk>/",
        EstudianteDeleteView.as_view(),
        name="eliminar_alumno",
    ),
    # ---------------- CBVs (Docentes) ---------
    path("docentes/", DocenteListView.as_view(), name="listado_docentes"),
    path("docentes/agregar/", DocenteCreateView.as_view(), name="agregar_docente"),
    path(
        "docentes/modificar/<int:pk>/",
        DocenteUpdateView.as_view(),
        name="modificar_docente",
    ),
    path(
        "docentes/eliminar/<int:pk>/",
        DocenteDeleteView.as_view(),
        name="eliminar_docente",
    ),
    # ---------------- CBVs (Materias) ---------
    path("materias/", MateriaListView.as_view(), name="listado_materias"),
    path("materias/agregar/", MateriaCreateView.as_view(), name="agregar_materia"),
    path(
        "materias/modificar/<int:pk>/",
        MateriaUpdateView.as_view(),
        name="modificar_materia",
    ),
    path(
        "materias/eliminar/<int:pk>/",
        MateriaDeleteView.as_view(),
        name="eliminar_materia",
    ),
    # ---------------- APIs para el panel (AJAX) ----
    path(
        "api/espacios-por-inscripcion/<int:insc_id>/",
        api_espacios_habilitados,
        name="api_espacios_por_inscripcion",
    ),
    path("api/estudiantes/", api_listar_estudiantes, name="api_listar_estudiantes"),
    path("api/docentes/", api_listar_docentes, name="api_listar_docentes"),
    path("api/profesorados/", api_listar_profesorados, name="api_listar_profesorados"),
    path(
        "api/planes-estudios/",
        api_listar_planes_estudios,
        name="api_listar_planes_estudios",
    ),
    path(
        "api/estudiantes/<int:pk>/",
        api_get_estudiante_detalle,
        name="api_get_estudiante_detalle",
    ),
    path(
        "api/docentes/<int:pk>/",
        api_get_docente_detalle,
        name="api_get_docente_detalle",
    ),
    path(
        "api/espacios-curriculares/<int:pk>/",
        api_get_espacio_curricular_detalle,
        name="api_get_espacio_curricular_detalle",
    ),
    path(
        "api/movimientos/estudiante/<int:estudiante_id>/",
        api_get_movimientos_estudiante,
        name="api_get_movimientos_estudiante",
    ),
    # Dos rutas para correlatividades:
    # - Solo espacio (sin inscripción -> devuelve requisitos)
    path(
        "api/correlatividades/<int:espacio_id>/",
        api_get_correlatividades,
        name="api_correlatividades",
    ),
    # - Espacio + inscripción (evalúa si puede cursar)
    path(
        "api/correlatividades/<int:espacio_id>/<int:insc_id>/",
        api_get_correlatividades,
        name="api_correlatividades_con_insc",
    ),
    path("api/planes-por-profesorado/", api_get_planes_for_profesorado, name="api_get_planes_for_profesorado"),
    path("api/espacios-por-plan/", api_get_espacios_for_plan, name="api_get_espacios_for_plan"),
    # ---------------- Guardados (POST) --------------
    path(
        "panel/inscripciones/<int:insc_prof_id>/cursadas/crear/",
        crear_inscripcion_cursada,
        name="crear_inscripcion_cursada",
    ),
    path(
        "panel/cursadas/<int:insc_cursada_id>/movimientos/crear/",
        crear_movimiento,
        name="crear_movimiento",
    ),
    path("panel/cargar-nota/", cargar_nota, name="cargar_nota"),
    # ---------------- Redirecciones utilitarias -----
    path("redir/estudiante/<int:est_id>/", redir_estudiante, name="redir_estudiante"),
    path(
        "redir/inscripcion/<int:insc_id>/", redir_inscripcion, name="redir_inscripcion"
    ),
    path(
    "api/correlatividades-por-materia/",
    api_correlatividades_por_materia,
    name="api_correlatividades_por_materia",
    ),
]