from __future__ import annotations

from typing import Iterable, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import ProtectedError
from django.http import HttpResponseForbidden, HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

# --- Formularios ---
from .forms_carga import (
    CargarMovimientoForm,
    InscripcionProfesoradoForm,
    InscripcionEspacioForm,
    EstudianteForm,
)
from .forms_correlativas import SeleccionEspacioForm, EditaCorrelativasForm
from .forms_espacios import EspacioForm, FiltroEspaciosForm
from .forms_admin import (
    ProfesoradoCreateForm, PlanCreateForm,
    RenombrarProfesoradoForm, RenombrarPlanForm, RenombrarEspacioForm,
    DeleteProfesoradoForm, DeletePlanForm, DeleteEspacioForm,
)

# --- Modelos ---
from .models import (
    Profesorado,
    Actividad,
    PlanEstudios,
    EspacioCurricular,
)

# ----------------- Copys por acción (título + subtítulo) -----------------
ACTION_COPY: dict[str, tuple[str, str]] = {
    # Acciones principales
    "add_est": (
        "Nuevo estudiante",
        "Cargá los datos básicos del estudiante. Podés adjuntar foto y marcar si queda activo."
    ),
    "insc_prof": (
        "Inscribir a carrera",
        "Alta en un profesorado/cohorte. Si la documentación está incompleta, queda con legajo <strong>condicional</strong>."
    ),
    "insc_esp": (
        "Inscribir a materia",
        "Seleccioná la inscripción y el espacio curricular. Filtra según correlativas vigentes para CURSAR."
    ),
    "cargar_mov": (
        "Notas y condición",
        "Cargá <em>Regularidad</em>, <em>Promoción</em> o <em>Final</em>. Si marcás <strong>Ausente</strong>, la nota se deshabilita. "
        "Para <strong>Equivalencia</strong>, completá la disposición interna."
    ),

    # Admin de espacios (editor simple de plan)
    "espacios_admin": (
        "Editar espacios del plan",
        "Listá, creá, editá o eliminá espacios del plan actual."
    ),

    # Correlatividades (admin)
    "correlativas": (
        "Correlatividades",
        "Definí requisitos para <strong>CURSAR</strong> (REG/APR) y <strong>RENDIR</strong> (APR) por espacio."
    ),

    # Admin: crear entidades
    "prof_new": (
        "Nuevo profesorado",
        "Dá de alta un profesorado. El <em>slug</em> se autogenera si lo dejás vacío."
    ),
    "plan_new": (
        "Nuevo plan",
        "Creá un plan de estudios para un profesorado. El <em>slug</em> se autogenera si lo dejás vacío."
    ),

    # Admin: renombrar/eliminar
    "admin_rename": (
        "Renombrar",
        "Cambiá rótulos sin afectar IDs ni relaciones."
    ),
    "admin_delete": (
        "Eliminar",
        "Borrá o marcá inactivo si existen relaciones protegidas."
    ),
}

# ----------------- Permisos de administración -----------------
ADMIN_ACTIONS: set[str] = {
    "correlativas", "espacios_admin",
    "prof_new", "plan_new",
    "admin_rename", "admin_rename_profesorado", "admin_rename_plan", "admin_rename_espacio",
    "admin_delete", "admin_delete_profesorado", "admin_delete_plan", "admin_delete_espacio",
}

# Con este set de permisos un usuario NO-staff puede administrar si se le asignan explícitamente
REQUIRED_PERMS: tuple[str, ...] = (
    "academia_core.add_profesorado",
    "academia_core.change_planestudios",
    "academia_core.add_espaciocurricular",
)

# ----------------- Utilidades de rol/permisos -----------------

def _can_admin(user) -> bool:
    """¿Tiene permisos de administración del panel? (superuser o permisos de modelo)."""
    return getattr(user, "is_superuser", False) or user.has_perms(REQUIRED_PERMS)

def _rol(user) -> Optional[str]:
    perfil = getattr(user, "perfil", None)
    return getattr(perfil, "rol", None)

