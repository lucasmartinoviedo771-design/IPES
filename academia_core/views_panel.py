from __future__ import annotations

import re
from statistics import mean
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import FieldError

try:
    from .correlativas import evaluar_correlatividades
except Exception:
    evaluar_correlatividades = None

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone  # <<< agregado para initial de anio_academico
from django.db.models import Q
from django.core.exceptions import FieldError
from .models import Correlatividad, Movimiento, Condicion


try:
    from .label_utils import espacio_etiqueta as _espacio_label_from_utils
except Exception:
    _espacio_label_from_utils = None

from .models import (
    Estudiante,
    Profesorado,
    EspacioCurricular,
    EstudianteProfesorado,
    InscripcionEspacio,
    InscripcionFinal,
    CondicionAdmin,
    EstadoInscripcion,   # <- agregado para el endpoint de guardado
    Movimiento,  # <-- usado para aprobadas/regularidad
    Docente,
)
from .forms_carga import (
    EstudianteForm,
    InscripcionProfesoradoForm,
    InscripcionEspacioForm,
    MovimientoForm,
)
from .forms_student import StudentInscripcionEspacioForm, StudentInscripcionFinalForm
from .utils import get

def panel_docente(request):
    try:
        docente = Docente.objects.get(email=request.user.email)
        espacios = docente.espacios.all()
    except Docente.DoesNotExist:
        espacios = []

    return render(request, 'panel_docente.html', {'espacios': espacios})


def panel_horarios(request):
    try:
        estudiante = Estudiante.objects.get(email=request.user.email)
        inscripciones = EstudianteProfesorado.objects.filter(estudiante=estudiante)
        profesorados = [i.profesorado for i in inscripciones]
        espacios = EspacioCurricular.objects.filter(profesorado__in=profesorados)
        horarios = Horario.objects.filter(espacio__in=espacios).order_by('dia_semana', 'hora_inicio')
        dias_semana = Horario.DIAS
    except Estudiante.DoesNotExist:
        horarios = []
        dias_semana = []

    return render(request, 'panel_horarios.html', {'horarios': horarios, 'dias_semana': dias_semana})



def panel_correlatividades(request):
    try:
        estudiante = Estudiante.objects.get(email=request.user.email)
        inscripciones = EstudianteProfesorado.objects.filter(estudiante=estudiante)
        profesorados = [i.profesorado for i in inscripciones]
        espacios = EspacioCurricular.objects.filter(profesorado__in=profesorados)

        correlatividades = []
        for espacio in espacios:
            correlatividad_rules = Correlatividad.objects.filter(espacio=espacio)
            correlatividades.append({
                'espacio': espacio,
                'rules': correlatividad_rules
            })

    except Estudiante.DoesNotExist:
        correlatividades = []

    return render(request, 'panel_correlatividades.html', {'correlatividades': correlatividades})


# ============================ Helpers de formato ============================

def _fmt_date(d):
    try:
        if isinstance(d, (date, datetime)):
            return d.strftime("%d/%m/%Y")
    except Exception:
        pass
    return str(d)

def _ord(n: Optional[int]) -> str:
    try:
        n = int(n)
        return f"{n}º"
    except Exception:
        return "—"

def _cuatri_label(cuatri: Optional[int], formato: Optional[str]) -> str:
    """
    Traduce cuatrimestre / formato a etiqueta legible:
    1 -> '1º C', 2 -> '2º C', None/0/Anual -> 'Anual'
    """
    if cuatri in (1, 2):
        return f"{cuatri}º C"
    # si no hay valor, tratamos como anual
    txt = (formato or "").strip().lower()
    return "Anual" if not txt else ("Anual" if "anual" in txt else "Anual")

def _espacio_label(e: EspacioCurricular) -> str:
    if _espacio_label_from_utils:
        try:
            return _espacio_label_from_utils(e)
        except Exception:
            pass
    anio_s = _ord(getattr(e, "anio", None))
    cuatri_s = _cuatri_label(getattr(e, "cuatrimestre", None))
    nombre = getattr(e, "nombre", "")
    left = " · ".join([p for p in [anio_s, cuatri_s] if p])
    return f"{left} — {nombre}" if left and nombre else (nombre or str(e))

