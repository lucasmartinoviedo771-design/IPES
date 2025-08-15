# academia_core/views_panel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from .forms_carga import (
    CargarRegularidadForm,
    CargarFinalForm,
    InscripcionProfesoradoForm,
    InscripcionEspacioForm,
    EstudianteForm,
)
from .forms_espacios import EspacioForm, FiltroEspaciosForm
from .forms_correlativas import SeleccionEspacioForm, EditaCorrelativasForm
from .forms_admin import (
    ProfesoradoCreateForm, PlanCreateForm,
    RenombrarProfesoradoForm, RenombrarPlanForm, RenombrarEspacioForm,
    DeleteProfesoradoForm, DeletePlanForm, DeleteEspacioForm
)
from .models import Profesorado, EspacioCurricular, Actividad

# =====================================================================================

def _get_rol(user):
    perfil = getattr(user, "perfil", None)
    return (getattr(perfil, "rol", None) or "USUARIO").upper()

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

def _get_last_events(user):
    return []

def _log(user, rol, accion, detalle):
    try:
        Actividad.objects.create(user=user, rol_cache=rol, accion=accion, detalle=detalle)
    except Exception:
        pass

# =====================================================================================

ACTION_COPY: Dict[str, Tuple[str, str]] = {
    # Secciones
    "section_est":  ("Estudiantes", ""),
    "section_insc": ("Inscripciones", ""),
    "section_calif":("Calificaciones", ""),
    "section_admin":("Administración", ""),
    "section_help": ("Ayuda", ""),

    # Formularios simples
    "add_est":     ("Nuevo estudiante", ""),
    "insc_prof":   ("Inscribir a carrera", ""),
    "insc_esp":    ("Inscribir a materia", ""),
    "cargar_cursada": ("Cargar Regularidad/Promoción", ""),
    "cargar_final":   ("Cargar nota de final", ""),

    # Administración
    "espacios_admin": ("Espacios curriculares", ""),
    "correlativas": ("Correlatividades", ""),
    "prof_new": ("Nuevo profesorado", ""),
    "plan_new": ("Nuevo plan", ""),
    "admin_rename": ("Renombrar entidades", ""),
    "admin_delete": ("Eliminar entidades", ""),
}

FORMS_MAP = {
    "add_est": EstudianteForm,
    "insc_prof": InscripcionProfesoradoForm,
    "insc_esp": InscripcionEspacioForm,
    "cargar_cursada": CargarRegularidadForm,
    "cargar_final":  CargarFinalForm,
}

# =====================================================================================

