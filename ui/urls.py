# ui/urls.py (extracto)
from django.urls import path
from . import views

app_name = "ui"

urlpatterns = [
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),

    # Personas
    path("estudiantes", views.EstudianteListView.as_view(), name="estudiantes_list"),
    path("estudiantes/<int:pk>", views.EstudianteDetailView.as_view(), name="estudiantes_detail"),
    path("estudiantes/nuevo", views.EstudianteCreateView.as_view(), name="estudiantes_new"),
    path("docentes", views.DocenteListView.as_view(), name="docentes_list"),

    # Inscripciones
    path("inscripciones/carrera", views.InscribirCarreraView.as_view(), name="inscribir_carrera"),
    path("inscripciones/materia", views.InscribirMateriaView.as_view(), name="inscribir_materia"),
    path("inscripciones/mesa-final", views.InscribirFinalView.as_view(), name="inscribir_final"),

    # Calificaciones
    path("calificaciones/cargar", views.CargarNotasView.as_view(), name="cargar_notas"),

    # Estudiante
    path("estudiante/historico", views.HistoricoEstudianteView.as_view(), name="estudiante_historico"),
    path("estudiante/carton", views.CartonEstudianteView.as_view(), name="estudiante_carton"),
]
