from django.urls import path
from .views import (
    DashboardView,
    EstudianteListView, EstudianteDetailView, NuevoEstudianteView,
    DocenteListView, NuevoDocenteView,
    InscribirCarreraView, InscribirMateriaView, InscribirFinalView, InscripcionProfesoradoView,
    CartonEstudianteView, HistoricoEstudianteView,
    SwitchRoleView,
    CorrelatividadesView,
)
from . import api

app_name = "ui"

urlpatterns = [
    path("dashboard", DashboardView.as_view(), name="dashboard"),

    # Personas
    path("estudiantes", EstudianteListView.as_view(), name="estudiantes_list"),
    path("estudiantes/<int:pk>", EstudianteDetailView.as_view(), name="estudiantes_detail"),
    path("personas/estudiantes/nuevo", NuevoEstudianteView.as_view(), name="estudiante_nuevo"),
    path("docentes", DocenteListView.as_view(), name="docentes_list"),
    path("personas/docentes/nuevo", NuevoDocenteView.as_view(), name="docente_nuevo"),

    # Inscripciones
    path("inscripciones/carrera", InscripcionProfesoradoView.as_view(), name="inscribir_carrera"),
    path("inscribir/materias", InscribirMateriaView.as_view(), name="inscribir_materias"),
    path("inscripciones/mesa-final", InscribirFinalView.as_view(), name="inscribir_final"),
    path("inscripciones/profesorado", InscripcionProfesoradoView.as_view(), name="inscripcion_profesorado"),

    # Académico
    path("academico/correlatividades", CorrelatividadesView.as_view(), name="correlatividades"),

    # Cartón e Histórico del Estudiante
    path("estudiante/carton", CartonEstudianteView.as_view(), name="carton_estudiante"),
    path("estudiante/historico", HistoricoEstudianteView.as_view(), name="historico_estudiante"),

    # Cambiar rol
    path("cambiar-rol", SwitchRoleView.as_view(), name="switch_role"),

    # API Endpoints
    path("api/planes", api.api_planes_por_carrera, name="api_planes"),
    path("api/cohortes", api.api_cohortes_por_plan, name="api_cohortes"),
    path("api/materias", api.api_materias_por_plan, name="api_materias_por_plan"),
    path("api/correlatividades", api.api_correlatividades_por_espacio, name="api_correlatividades_por_espacio"),
]