def _puede_editar(user) -> bool:
    """Quienes pueden crear/modificar movimientos e inscripciones: Secretaría y Bedel (y admins)."""
    if _can_admin(user):
        return True
    rol = _rol(user)
    return rol in {"SECRETARIA", "BEDEL"}

def _profes_visibles(user):
    perfil = getattr(user, "perfil", None)
    qs = Profesorado.objects.all().order_by("nombre")
    if perfil and getattr(perfil, "rol", None) in {"BEDEL", "TUTOR"}:
        return perfil.profesorados_permitidos.all().order_by("nombre")
    return qs

def _log_actividad(user, rol: Optional[str], accion: str, detalle: str) -> None:
    """Registro simple para 'Última actividad'."""
    try:
        Actividad.objects.create(
            user=user,
            rol_cache=str(rol),
            accion=accion,
            detalle=detalle,
        )
    except Exception:
        # No romper la UX si falla auditoría
        pass

def _safe_delete(obj: models.Model, request: HttpRequest) -> None:
    """Borrado seguro con fallback a inactivo si hay relaciones protegidas."""
    try:
        obj.delete()
        messages.success(request, "Eliminación realizada.")
    except ProtectedError:
        if hasattr(obj, "activo"):
            setattr(obj, "activo", False)
            obj.save(update_fields=["activo"])
            messages.success(request, "El registro tiene datos vinculados. Se marcó como inactivo.")
        else:
            messages.error(request, "No se pudo eliminar porque existen registros relacionados.")

def _ultimas_actividades(max_total: int = 2, max_login: int = 2) -> list[Actividad]:
    """
    Devuelve una lista de actividades recientes, limitando la cantidad de LOGIN a `max_login`.
    Mantiene el orden por fecha descendente y completa con otros eventos hasta `max_total`.
    """
    candidatos = Actividad.objects.order_by("-creado")[: max_total * 5]
    salida: list[Actividad] = []
    logins = 0
    for ev in candidatos:
        if ev.accion == "LOGIN":
            if logins >= max_login:
                continue
            logins += 1
        salida.append(ev)
        if len(salida) >= max_total:
            break
    return salida

# ----------------- Vista principal del panel -----------------