@login_required
def panel(request):
    action = request.GET.get("action") or request.POST.get("action") or "section_est"
    rol = _get_rol(request.user)

    ctx: Dict[str, Any] = {
        "action": action,
        "action_title": ACTION_COPY.get(action, ("Panel", ""))[0],
        "action_subtitle": ACTION_COPY.get(action, ("Panel", ""))[1],
        "form": None,
        "puede_cargar": True,
        "puede_editar": True,
        "bloquear_guardar": False,
        "profesorados": _profesorados_sidebar(request.user),
        "events": _get_last_events(request.user),
        "can_admin": (rol in {"ADMIN", "SECRETARIA", "DIRECTIVO"}),
        "rol": rol,
    }

    # =============== Formularios sencillos (altas / inscripciones / calif) ============
    form_class = FORMS_MAP.get(action)
    if form_class:
        if request.method == "POST" and request.POST.get("save") == "1":
            form = form_class(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                obj = form.save()
                messages.success(request, "Guardado correctamente.")
                return redirect(f"{reverse('panel')}?action={action}")
            else:
                messages.error(request, "Revisá los errores del formulario.")
        else:
            form = form_class(user=request.user)
        ctx["form"] = form
        return render(request, "panel.html", ctx)

    # =============== BLOQUES ADMIN (listados / ediciones) ============================
    if action == "espacios_admin":
        data = request.POST if request.method == "POST" else request.GET
        filtro = FiltroEspaciosForm(data or None)
        plan_sel = filtro.cleaned_data.get("plan") if filtro.is_valid() else None

        if request.method == "POST":
            if request.POST.get("op") == "delete":
                esp = get_object_or_404(EspacioCurricular, pk=request.POST.get("id"))
                esp.delete()
                messages.success(request, "Espacio eliminado.")
                return redirect(f"{reverse('panel')}?action=espacios_admin")
            if request.POST.get("op") == "save":
                esp_id = request.POST.get("id") or None
                inst = get_object_or_404(EspacioCurricular, pk=esp_id) if esp_id else None
                form_esp = EspacioForm(request.POST, instance=inst)
                if form_esp.is_valid():
                    form_esp.save()
                    messages.success(request, "Guardado.")
                    return redirect(f"{reverse('panel')}?action=espacios_admin")

        lista = EspacioCurricular.objects.filter(plan=plan_sel) if plan_sel else []
        ctx.update({"filtro_form": filtro, "espacios": lista, "espacio_form": EspacioForm()})
        return render(request, "panel.html", ctx)

    if action == "correlativas":
        data = request.POST if request.method == "POST" else request.GET
        sel = SeleccionEspacioForm(data or None)
        esp = sel.cleaned_data.get("espacio") if sel.is_valid() else None

        if request.method == "POST" and esp:
            form = EditaCorrelativasForm(esp, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Correlatividades guardadas.")
            return redirect(f"{reverse('panel')}?action=correlativas&espacio={esp.id}")

        ctx.update({"sel_form": sel, "espacio_sel": esp})
        if esp:
            ctx["edit_form"] = EditaCorrelativasForm(esp)
        return render(request, "panel.html", ctx)

    if action == "prof_new":
        form = ProfesoradoCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Profesorado creado.")
            return redirect(f"{reverse('panel')}?action=prof_new")
        ctx["profesorado_form"] = form
        return render(request, "panel.html", ctx)

    if action == "plan_new":
        form = PlanCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Plan creado.")
            return redirect(f"{reverse('panel')}?action=plan_new")
        ctx["plan_form"] = form
        return render(request, "panel.html", ctx)

    if action == "admin_rename":
        p_form = RenombrarProfesoradoForm(request.POST or None)
        pl_form = RenombrarPlanForm(request.POST or None)
        e_form = RenombrarEspacioForm(request.POST or None)
        if request.method == "POST":
            if p_form.is_valid():
                obj = p_form.save(); messages.success(request, "Profesorado renombrado.")
            if pl_form.is_valid():
                obj = pl_form.save(); messages.success(request, "Plan renombrado.")
            if e_form.is_valid():
                obj = e_form.save(); messages.success(request, "Espacio renombrado.")
            return redirect(f"{reverse('panel')}?action=admin_rename")
        ctx.update({
            "ren_profesorado_form": p_form,
            "ren_plan_form": pl_form,
            "ren_espacio_form": e_form
        })
        return render(request, "panel.html", ctx)

    if action == "admin_delete":
        dp = DeleteProfesoradoForm(request.POST or None)
        dpl = DeletePlanForm(request.POST or None)
        de = DeleteEspacioForm(request.POST or None)
        if request.method == "POST":
            form_name = request.POST.get("action")
            if form_name == "admin_delete_profesorado" and dp.is_valid():
                dp.cleaned_data["profesorado"].delete()
                messages.success(request, "Profesorado eliminado.")
            if form_name == "admin_delete_plan" and dpl.is_valid():
                dpl.cleaned_data["plan"].delete()
                messages.success(request, "Plan eliminado.")
            if form_name == "admin_delete_espacio" and de.is_valid():
                de.cleaned_data["espacio"].delete()
                messages.success(request, "Espacio eliminado.")
            return redirect(f"{reverse('panel')}?action=admin_delete")
        ctx.update({
            "del_profesorado_form": dp,
            "del_plan_form": dpl,
            "del_espacio_form": de
        })
        return render(request, "panel.html", ctx)

    # Si caemos acá → es una section_* → se muestran enlaces
    return render(request, "panel.html", ctx)
