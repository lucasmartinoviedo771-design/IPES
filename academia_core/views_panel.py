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


# imports necesarios arriba del archivo
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from .models import (
    EstudianteProfesorado,
    EspacioCurricular,
    InscripcionEspacio,
)

def _plan_vigente_id(prof):
    pv = getattr(prof, "plan_vigente", None)
    return getattr(pv, "id", None)

@login_required
@require_GET
def get_espacios_por_inscripcion(request, insc_id: int):
    """
    Devuelve JSON para poblar el <select name="espacio"> en forms dependientes.
    Parámetros:
      - mode: 'regularidad' (default) | 'final'
        * regularidad: primero intenta cursadas de esa inscripción; si no hay, todos los espacios del profesorado
        * final: todos los espacios del profesorado (opcionalmente por plan vigente si hay)
    """
    mode = request.GET.get("mode", "regularidad")
    try:
        insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
    except EstudianteProfesorado.DoesNotExist:
        return JsonResponse({"ok": False, "error": "inscripcion_not_found", "items": []}, status=404)

    # helper: espacios del profesorado (aplica plan vigente solo si tiene resultados)
    def _espacios_profesorado():
        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_id = _plan_vigente_id(insc.profesorado)
        if plan_id:
            base_pv = base.filter(plan_id=plan_id)
            if base_pv.exists():
                base = base_pv
        return base.order_by("anio", "cuatrimestre", "nombre")

    if mode == "final":
        esp_qs = _espacios_profesorado()
    else:
        # regularidad: si hay cursadas para esta inscripción, usamos esas
        cursadas_ids = list(
            InscripcionEspacio.objects
            .filter(inscripcion=insc)   # ✅ en tu proyecto la FK se llama 'inscripcion'
            .values_list("espacio_id", flat=True)
            .distinct()
        )
        if cursadas_ids:
            esp_qs = EspacioCurricular.objects.filter(id__in=cursadas_ids).order_by("anio", "cuatrimestre", "nombre")
        else:
            esp_qs = _espacios_profesorado()

    items = [{"id": e.id, "nombre": e.nombre} for e in esp_qs]
    return JsonResponse({"ok": True, "items": items})



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