def _safe_order(qs, *candidates):
    for cand in candidates:
        try:
            return qs.order_by(*cand)
        except FieldError:
            continue
    return qs.order_by("id")

# ======= Helper de acceso para endpoints que requieren Secretaría/Admin ====

def is_sec_or_admin(u):
    return (
        getattr(u, "is_authenticated", False)
        and (getattr(u, "is_staff", False) or getattr(u, "is_superuser", False))
    )

def _role_for(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "Invitado"
    if getattr(user, "is_superuser", False):
        return "Admin"
    if getattr(user, "is_staff", False):
        return "Secretaría"
    try:
        if hasattr(user, "rol") and user.rol:
            return str(user.rol)
        if user.groups.filter(name__iexact="Docente").exists():
            return "Docente"
        if user.groups.filter(name__iexact="Estudiante").exists():
            return "Estudiante"
    except Exception:
        pass
    return "Usuario"

def _base_context(request: HttpRequest) -> Dict[str, Any]:
    user = getattr(request, "user", None)
    can_admin = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    try:
        profesorados = list(Profesorado.objects.all().order_by("nombre"))
    except Exception:
        profesorados = []
    return {"rol": _role_for(user), "can_admin": can_admin, "profesorados": profesorados}

@login_required
def panel(request: HttpRequest) -> HttpResponse:
    """
    Vista unificada del panel.
    Redirige a la plantilla correcta según el rol del usuario.
    """
    user = request.user
    role = _role_for(user)

    if role in ["Admin", "Secretaría"]:
        ctx = _base_context(request)
    
        # === LA LÍNEA CLAVE QUE FALTABA ===
        # Leemos el parámetro 'action' de la URL. Si no existe, usamos 'section_est' como valor por defecto.
        action = request.GET.get("action", "section_est")
        
        # Pasamos la acción y el formulario (inicialmente vacío) a la plantilla
        ctx["action"] = action
        ctx["form"] = None
        
        # Títulos por defecto
        ctx["action_title"] = "Inicio"
        ctx["action_subtitle"] = "Bienvenido al panel de gestión."

        # Ahora, según la 'action', definimos el título y cargamos el formulario correspondiente
        if action == "add_est":
            ctx["action_title"] = "Nuevo Estudiante"
            ctx["action_subtitle"] = "Completa los datos para dar de alta un nuevo estudiante."
            ctx["form"] = EstudianteForm()

        elif action == "insc_prof":
            ctx["action_title"] = "Inscribir a Carrera"
            ctx["action_subtitle"] = "Selecciona un estudiante y un profesorado para crear una nueva inscripción."
            ctx["form"] = InscripcionProfesoradoForm()

        elif action == "insc_esp":
            ctx["action_title"] = "Inscribir a Espacio Curricular"
            ctx["action_subtitle"] = "Inscribe a un estudiante en una materia para el ciclo académico actual."
            form = InscripcionEspacioForm()
            # Ponemos el año actual por defecto en el campo anio_academico (si existe)
            try:
                form.fields["anio_academico"].initial = timezone.now().year
            except Exception:
                pass
            ctx["form"] = form
        
        # Agregamos los títulos para las secciones que no tienen formulario
        elif action == "section_est":
            ctx["action_title"] = "Estudiantes"
            ctx["action_subtitle"] = "Gestiona los estudiantes existentes o crea uno nuevo."
            
        elif action == "section_insc":
            ctx["action_title"] = "Inscripciones"
            ctx["action_subtitle"] = "Gestiona las inscripciones a carreras, materias y mesas de examen."
            
        elif action == "section_calif":
            ctx["action_title"] = "Calificaciones"
            ctx["action_subtitle"] = "Carga y gestiona las calificaciones de los estudiantes."
            
        elif action == "section_admin":
            ctx["action_title"] = "Administración"
            ctx["action_subtitle"] = "Configuración de espacios, planes y correlatividades."
            
        elif action == "section_help":
            ctx["action_title"] = "Ayuda"
            ctx["action_subtitle"] = "Información y soporte."

        # Finalmente, renderizamos la plantilla con todo el contexto preparado
        return render(request, "academia_core/panel_inicio.html", ctx)
    elif role == "Estudiante":
        action = request.GET.get("action") or "tray"
        ctx: Dict[str, Any] = {"action": action}
        ctx.update(_base_ctx_est(request))

        TITLES = {
            "tray": ("Mi trayectoria", ""),
            "correl": ("Consulta de correlatividades", ""),
            "sit": ("Situación académica", ""),
            "horarios": ("Horarios", ""),
            "insc_esp": ("Inscribirme a una materia", ""),
            "insc_final": ("Inscribirme a un final", ""),
            "hist": ("Histórico (cartón)", "Vista consolidada por espacio con regularidad y mesas finales."),
        }
        if action in TITLES:
            ctx["action_title"], ctx["action_subtitle"] = TITLES[action]

        if action == "insc_esp":
            form = StudentInscripcionEspacioForm(request.POST or None, request=request)
            if request.method == "POST" and form.is_valid():
                form.save()
                return redirect(f"{reverse('panel_estudiante')}?action=insc_esp&ok=1")
            ctx["form"] = form

        elif action == "insc_final":
            form = StudentInscripcionFinalForm(request.POST or None, request=request)
            if request.method == "POST" and form.is_valid():
                form.save()
                return redirect(f"{reverse('panel_estudiante')}?action=insc_final&ok=1")
            ctx["form"] = form

        elif action == "tray":
            est = getattr(request.user, "estudiante", None)
            try:
                if est is None and request.user.email:
                    est = Estudiante.objects.filter(email__iexact=request.user.email).first()
            except Exception:
                est = None
            if est:
                inscs = EstudianteProfesorado.objects.filter(estudiante=est)
                cursadas = InscripcionEspacio.objects.filter(inscripcion__in=inscs).select_related("espacio")
            else:
                cursadas = InscripcionEspacio.objects.none()
            ctx["cursadas"] = cursadas

        elif action == "correl":
            return panel_correlatividades(request)

        elif action == "horarios":
            return panel_horarios(request)

        elif action == "hist":
            ctx["carton_rows"] = _carton_rows(request)

        return render(request, "panel_estudiante.html", ctx)
    elif role == "Docente":
        return panel_docente(request)


# ============================== Vistas HTML ================================



@login_required
def estudiante_list(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    q = request.GET.get("q", "").strip()
    qs = Estudiante.objects.all()
    if q:
        qs = qs.filter(
            Q(apellidos__icontains=q)
            | Q(nombres__icontains=q)
            | Q(dni__icontains=q)
            | Q(email__icontains=q)
        )
    qs = _safe_order(qs, ["apellidos", "nombres"])
    ctx.update({"items": qs, "q": q})
    return render(request, "estudiante_list.html", ctx)

@login_required
def estudiante_edit(request: HttpRequest, pk: Optional[int] = None) -> HttpResponse:
    ctx = _base_context(request)
    if pk:
        est = get_object_or_404(Estudiante, pk=pk)
    else:
        est = Estudiante()

    if request.method == "POST":
        form = EstudianteForm(request.POST or None, request.FILES or None, instance=est)
        if form.is_valid():
            est = form.save()
            messages.success(request, "Estudiante guardado correctamente.")
            return redirect(reverse("estudiante_edit", args=[est.pk]))
        messages.error(request, "Por favor, corrige los errores.")
    else:
        form = EstudianteForm(instance=est)

    ctx.update({"form": form, "estudiante": est})
    return render(request, "estudiante_edit.html", ctx)



@login_required
def estudiante_panel(request: HttpRequest, insc_id: int) -> HttpResponse:
    """
    Cartón del estudiante: vista general con materias por año, correlatividades y promedio.
    """
    inscripcion = get_object_or_404(
        EstudianteProfesorado.objects.select_related("estudiante", "profesorado"),
        pk=insc_id
    )
    estudiante = inscripcion.estudiante
    profesorado = inscripcion.profesorado

    # datos de plan si los hay (opcionales)
    try:
        plan = getattr(profesorado, "plan", None)
    except Exception:
        plan = None

    # bloques por año / cuatrimestre
    try:
        espacios = EspacioCurricular.objects.filter(profesorado=profesorado)
    except Exception:
        espacios = EspacioCurricular.objects.none()

    # ordenar por año/cuatrimestre/nombre de forma robusta
    espacios = _safe_order(espacios, ["anio", "cuatrimestre", "nombre"], ["nombre"])

    bloques: Dict[str, List[Dict[str, Any]]] = {}
    notas_finales: List[float] = []

    for e in espacios:
        anio = getattr(e, "anio", None)
        key = str(anio or 0)
        rows: List[Dict[str, Any]] = bloques.setdefault(key, [])
        rows.append({
            "id": e.id,
            "label": _espacio_label(e),
            "anio": anio,
            "cuatri": getattr(e, "cuatrimestre", None),
            "espacio": getattr(e, "nombre", str(e)),
            "rows":    rows,
        })

    promedio_db = get(inscripcion, "promedio_general", None)
    promedio_calc = round(mean(notas_finales), 2) if notas_finales else None
    promedio_general = promedio_db if promedio_db not in (None, "") else promedio_calc

    ctx = {
        "estudiante": estudiante,
        "profesorado": profesorado,
        "inscripcion": inscripcion,
        "plan": plan,
        "bloques": bloques,
        "promedio_general": promedio_general,
    }
    return render(request, "panel_estudiante_carton.html", ctx)


# =============================== Endpoints JSON ===========================


# En: academia_core/views_panel.py

# En: academia_core/views_panel.py

# Asegúrate de tener estos imports al principio del archivo
from .models import Correlatividad, Movimiento, Condicion



@login_required
@require_GET
def get_espacios_por_inscripcion(request: HttpRequest, insc_id: int):
    """
    Versión CORREGIDA: Incluye una lógica de filtros y correlatividades funcional.
    """
    try:
        insc = EstudianteProfesorado.objects.select_related("profesorado", "estudiante").get(pk=insc_id)
        estudiante = insc.estudiante
    except EstudianteProfesorado.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Inscripción no encontrada"}, status=404)

    # --- OBTENER ESTADO ACADÉMICO DEL ALUMNO ---
    # Obtenemos de una sola vez todas las materias que el alumno tiene APROBADAS o REGULARIZADAS
    movimientos_alumno = Movimiento.objects.filter(inscripcion__estudiante=estudiante)

    materias_aprobadas_ids = set(movimientos_alumno.filter(
        Q(tipo="REG", condicion__codigo__in=["PROMOCION", "APROBADO"]) |
        Q(tipo="FIN", nota_num__gte=6) |
        Q(condicion__codigo="EQUIVALENCIA")
    ).values_list("espacio_id", flat=True))

    materias_regularizadas_ids = set(movimientos_alumno.filter(
        condicion__codigo__in=["REGULAR", "PROMOCION", "APROBADO"]
    ).values_list("espacio_id", flat=True))


    # 1. Búsqueda inicial de todas las materias de la carrera
    qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado)

    # 2. Filtro: Excluir APROBADAS
    if materias_aprobadas_ids:
        qs = qs.exclude(pk__in=materias_aprobadas_ids)

    # 3. Filtro: Excluir ya inscriptas en el año (si aplica)
    anio_academico = request.GET.get("anio_academico")
    if anio_academico and anio_academico.isdigit():
        ya_inscripto_ids = InscripcionEspacio.objects.filter(
            inscripcion=insc, anio_academico=int(anio_academico)
        ).values_list("espacio_id", flat=True)
        if ya_inscripto_ids.exists():
            qs = qs.exclude(pk__in=ya_inscripto_ids)

    # 4. Filtro final: Aplicar CORRELATIVIDADES
    # Iteramos sobre las materias restantes y verificamos si se cumplen los requisitos
    espacios_permitidos = []
    for espacio in qs:
        # Buscamos todas las reglas de correlatividad para cursar este espacio
        reglas = Correlatividad.objects.filter(espacio=espacio, tipo="CURSAR")

        # Si no hay reglas, la materia está permitida
        if not reglas.exists():
            espacios_permitidos.append(espacio)
            continue

        # Si hay reglas, verificamos que se cumplan todas
        cumple_todas = True
        for regla in reglas:
            if regla.requisito == "APROBADA":
                if regla.requiere_espacio_id not in materias_aprobadas_ids:
                    cumple_todas = False
                    break # Si una falla, no hace falta seguir revisando
            elif regla.requisito == "REGULARIZADA":
                if regla.requiere_espacio_id not in materias_regularizadas_ids:
                    cumple_todas = False
                    break

        if cumple_todas:
            espacios_permitidos.append(espacio)

    # La respuesta final se basa en la lista filtrada por correlatividades
    items = [{"id": e.id, "nombre": _espacio_label(e)} for e in espacios_permitidos]
    return JsonResponse({"ok": True, "items": items})
    
    
    
    
    """
    Versión de DEPURACIÓN: Devuelve los espacios que un estudiante puede cursar,
    imprimiendo en la terminal cada paso del filtro.
    """
    print("\n--- INICIANDO DEPURACIÓN DE get_espacios_por_inscripcion ---")
    try:
        insc = EstudianteProfesorado.objects.select_related("profesorado", "estudiante").get(pk=insc_id)
        estudiante = insc.estudiante
        print(f"1. Estudiante encontrado: {estudiante}")
    except EstudianteProfesorado.DoesNotExist:
        print("!!! ERROR: Inscripción no encontrada.")
        return JsonResponse({"ok": False, "error": "Inscripción no encontrada"}, status=404)

    # 1. Búsqueda inicial
    qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado).order_by("anio", "cuatrimestre", "nombre")
    print(f"2. Materias totales de la carrera: {qs.count()}")

    # 2. Filtro: Excluir ya inscriptas en el año
    anio_academico = request.GET.get("anio_academico")
    if anio_academico and anio_academico.isdigit():
        ya_inscripto_ids = InscripcionEspacio.objects.filter(
            inscripcion=insc,
            anio_academico=int(anio_academico)
        ).values_list("espacio_id", flat=True)

        if ya_inscripto_ids.exists():
            print(f"3. Excluyendo {len(ya_inscripto_ids)} materias ya inscriptas en {anio_academico}.")
            qs = qs.exclude(pk__in=ya_inscripto_ids)
            print(f"   Materias restantes tras filtro de inscriptas: {qs.count()}")

    # 3. Filtro: Excluir APROBADAS o con REGULARIDAD VIGENTE
    try:
        aprobadas_ids = set(Movimiento.objects.filter(
            Q(inscripcion__estudiante=estudiante, tipo="REG", condicion__codigo__in=["PROMOCION", "APROBADO"]) |
            Q(inscripcion__estudiante=estudiante, tipo="FIN", nota_num__gte=6) |
            Q(inscripcion__estudiante=estudiante, condicion__codigo="EQUIVALENCIA")
        ).values_list("espacio_id", flat=True))
        print(f"4. IDs de materias APROBADAS encontradas: {aprobadas_ids}")

        fecha_limite = timezone.now().date() - timedelta(days=775)
        regular_vigente_ids = set(Movimiento.objects.filter(
            inscripcion__estudiante=estudiante,
            tipo="REG",
            condicion__codigo="REGULAR",
            fecha__gte=fecha_limite
        ).values_list("espacio_id", flat=True))
        print(f"5. IDs de materias con REGULARIDAD VIGENTE encontradas: {regular_vigente_ids}")

        ids_a_excluir = aprobadas_ids.union(regular_vigente_ids)
        print(f"6. IDs totales a excluir (aprobadas + regulares): {ids_a_excluir}")

        if ids_a_excluir:
            qs = qs.exclude(pk__in=ids_a_excluir)

        print(f"   Materias restantes tras filtro de aprobadas/regulares: {qs.count()}")

    except (FieldError, NameError) as e:
        print(f"!!! ERROR en el filtro de aprobadas/regulares: {e}")
        pass

    # 4. Filtro: Aplicar CORRELATIVIDADES
    if evaluar_correlatividades:
        print("7. Aplicando filtro de CORRELATIVIDADES...")
        # Usaremos una lista temporal para ver qué está pasando
        espacios_finales_ids = []
        for espacio in qs:
            puede_cursar, _ = evaluar_correlatividades(insc, espacio)
            if puede_cursar:
                espacios_finales_ids.append(espacio.id)
            # Opcional: Descomenta la siguiente línea para ver por qué se rechaza una materia
            # else:
            #     print(f"   -> RECHAZADA por correlatividad: {espacio.nombre}")

        qs = qs.filter(pk__in=espacios_finales_ids)
        print(f"   Materias restantes tras filtro de correlatividades: {qs.count()}")
    else:
        print("7. ADVERTENCIA: La función 'evaluar_correlatividades' no está disponible.")

    # Respuesta final
    items = [{"id": e.id, "nombre": _espacio_label(e)} for e in qs]
    print("--- FIN DEPURACIÓN ---")
    return JsonResponse({"ok": True, "items": items})
