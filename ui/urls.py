from django.urls import path
from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="home"),
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),

    path("inscripciones/carrera", views.InscribirCarreraView.as_view()),
    path("inscripciones/materia", views.InscribirMateriaView.as_view()),
    path("inscripciones/mesa-final", views.InscribirMesaFinalView.as_view()),

    path("calificaciones/cargar", views.CargarNotasView.as_view()),
    path("calificaciones/regularidades", views.RegularidadesView.as_view()),

    path("correlatividades", views.CorrelatividadesView.as_view()),
    path("horarios", views.HorariosView.as_view()),
    path("espacios", views.EspaciosView.as_view()),
    path("planes", views.PlanesView.as_view()),
    path("estudiantes", views.EstudiantesView.as_view()),
    path("docentes", views.DocentesView.as_view()),

    path("periodos", views.PeriodosView.as_view()),
    path("usuarios", views.UsuariosView.as_view()),
    path("parametros", views.ParametrosView.as_view()),
    path("auditoria", views.AuditoriaView.as_view()),
    path("ayuda", views.AyudaView.as_view()),
]