@login_required
def panel(request: HttpRequest) -> HttpResponse:
    """Panel único (no disponible para estudiantes)."""
    rol = _rol(request.user)
    if rol == "ESTUDIANTE":
        return HttpResponseForbidden("Solo para personal administrativo y docentes.")

    # Acción solicitada
    valid_actions: set[str] = set(ACTION_COPY.keys()) | {
        # subacciones internas para admin
        "admin_rename_profesorado", "admin_rename_plan", "admin_rename_espacio",
        "admin_delete_profesorado", "admin_delete_plan", "admin_delete_espacio",
    }
    action = request.POST.get("action") or request.GET.get("action") or "cargar_mov"
    if action not in valid_actions:
        action = "cargar_mov"

    # Gate centralizado para acciones de administración
    if action in ADMIN_ACTIONS and not _can_admin(request.user):
        return HttpResponseForbidden("Acción solo para administradores.")

    # Contexto base
    puede_editar = _puede_editar(request.user)
    context = {
        "rol": rol,
        "puede_editar": puede_editar,
        "puede_cargar": puede_editar,
        "can_admin": _can_admin(request.user),
        "action": action,
        "profesorados": _profes_visibles(request.user),
        "events": _ultimas_actividades(2, 2),
        "logout_url": "/accounts/logout/",
        "login_url": "/accounts/login/",
    }

    # ----------- Admin: crear entidades -----------
    if action == "prof_new":
        title, subtitle = ACTION_COPY["prof_new"]
        form = ProfesoradoCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                prof = form.save()
            messages.success(request, f"Profesorado «{prof.nombre}» creado.")
            return redirect(f'{reverse("panel")}?action=prof_new')
        context.update({"action_title": title, "action_subtitle": subtitle, "profesorado_form": form})
        return render(request, "panel.html", context)

    if action == "plan_new":
        title, subtitle = ACTION_COPY["plan_new"]
        form = PlanCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                plan = form.save()
            messages.success(request, f"Plan «{plan.resolucion}» creado.")
            return redirect(f'{reverse("panel")}?action=plan_new')
        context.update({"action_title": title, "action_subtitle": subtitle, "plan_form": form})
        return render(request, "panel.html", context)

    # ----------- Admin: renombrar -----------
    if action in {"admin_rename", "admin_rename_profesorado", "admin_rename_plan", "admin_rename_espacio"}:
        title, subtitle = ACTION_COPY["admin_rename"]

        prof_form = RenombrarProfesoradoForm(
            request.POST if request.method == "POST" and request.POST.get("action") == "admin_rename_profesorado" else None
        )
        plan_form = RenombrarPlanForm(
            request.POST if request.method == "POST" and request.POST.get("action") == "admin_rename_plan" else request.GET or None
        )
        esp_form = RenombrarEspacioForm(
            request.POST if request.method == "POST" and request.POST.get("action") == "admin_rename_espacio" else request.GET or None
        )

        if request.method == "POST":
            sub = request.POST.get("action")
            if sub == "admin_rename_profesorado" and prof_form.is_valid():
                p = prof_form.cleaned_data["profesorado"]
                p.nombre = prof_form.cleaned_data["nuevo_nombre"]
                p.save(update_fields=["nombre"])
                messages.success(request, "Profesorado renombrado.")
                return redirect(f'{reverse("panel")}?action=admin_rename')

            if sub == "admin_rename_plan" and plan_form.is_valid():
                plan = plan_form.cleaned_data["plan"]
                nuevo_nombre = plan_form.cleaned_data.get("nuevo_nombre")
                nueva_res = plan_form.cleaned_data.get("nueva_resolucion")
                fields: list[str] = []
                if nuevo_nombre and hasattr(plan, "nombre"):
                    plan.nombre = nuevo_nombre
                    fields.append("nombre")
                if nueva_res:
                    plan.resolucion = nueva_res
                    fields.append("resolucion")
                if fields:
                    plan.save(update_fields=fields)
                    messages.success(request, "Plan actualizado.")
                else:
                    messages.info(request, "No hubo cambios.")
                return redirect(f'{reverse("panel")}?action=admin_rename')

            if sub == "admin_rename_espacio" and esp_form.is_valid():
                esp = esp_form.cleaned_data["espacio"]
                esp.nombre = esp_form.cleaned_data["nuevo_nombre"]
                esp.save(update_fields=["nombre"])
                messages.success(request, "Espacio curricular renombrado.")
                return redirect(f'{reverse("panel")}?action=admin_rename')

        context.update({
            "action": "admin_rename",
            "action_title": title,
            "action_subtitle": subtitle,
            "ren_profesorado_form": prof_form,
            "ren_plan_form": plan_form,
            "ren_espacio_form": esp_form,
        })
        return render(request, "panel.html", context)

    # ----------- Admin: eliminar -----------
    if action in {"admin_delete", "admin_delete_profesorado", "admin_delete_plan", "admin_delete_espacio"}:
        title, subtitle = ACTION_COPY["admin_delete"]

        del_prof = DeleteProfesoradoForm(
            request.POST if request.method == "POST" and request.POST.get("action") == "admin_delete_profesorado" else None
        )
        del_plan = DeletePlanForm(
            request.POST if request.method == "POST" and request.POST.get("action") == "admin_delete_plan" else request.GET or None
        )
        del_esp = DeleteEspacioForm(
            request.POST if request.method == "POST" and request.POST.get("action") == "admin_delete_espacio" else request.GET or None
        )

        if request.method == "POST":
            sub = request.POST.get("action")
            if sub == "admin_delete_profesorado" and del_prof.is_valid():
                _safe_delete(del_prof.cleaned_data["profesorado"], request)
                return redirect(f'{reverse("panel")}?action=admin_delete')

            if sub == "admin_delete_plan" and del_plan.is_valid():
                _safe_delete(del_plan.cleaned_data["plan"], request)
                return redirect(f'{reverse("panel")}?action=admin_delete')

            if sub == "admin_delete_espacio" and del_esp.is_valid():
                _safe_delete(del_esp.cleaned_data["espacio"], request)
                return redirect(f'{reverse("panel")}?action=admin_delete')

        context.update({
            "action": "admin_delete",
            "action_title": title,
            "action_subtitle": subtitle,
            "del_profesorado_form": del_prof,
            "del_plan_form": del_plan,
            "del_espacio_form": del_esp,
        })
        return render(request, "panel.html", context)

    # ----------- Admin: espacios / correlativas -----------
    if action == "espacios_admin":
        data = request.POST if request.method == "POST" else request.GET
        filtro_form = FiltroEspaciosForm(data or None)
        plan_sel = filtro_form.cleaned_data.get("plan") if filtro_form.is_valid() else None

        if request.method == "POST":
            op = request.POST.get("op")
            if op == "delete":
                esp = get_object_or_404(EspacioCurricular, pk=request.POST.get("id"))
                _safe_delete(esp, request)
                return redirect(f"{reverse('panel')}?action=espacios_admin&profesorado={esp.profesorado_id}&plan={esp.plan_id}")

            if op == "save":
                esp_id = request.POST.get("id") or None
                inst = get_object_or_404(EspacioCurricular, pk=esp_id) if esp_id else None
                esp_form = EspacioForm(request.POST, instance=inst)
                if esp_form.is_valid():
                    with transaction.atomic():
                        esp = esp_form.save()
                    messages.success(request, f"Espacio guardado: {esp.nombre}")
                    return redirect(f"{reverse('panel')}?action=espacios_admin&profesorado={esp.profesorado_id}&plan={esp.plan_id}")
                else:
                    messages.error(request, "Revisá los datos del formulario.")

        lista = EspacioCurricular.objects.filter(plan=plan_sel).order_by("anio", "cuatrimestre", "nombre") if plan_sel else EspacioCurricular.objects.none()
        editar_id = request.GET.get("edit")
        if editar_id:
            esp_form = EspacioForm(instance=get_object_or_404(EspacioCurricular, pk=editar_id))
        else:
            initial = {"profesorado": filtro_form.cleaned_data["profesorado"].pk, "plan": filtro_form.cleaned_data["plan"].pk} if plan_sel else {}
            esp_form = EspacioForm(initial=initial)

        title, subtitle = ACTION_COPY["espacios_admin"]
        context.update({
            "filtro_form": filtro_form,
            "espacios": lista,
            "espacio_form": esp_form,
            "editando": editar_id,
            "action_title": title,
            "action_subtitle": subtitle,
        })
        return render(request, "panel.html", context)

    if action == "correlativas":
        data = request.POST if request.method == "POST" else request.GET
        sel_form = SeleccionEspacioForm(data or None)
        espacio = sel_form.cleaned_data.get("espacio") if sel_form.is_valid() else None
        edit_form = None
        is_edit_post = request.method == "POST" and ({"cursar_regularizadas", "cursar_aprobadas", "rendir_aprobadas"} & set(request.POST.keys()))

        if is_edit_post and espacio:
            edit_form = EditaCorrelativasForm(espacio, request.POST)
            if edit_form.is_valid():
                with transaction.atomic():
                    edit_form.sync_to_db()
                messages.success(request, "Correlatividades actualizadas.")
                return redirect(f"{reverse('panel')}?action=correlativas&profesorado={espacio.profesorado_id}&plan={espacio.plan_id}&espacio={espacio.id}")
        elif espacio:
            edit_form = EditaCorrelativasForm(espacio)

        title, subtitle = ACTION_COPY["correlativas"]
        context.update({
            "sel_form": sel_form,
            "edit_form": edit_form,
            "espacio_sel": espacio,
            "action_title": title,
            "action_subtitle": subtitle,
        })
        return render(request, "panel.html", context)

    # ----------- Acciones de carga (Secretaría/Bedel) - Default -----------
    forms_map = {
        "cargar_mov": CargarMovimientoForm,
        "insc_prof": InscripcionProfesoradoForm,
        "insc_esp": InscripcionEspacioForm,
        "add_est": EstudianteForm,
    }
    FormClass = forms_map[action]

    wants_save = request.method == "POST" and request.POST.get("save") == "1"
    form = None

    if wants_save:
        if not puede_editar:
            messages.error(request, "No tenés permisos para cargar/inscribir.")
            return redirect(f'{reverse("panel")}?action={action}')

        if action == "add_est":
            form = FormClass(request.POST, request.FILES)
        elif action == "insc_esp":
            form = FormClass(data=request.POST, user=request.user)
        else:
            form = FormClass(data=request.POST, user=request.user)

        if form.is_valid():
            with transaction.atomic():
                obj = form.save()

            if action == "cargar_mov":
                _log_actividad(request.user, rol, "MOV_ALTA", f"{obj.inscripcion.estudiante.apellido}, {obj.inscripcion.estudiante.nombre} · {obj.espacio.nombre}")
                messages.success(request, "Movimiento cargado correctamente.")
                return redirect(f'{reverse("panel")}?action={action}')

            if action == "insc_prof":
                _log_actividad(request.user, rol, "INSC_PROF", f"{obj.estudiante.apellido}, {obj.estudiante.nombre} · {obj.profesorado.nombre}")
                messages.success(request, "Inscripción a profesorado creada.")
                return redirect(f'{reverse("panel")}?action={action}')

            if action == "insc_esp":
                _log_actividad(request.user, rol, "INSC_ESP", f"{obj.inscripcion.estudiante.apellido}, {obj.inscripcion.estudiante.nombre} · {obj.espacio.nombre} ({obj.anio_academico})")
                messages.success(request, "Inscripción a materia creada.")
                return redirect(f"{reverse('panel')}?action=insc_esp&inscripcion={obj.inscripcion_id}")

            # add_est
            _log_actividad(request.user, rol, "EST_ALTA", f"{obj.apellido}, {obj.nombre} · DNI {getattr(obj, 'dni', '') or ''}")
            messages.success(request, f"Estudiante creado correctamente. DNI: {getattr(obj, 'dni', '') or ''}")
            return redirect(f'{reverse("panel")}?action={action}')
        else:
            messages.error(request, "Revisá los datos del formulario.")
    else:
        # Formulario GET o POST no-guardar
        if action == "add_est":
            form = FormClass(request.POST or None, request.FILES or None)
        elif action == "insc_esp":
            form = FormClass(data=request.POST or request.GET, user=request.user)
        else:
            form = FormClass(data=request.POST or None, user=request.user)

    title, subtitle = ACTION_COPY.get(action, ("", ""))
    context.update({
        "form": form,
        "bloquear_guardar": (not puede_editar) and (action in {"cargar_mov", "insc_prof", "insc_esp", "add_est"}),
        "action_title": title,
        "action_subtitle": subtitle,
        "buscar_carton_url": "buscar_carton_primaria",
    })
    return render(request, "panel.html", context)


# Alias para compatibilidad con URLs antiguas:
def panel_home(request: HttpRequest, *args, **kwargs) -> HttpResponse:
    """Entrada compatible: reusa la vista principal 'panel' para rutas antiguas."""
    return panel(request, *args, **kwargs)


# ------------ Helper opcional para el header ------------
def get_role_label(user) -> str:
    """Etiqueta simple para mostrar en el header."""
    if not getattr(user, "is_authenticated", False):
        return "Anónimo"
    if getattr(user, "is_superuser", False):
        return "Superadmin"
    if getattr(user, "is_staff", False):
        return "Admin"
    return "Usuario"