@login_required
@require_GET
def get_correlatividades(request: HttpRequest, espacio_id: int, insc_id: Optional[int] = None):
    """
    Devuelve (según el helper `correlativas`) los requisitos del espacio y si se cumplen.
    """
    try:
        espacio = EspacioCurricular.objects.get(pk=espacio_id)
    except EspacioCurricular.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Espacio no encontrado"}, status=404)

    try:
        from .correlativas import evaluar_correlatividades, obtener_requisitos_para
    except Exception:
        return JsonResponse({"ok": True, "detalles": [], "puede_cursar": True})

    if insc_id:
        try:
            insc = EstudianteProfesorado.objects.get(pk=insc_id)
        except EstudianteProfesorado.DoesNotExist:
            return JsonResponse({"ok": False, "error": "Inscripción no encontrada"}, status=404)
        ok, detalles = evaluar_correlatividades(insc, espacio)
        data = [{
            "espacio_id": d["requisito"].espacio_id,
            "etiqueta": d["requisito"].etiqueta,
            "minimo": d["requisito"].minimo,
            "cumplido": d["cumplido"],
            "estado_encontrado": d.get("estado_encontrado"),
            "motivo": d.get("motivo"),
        } for d in detalles]
        return JsonResponse({"ok": True, "puede_cursar": bool(ok), "detalles": data})

    # si no hay insc_id, devolvemos solo los requisitos del espacio
    reqs = obtener_requisitos_para(espacio)
    data = [{
        "espacio_id": r.espacio_id,
        "etiqueta": r.etiqueta,
        "minimo": r.minimo,
    } for r in reqs]
    return JsonResponse({"ok": True, "detalles": data})

