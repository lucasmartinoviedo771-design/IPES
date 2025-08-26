# ui/urls.py
from django.urls import path
from . import views

app_name = "ui"

urlpatterns = [
    # Home dinámico por rol
    path("", views.HomeView.as_view(), name="root"),

    # Dashboard (no Estudiante)
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),

    # Mi trayectoria (Estudiante)
    path("mi/historico", views.EstudianteHistoricoView.as_view(), name="historico_estudiante"),
    path("mi/carton", views.EstudianteCartonView.as_view(), name="carton_estudiante"),

    # Académico
    path("inscripciones/carrera", views.InscribirCarreraView.as_view(), name="inscribir_carrera"),
    path("inscripciones/materia", views.InscribirMateriaView.as_view(), name="inscribir_materia"),
    path("inscripciones/mesa-final", views.InscribirMesaFinalView.as_view(), name="inscribir_mesa_final"),
    path("calificaciones/cargar", views.CargarNotasView.as_view(), name="cargar_notas"),
    path("calificaciones/regularidades", views.RegularidadesView.as_view(), name="regularidades"),
    path("correlatividades", views.CorrelatividadesView.as_view(), name="correlatividades"),

    # Planificación
    path("horarios", views.HorariosView.as_view(), name="horarios"),
    path("espacios", views.EspaciosView.as_view(), name="espacios"),
    path("planes", views.PlanesView.as_view(), name="planes"),

    # Personas
    path("estudiantes", views.EstudiantesView.as_view(), name="estudiantes"),
    path("estudiantes/nuevo", views.EstudianteNuevoView.as_view(), name="estudiante_nuevo"),
    path("docentes", views.DocentesView.as_view(), name="docentes"),

    # Administración
    path("periodos", views.PeriodosView.as_view(), name="periodos"),
    path("usuarios", views.UsuariosPermisosView.as_view(), name="usuarios"),
    path("parametros", views.ParametrosView.as_view(), name="parametros"),
    path("auditoria", views.AuditoriaView.as_view(), name="auditoria"),

    # Ayuda
    path("ayuda", views.AyudaView.as_view(), name="ayuda"),
]