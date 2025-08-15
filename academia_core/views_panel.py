from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
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
    Correlatividad,
)


# ----------------- Utilidades de rol/permisos -----------------

def _is_admin(user):
    """Verifica si el usuario es administrador (staff o superuser)."""
    return getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)

def _rol(user):
    perfil = getattr(user, "perfil", None)
    return getattr(perfil, "rol", None)

def _puede_editar(user) -> bool:
    """Quienes pueden crear/modificar: Secretaría y Bedel (y staff)."""
    if _is_admin(user):
        return True
    rol = _rol(user)
    return rol in {"SECRETARIA", "BEDEL"}

def _profes_visibles(user):
    perfil = getattr(user, "perfil", None)
    if perfil and perfil.rol in {"BEDEL", "TUTOR"}:
        return perfil.profesorados_permitidos.all().order_by("nombre")
    return Profesorado.objects.all().order_by("nombre")

def _log_actividad(user, rol, accion, detalle):
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

def _safe_delete(obj, request):
    """Helper para borrado seguro con fallback a inactivo."""
    try:
        obj.delete()
        messages.success(request, "Eliminación realizada.")
    except ProtectedError:
        if hasattr(obj, "activo"):
            obj.activo = False
            obj.save(update_fields=["activo"])
            messages.success(request, "El registro tiene datos vinculados. Se marcó como inactivo.")
        else:
            messages.error(request, "No se pudo eliminar porque existen registros relacionados.")


# ----------------- Vista principal del panel -----------------