# ---------------------- Endpoints de guardado/altas -----------------------



@login_required
@require_POST
def crear_inscripcion_cursada(request: HttpRequest, insc_prof_id: int):
    """
    Versión CORREGIDA para guardar la inscripción a la cursada.
    """
    insc = get_object_or_404(EstudianteProfesorado, pk=insc_prof_id)

    # Creamos el formulario directamente con los datos del POST
    form = InscripcionEspacioForm(request.POST)

    if form.is_valid():
        # Guardamos el objeto pero sin mandarlo a la base de datos todavía
        obj = form.save(commit=False)

        # Asignamos manualmente la inscripción del estudiante, ya que no es parte del formulario
        obj.inscripcion = insc

        # Ahora sí, guardamos el objeto completo en la base de datos
        obj.save()

        # Devolvemos una respuesta JSON de éxito
        return JsonResponse({"ok": True, "id": obj.pk, "label": _espacio_label(obj.espacio)})
    else:
        # Si el formulario no es válido, devolvemos los errores en formato JSON
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
        
        
        
        
@login_required
@require_POST
def crear_movimiento(request: HttpRequest, insc_cursada_id: int):
    """
    Crea un Movimiento (REG/FIN) asociado a una InscripcionEspacio.
    """
    cursada = get_object_or_404(InscripcionEspacio.objects.select_related("inscripcion", "espacio"), pk=insc_cursada_id)
    form = MovimientoForm(request.POST or None, request.FILES or None)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    mv: Movimiento = form.save(commit=False)
    mv.inscripcion = cursada.inscripcion
    mv.espacio = cursada.espacio
    mv.save()
    return JsonResponse({"ok": True, "id": mv.pk})

# --------------------------- Utilitarios simples --------------------------

@login_required
def redir_estudiante(request: HttpRequest, est_id: int) -> HttpResponse:
    est = get_object_or_404(Estudiante, pk=est_id)
    return redirect(reverse("estudiante_edit", args=[est.pk]))

@login_required
def redir_inscripcion(request: HttpRequest, insc_id: int) -> HttpResponse:
    insc = get_object_or_404(EstudianteProfesorado, pk=insc_id)
    return redirect(reverse("estudiante_panel", args=[insc.pk]))




