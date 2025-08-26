from django.urls import path
from . import views

app_name = "ui"

urlpatterns = [
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),

    # Personas
    path("estudiantes", views.EstudianteListView.as_view(), name="estudiantes_list"),
    path("estudiantes/<int:pk>", views.EstudianteDetailView.as_view(), name="estudiantes_detail"),
    path("personas/estudiantes/nuevo", views.NuevoEstudianteView.as_view(), name="estudiante_nuevo"),
    path("docentes", views.DocenteListView.as_view(), name="docentes_list"),
    path("personas/docentes/nuevo", views.NuevoDocenteView.as_view(), name="docente_nuevo"),

    # Inscripciones
    path("inscripciones/carrera", views.InscribirCarreraView.as_view(), name="inscribir_carrera"),
    path("inscripciones/materia", views.InscribirMateriaView.as_view(), name="inscribir_materia"),
    path("inscripciones/mesa-final", views.InscribirFinalView.as_view(), name="inscribir_final"),
    path("inscripciones/profesorado", views.InscripcionProfesoradoView.as_view(), name="inscripcion_profesorado"),

    # Cartón e Histórico del Estudiante
    path("estudiante/carton", views.CartonEstudianteView.as_view(), name="carton_estudiante"),
    path("estudiante/historico", views.HistoricoEstudianteView.as_view(), name="historico_estudiante"),

    # Opcional: Cambiar rol
    path("cambiar-rol", views.SwitchRoleView.as_view(), name="switch_role"),
]