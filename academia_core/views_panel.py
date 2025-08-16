# academia_core/views_panel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

# Importamos TODOS los formularios posibles
from .forms_carga import (
    CargarRegularidadForm,
    CargarFinalForm,
    InscripcionProfesoradoForm,
    InscripcionEspacioForm,
    InscripcionFinalForm,
    EstudianteForm,
    CargarNotaFinalForm,
    CargarResultadoFinalForm,
)
from .models import Profesorado


# ================ Helpers ===================

def _get_rol(user) -> str:
    perfil = getattr(user, "perfil", None)
    rol = getattr(perfil, "rol", None)
    return (rol or "USUARIO").upper()

def _profesorados_sidebar(user):
    perfil = getattr(user, "perfil", None)
    if perfil and hasattr(perfil, "profesorados_permitidos"):
        return perfil.profesorados_permitidos.all().order_by("nombre")
    return Profesorado.objects.all().order_by("nombre")

@dataclass
class Evento:
    creado: Any
    accion: str
    detalle: str

def _get_last_events(user, limit=15):
    return []

def _log_actividad(user, rol, accion, detalle):
    pass


# =============== Títulos / subtítulos ======================

ACTION_COPY: Dict[str, Tuple[str, str]] = {
    # secciones del menú
    "section_est":  ("Estudiantes", ""),
    "section_insc": ("Inscripciones", ""),
    "section_calif":("Calificaciones", ""),
    "section_admin":("Administración", ""),
    "section_help": ("Ayuda", ""),

    # formularios reales
    "add_est": ("Nuevo estudiante", "Cargá un estudiante nuevo."),
    "insc_prof": ("Inscribir a carrera", "Vincular estudiante a profesorado."),
    "insc_esp": ("Inscribir a materia", "Inscripción a cursada."),
    "insc_final": ("Inscribir a mesa de final", "Selecciona cursada regular vigente."),

    "cargar_cursada": ("Cargar Regularidad / Promoción", ""),
    "cargar_final": ("Cargar nota de final", ""),
    "cargar_nota_final": ("Cargar nota de final", ""),
    "cargar_final_resultado": ("Cargar resultado de final", ""),
}


# ============= Mapa formularios ============================

FORMS_MAP = {
    "add_est": EstudianteForm,
    "insc_prof": InscripcionProfesoradoForm,
    "insc_esp": InscripcionEspacioForm,
    "insc_final": InscripcionFinalForm,
    "cargar_cursada": CargarRegularidadForm,
    "cargar_final":  CargarFinalForm,
    "cargar_nota_final": CargarNotaFinalForm,
    "cargar_final_resultado": CargarResultadoFinalForm,
}


# ================ Vista principal ==========================

@login_required
def panel(request: HttpRequest) -> HttpResponse:
    """
    Vista del nuevo panel lateral.
    Si action empieza con 'section_' se muestran solo links,
    de lo contrario tratamos de renderizar un formulario.
    """
    # Acción activa
    action = request.GET.get("action") or request.POST.get("action") or "section_est"
    rol = _get_rol(request.user)

    # Título
    action_title, action_subtitle = ACTION_COPY.get(action, ("Panel", ""))

    # Base del contexto
    ctx: Dict[str, Any] = {
        "action": action,
        "action_title": action_title,
        "action_subtitle": action_subtitle,
        "form": None,
        "puede_cargar": True,
        "puede_editar": True,
        "bloquear_guardar": False,
        "profesorados": _profesorados_sidebar(request.user),
        "events": _get_last_events(request.user),
        "can_admin": (rol in {"ADMIN", "SECRETARIA", "DIRECTIVO"}),
        "rol": rol,
    }

    # --- detectamos si es un formulario concreto ---
    form_class = FORMS_MAP.get(action)
    if form_class is not None:
        if request.method == "POST" and request.POST.get("save") == "1":
            # Intenta instanciar el form pasando el usuario; si falla, lo instancia sin él
            try:
                form = form_class(request.POST, request.FILES, user=request.user)
            except TypeError:
                form = form_class(request.POST, request.FILES)

            if form.is_valid():
                obj = form.save()
                messages.success(request, "Guardado correctamente.")
                return redirect(f"{reverse('panel')}?action={action}")
            else:
                messages.error(request, "Revisá los errores del formulario.")
        else:
            # Para GET, intenta instanciar el form pasando el usuario; si falla, lo instancia vacío
            try:
                form = form_class(user=request.user)
            except TypeError:
                form = form_class()
        
        ctx["form"] = form

    return render(request, "panel.html", ctx)