@login_required
def panel(request):
    """Panel único (no disponible para estudiantes)."""
    rol = _rol(request.user)
    if rol == "ESTUDIANTE":
        return HttpResponseForbidden("Solo para personal administrativo y docentes.")

    valid_actions = (
        "cargar_mov", "insc_prof", "insc_esp", "add_est",
        "correlativas", "espacios_admin", "prof_new", "plan_new",
        "admin_rename", "admin_rename_profesorado", "admin_rename_plan", "admin_rename_espacio",
        "admin_delete", "admin_delete_profesorado", "admin_delete_plan", "admin_delete_espacio",
    )

    action = request.GET.get("action") or request.POST.get("action") or "cargar_mov"
    if action not in valid_actions:
        action = "cargar_mov"

    # Contexto base para todas las acciones
    puede_editar = _puede_editar(request.user)
    context = {
        "rol": rol,
        "puede_editar": puede_editar,
        "puede_cargar": puede_editar,
        "action": action,
        "profesorados": _profes_visibles(request.user),
        "events": Actividad.objects.order_by("-creado")[:20],
        "logout_url": "/accounts/logout/",
        "login_url": "/accounts/login/",
    }

    # ----------------- Nuevos Bloques de Acciones (Admin) -----------------
    
    # Crear profesorado
    if action == "prof_new":
        if not _is_admin(request.user): return HttpResponseForbidden("Acción solo para administradores.")
        context["action_title"] = "Crear profesorado"
        form = ProfesoradoCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            prof = form.save()
            messages.success(request, f"Profesorado «{prof.nombre}» creado.")
            return redirect(f'{reverse("panel")}?action=prof_new')
        context["profesorado_form"] = form
        return render(request, "panel.html", context)

    # Crear plan
    if action == "plan_new":
        if not _is_admin(request.user): return HttpResponseForbidden("Acción solo para administradores.")
        context["action_title"] = "Crear plan de estudios"
        form = PlanCreateForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            plan = form.save()
            messages.success(request, f"Plan «{plan.resolucion}» creado.")
            return redirect(f'{reverse("panel")}?action=plan_new')
        context["plan_form"] = form
        return render(request, "panel.html", context)

    # Modificar / renombrar (3 subformularios)
    if action in {"admin_rename", "admin_rename_profesorado", "admin_rename_plan", "admin_rename_espacio"}:
        if not _is_admin(request.user): return HttpResponseForbidden("Acción solo para administradores.")
        context["action"] = "admin_rename"
        context["action_title"] = "Modificar / renombrar"
        
        prof_form = RenombrarProfesoradoForm(request.POST if request.method == "POST" and request.POST.get("action") == "admin_rename_profesorado" else None)
        plan_form = RenombrarPlanForm(request.POST if request.method == "POST" and request.POST.get("action") == "admin_rename_plan" else request.GET or None)
        esp_form = RenombrarEspacioForm(request.POST if request.method == "POST" and request.POST.get("action") == "admin_rename_espacio" else request.GET or None)

        if request.method == "POST":
            sub = request.POST.get("action")
            if sub == "admin_rename_profesorado" and prof_form.is_valid():
                p = prof_form.cleaned_data["profesorado"]; p.nombre = prof_form.cleaned_data["nuevo_nombre"]; p.save(update_fields=["nombre"])
                messages.success(request, "Profesorado renombrado.")
                return redirect(f'{reverse("panel")}?action=admin_rename')
            if sub == "admin_rename_plan" and plan_form.is_valid():
                plan = plan_form.cleaned_data["plan"]; nuevo_nombre = plan_form.cleaned_data.get("nuevo_nombre"); nueva_res = plan_form.cleaned_data.get("nueva_resolucion"); fields = []
                if nuevo_nombre and hasattr(plan, "nombre"): plan.nombre = nuevo_nombre; fields.append("nombre")
                if nueva_res: plan.resolucion = nueva_res; fields.append("resolucion")
                if fields: plan.save(update_fields=fields); messages.success(request, "Plan actualizado.")
                else: messages.info(request, "No hubo cambios.")
                return redirect(f'{reverse("panel")}?action=admin_rename')
            if sub == "admin_rename_espacio" and esp_form.is_valid():
                esp = esp_form.cleaned_data["espacio"]; esp.nombre = esp_form.cleaned_data["nuevo_nombre"]; esp.save(update_fields=["nombre"])
                messages.success(request, "Espacio curricular renombrado.")
                return redirect(f'{reverse("panel")}?action=admin_rename')

        context.update({"ren_profesorado_form": prof_form, "ren_plan_form": plan_form, "ren_espacio_form": esp_form})
        return render(request, "panel.html", context)

    # Eliminar (3 subformularios)
    if action in {"admin_delete", "admin_delete_profesorado", "admin_delete_plan", "admin_delete_espacio"}:
        if not _is_admin(request.user): return HttpResponseForbidden("Acción solo para administradores.")
        context["action"] = "admin_delete"
        context["action_title"] = "Eliminar"

        del_prof = DeleteProfesoradoForm(request.POST if request.method == "POST" and request.POST.get("action") == "admin_delete_profesorado" else None)
        del_plan = DeletePlanForm(request.POST if request.method == "POST" and request.POST.get("action") == "admin_delete_plan" else request.GET or None)
        del_esp = DeleteEspacioForm(request.POST if request.method == "POST" and request.POST.get("action") == "admin_delete_espacio" else request.GET or None)

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
        
        context.update({"del_profesorado_form": del_prof, "del_plan_form": del_plan, "del_espacio_form": del_esp})
        return render(request, "panel.html", context)

    # ----------------- Acciones de Admin existentes -----------------
    if action in {"correlativas", "espacios_admin"}:
        if not _is_admin(request.user):
            return HttpResponseForbidden("Solo para administradores")

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

            context.update({
                "filtro_form": filtro_form, "espacios": lista, "espacio_form": esp_form, "editando": editar_id,
                "action_title": "Gestionar espacios curriculares", "action_subtitle": "Listar, crear, renombrar o eliminar espacios de un plan",
            })
            return render(request, "panel.html", context)

        if action == "correlativas":
            data = request.POST if request.method == "POST" else request.GET
            sel_form = SeleccionEspacioForm(data or None)
            espacio = sel_form.cleaned_data.get("espacio") if sel_form.is_valid() else None
            is_edit_post = request.method == "POST" and ({"cursar_regularizadas", "cursar_aprobadas", "rendir_aprobadas"} & set(request.POST.keys()))
            edit_form = None
            if is_edit_post and espacio:
                edit_form = EditaCorrelativasForm(espacio, request.POST)
                if edit_form.is_valid():
                    edit_form.sync_to_db()
                    messages.success(request, "Correlatividades actualizadas.")
                    return redirect(f"{reverse('panel')}?action=correlativas&profesorado={espacio.profesorado_id}&plan={espacio.plan_id}&espacio={espacio.id}")
            elif espacio:
                edit_form = EditaCorrelativasForm(espacio)
            
            context.update({
                "sel_form": sel_form, "edit_form": edit_form, "espacio_sel": espacio,
                "action_title": "Editar Correlatividades", "action_subtitle": "Definir qué materias se deben tener aprobadas para cursar/rendir",
            })
            return render(request, "panel.html", context)

    # ----------------- Acciones de carga (Secretaría/Bedel) - Default -----------------
    FormClass = {"cargar_mov": CargarMovimientoForm, "insc_prof": InscripcionProfesoradoForm, "insc_esp": InscripcionEspacioForm, "add_est": EstudianteForm}[action]
    wants_save = request.method == "POST" and request.POST.get("save") == "1"
    form = None

    if wants_save:
        if not puede_editar:
            messages.error(request, "No tenés permisos para cargar/inscribir.")
            return redirect(f'{reverse("panel")}?action={action}')
        form = FormClass(request.POST, request.FILES) if action == "add_est" else FormClass(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save()
            if action == "cargar_mov":
                _log_actividad(request.user, rol, "MOV_ALTA", f"{obj.inscripcion.estudiante.apellido}, {obj.inscripcion.estudiante.nombre} · {obj.espacio.nombre}")
                messages.success(request, "Movimiento cargado correctamente.")
                return redirect(f'{reverse("panel")}?action={action}')
            elif action == "insc_prof":
                _log_actividad(request.user, rol, "INSC_PROF", f"{obj.estudiante.apellido}, {obj.estudiante.nombre} · {obj.profesorado.nombre}")
                messages.success(request, "Inscripción a profesorado creada.")
                return redirect(f'{reverse("panel")}?action={action}')
            elif action == "insc_esp":
                _log_actividad(request.user, rol, "INSC_ESP", f"{obj.inscripcion.estudiante.apellido}, {obj.inscripcion.estudiante.nombre} · {obj.espacio.nombre} ({obj.anio_academico})")
                messages.success(request, "Inscripción a materia creada.")
                return redirect(f"{reverse('panel')}?action=insc_esp&inscripcion={obj.inscripcion_id}")
            else: # add_est
                _log_actividad(request.user, rol, "EST_ALTA", f"{obj.apellido}, {obj.nombre} · DNI {getattr(obj, 'dni', '') or ''}")
                messages.success(request, f"Estudiante creado correctamente. DNI: {getattr(obj, 'dni', '') or ''}")
                return redirect(f'{reverse("panel")}?action={action}')
        else:
            messages.error(request, "Revisá los datos del formulario.")
    else:
        # Formulario para GET o POST que no es de guardado
        if action == "add_est": form = FormClass(request.POST or None, request.FILES or None)
        elif action == "insc_esp": form = FormClass(data=request.POST or request.GET, user=request.user)
        else: form = FormClass(data=request.POST or None, user=request.user)

    action_titles = {"cargar_mov": "Regularidad y final", "insc_prof": "Inscripción a profesorado", "insc_esp": "Inscripción a materia", "add_est": "Alta de estudiante"}
    action_subtitles = {"cargar_mov": "Registrar un <strong>movimiento</strong>", "insc_prof": "Vínculo Estudiante ↔ Profesorado + legajo", "insc_esp": "Cursada por año", "add_est": "Carga rápida de datos básicos"}
    context.update({
        "form": form,
        "bloquear_guardar": (not puede_editar) and (action in {"cargar_mov", "insc_prof", "insc_esp", "add_est"}),
        "action_title": action_titles.get(action, ""),
        "action_subtitle": action_subtitles.get(action, ""),
        "buscar_carton_url": "buscar_carton_primaria",
    })
    return render(request, "panel.html", context)


# Alias para compatibilidad con URLs antiguas:
def panel_home(request, *args, **kwargs):
    """
    Entrada compatible: reusa la vista principal 'panel' para
    rutas antiguas que apuntaban a 'panel_home'.
    """
    return panel(request, *args, **kwargs)