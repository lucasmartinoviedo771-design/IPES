from django.urls import path
from django.contrib.auth.views import LogoutView

from .views import (
    carton_primaria_por_dni, carton_primaria_pdf, buscar_carton_primaria,
    carton_por_prof_y_plan, carton_generico_pdf,
)
from .views_panel import panel_home
from .views_cbv import (
    # Estudiantes
    EstudianteListView, EstudianteCreateView,
    EstudianteUpdateView, EstudianteDeleteView,
    # Docentes
    DocenteListView, DocenteCreateView,
    DocenteUpdateView, DocenteDeleteView,
)
from .views_auth import RoleAwareLoginView  # ⬅️ NUEVO

urlpatterns = [
    # Auth
    path("accounts/login/", RoleAwareLoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="/accounts/login/"), name="logout"),

    # Cartón fijo Primaria
    path("carton/primaria/", buscar_carton_primaria, name="buscar_carton_primaria"),
    path("carton/primaria/<str:dni>/", carton_primaria_por_dni, name="carton_primaria"),
    path("carton/primaria/<str:dni>/pdf/", carton_primaria_pdf, name="carton_primaria_pdf"),

    # Cartón genérico por slugs
    path(
        "carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/",
        carton_por_prof_y_plan, name="carton_generico"
    ),
    path(
        "carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/pdf/",
        carton_generico_pdf, name="carton_generico_pdf"
    ),

    # Panel único
    path("panel/", panel_home, name="panel_home"),

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
]
