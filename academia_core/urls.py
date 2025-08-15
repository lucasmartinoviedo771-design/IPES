from django.urls import path
from .views import (
    carton_primaria_por_dni, carton_primaria_pdf, buscar_carton_primaria,
    carton_por_prof_y_plan, carton_generico_pdf,
)
from .views_panel import panel_home

urlpatterns = [
    # Cartón fijo Primaria
    path("carton/primaria/", buscar_carton_primaria, name="buscar_carton_primaria"),
    path("carton/primaria/<str:dni>/", carton_primaria_por_dni, name="carton_primaria"),
    path("carton/primaria/<str:dni>/pdf/", carton_primaria_pdf, name="carton_primaria_pdf"),

    # Cartón genérico por slugs
    path("carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/",
         carton_por_prof_y_plan, name="carton_generico"),
    path("carton/<slug:prof_slug>/<slug:res_slug>/<str:dni>/pdf/",
         carton_generico_pdf, name="carton_generico_pdf"),

    # Panel único
    path("panel/", panel_home, name="panel_home"),
]
