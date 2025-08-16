# academia_core/views_panel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

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
    "section_est":  ("Estudiantes", ""),
    "section_insc": ("Inscripciones", ""),
    "section_calif":("Calificaciones", ""),
    "section_admin":("Administración", ""),
    "section_help": ("Ayuda", ""),

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
    action = request.GET.get("action") or request.POST.get("action") or "section_est"
    rol = _get_rol(request.user)

    action_title, action_subtitle = ACTION_COPY.get(action, ("Panel", ""))

    ctx = {
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

    form_class = FORMS_MAP.get(action)
    if form_class is not None:
        # ¿Es un POST de guardado?
        is_save = request.method == "POST" and request.POST.get("save") == "1"

        # Datos para bindear el form cuando NO estamos guardando (autosubmit de combos)
        bound_data = None
        if request.method in ("GET", "POST") and not is_save:
            data = {}
            data.update(request.GET.dict())
            data.update(request.POST.dict())
            # Nunca bindeamos 'action' ni 'save' (ni 'ok')
            for k in ("action", "save", "ok"):
                data.pop(k, None)
            bound_data = data

        # Instanciar form (algunos aceptan user=)
        try:
            if is_save:
                form = form_class(request.POST, request.FILES, user=request.user)
            elif bound_data:
                form = form_class(bound_data, user=request.user)
            else:
                form = form_class(user=request.user)
        except TypeError:
            if is_save:
                form = form_class(request.POST, request.FILES)
            elif bound_data:
                form = form_class(bound_data)
            else:
                form = form_class()

        if is_save:
            if form.is_valid():
                obj = form.save()
                messages.success(request, "Guardado correctamente.")

                # --- Sticky params tras guardar ---
                params = {"action": action, "ok": 1}
                if action == "insc_esp":
                    try:
                        insc_id = form.cleaned_data.get("inscripcion").pk
                        anio = form.cleaned_data.get("anio_academico")
                        if insc_id:
                            params["inscripcion"] = str(insc_id)
                        if anio:
                            params["anio_academico"] = str(anio)
                    except Exception:
                        pass

                url = f"{reverse('panel')}?{urlencode(params)}"
                return redirect(url)
            else:
                messages.error(request, "Hay errores en el formulario.")
                ctx["form"] = form
                return render(request, "panel.html", ctx)

        # GET o autosubmit: sólo render
        ctx["form"] = form

        # Correlatividades para insc_esp (si podemos calcularlas)
        if action == "insc_esp":
            correl_map = {}
            try:
                qs = form.fields["espacio"].queryset
                # Intento genérico de obtener requisitos
                for e in qs:
                    lst = []
                    # Probamos distintos nombres comunes
                    for attr in ("correlativas", "requisitos", "prerequisitos", "requisitos_previos"):
                        if hasattr(e, attr):
                            try:
                                objs = getattr(e, attr).all()
                                for o in objs:
                                    lst.append({"tipo": "Requisito", "nombre": getattr(o, "nombre", str(o))})
                            except Exception:
                                pass
                    if lst:
                        correl_map[str(e.pk)] = lst
            except Exception:
                correl_map = {}
            ctx["correl_map"] = correl_map

    return render(request, "panel.html", ctx)
