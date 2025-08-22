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
)
from .forms_carga import (
    EstudianteForm,
    InscripcionProfesoradoForm,
    InscripcionEspacioForm,
    MovimientoForm,
)
from .utils import get, coalesce, year_now

# ============================ Helpers de formato ============================

def _fmt_date(d):
    try:
        if isinstance(d, (date, datetime)):
            return d.strftime("%d/%m/%Y")
    except Exception:
        pass
    return str(d)

def _ord(n):
    if not n:
        return ""
    try:
        n = int(n)
    except Exception:
        return ""
    return f"{n}º Año"

def _cuatri_label(x):
    if x in (None, "", 0):
        return ""
    try:
        x = int(x)
    except Exception:
        s = str(x).upper().strip()
        if s in ("ANUAL", "A"):
            return "Anual"
        m = re.search(r"\d+", s)
        return f"{m.group(0)}º C" if m else s
    return "Anual" if x == 0 else f"{x}º C"

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
    return "Docente/Estudiante"

def _base_context(request: HttpRequest) -> Dict[str, Any]:
    user = getattr(request, "user", None)
    can_admin = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    try:
        profesorados = list(Profesorado.objects.all().order_by("nombre"))
    except Exception:
        profesorados = []
    return {"rol": _role_for(user), "can_admin": can_admin, "profesorados": profesorados}

# ============================== Vistas HTML ================================

@login_required
def panel_inicio(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    return render(request, "academia_core/panel_inicio.html", ctx)

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
def profesorados_list(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    qs = Profesorado.objects.all().order_by("nombre")
    ctx.update({"items": qs})
    return render(request, "profesorado_list.html", ctx)

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


@login_required
@require_GET
def get_espacios_por_inscripcion(request: HttpRequest, insc_id: int):
    """
    Versión final y definitiva: Devuelve los espacios que un estudiante puede cursar,
    aplicando todos los filtros de negocio según el reglamento académico.
    """
    try:
        insc = EstudianteProfesorado.objects.select_related("profesorado", "estudiante").get(pk=insc_id)
        estudiante = insc.estudiante
    except EstudianteProfesorado.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Inscripción no encontrada"}, status=404)

    # 1. Búsqueda inicial de todas las materias de la carrera
    qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado).order_by("anio", "cuatrimestre", "nombre")

    # 2. Filtro: Excluir materias en las que YA se inscribió en el año académico seleccionado
    anio_academico = request.GET.get("anio_academico")
    if anio_academico and anio_academico.isdigit():
        ya_inscripto_ids = InscripcionEspacio.objects.filter(
            inscripcion=insc,
            anio_academico=int(anio_academico)
        ).values_list("espacio_id", flat=True)
        
        if ya_inscripto_ids.exists():
            qs = qs.exclude(pk__in=ya_inscripto_ids)

    # 3. Filtro Definitivo: Excluir materias APROBADAS o con REGULARIDAD VIGENTE
    try:
        # A) Materias con APROBACIÓN FINAL (Promoción, Aprobado directo, Final Regular/Libre, Equivalencia)
        aprobadas_ids = set(Movimiento.objects.filter(
            Q(inscripcion__estudiante=estudiante, tipo="REG", condicion__codigo__in=["PROMOCION", "APROBADO"]) |
            Q(inscripcion__estudiante=estudiante, tipo="FIN", nota_num__gte=6) |
            Q(inscripcion__estudiante=estudiante, condicion__codigo="EQUIVALENCIA")
        ).values_list("espacio_id", flat=True))

        # B) Materias con REGULARIDAD VIGENTE (2 años y 45 días)
        fecha_limite = timezone.now().date() - timedelta(days=775) # 365*2 + 45
        regular_vigente_ids = set(Movimiento.objects.filter(
            inscripcion__estudiante=estudiante,
            tipo="REG",
            condicion__codigo="REGULAR",
            fecha__gte=fecha_limite
        ).values_list("espacio_id", flat=True))

        # C) Unimos todos los IDs que se deben excluir
        ids_a_excluir = aprobadas_ids.union(regular_vigente_ids)

        if ids_a_excluir:
            qs = qs.exclude(pk__in=ids_a_excluir)
            
    except (FieldError, NameError):
        pass

    # 4. Filtro: Aplicar CORRELATIVIDADES
    if evaluar_correlatividades:
        espacios_permitidos_ids = [
            espacio.id for espacio in qs 
            if evaluar_correlatividades(insc, espacio, tipo="CURSAR")[0]
        ]
        qs = qs.filter(pk__in=espacios_permitidos_ids)

    # Respuesta final
    items = [{"id": e.id, "nombre": _espacio_label(e)} for e in qs]
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
    Crea una InscripcionEspacio (cursada) de manera segura desde el panel.
    """
    insc = get_object_or_404(EstudianteProfesorado.objects.select_related("estudiante", "profesorado"), pk=insc_prof_id)

    # intentamos inferir año académico si no viene
    initial = {}
    anio_in = request.POST.get("anio_academico")
    if not anio_in:
        try:
            initial["anio_academico"] = year_now()
        except Exception:
            initial["anio_academico"] = timezone.now().year

    # wrapper para construir un form aceptando kwargs extra si corresponde
    def _build_form(FormClass, data=None, files=None, initial=None):
        try:
            return FormClass(data, files, request=request, user=getattr(request, "user", None), initial=initial)
        except TypeError:
            try:
                return FormClass(data, files, initial=initial)
            except TypeError:
                try:
                    return FormClass(data, files)
                except TypeError:
                    return FormClass()

    form = _build_form(InscripcionEspacioForm, request.POST or None, request.FILES or None, initial=initial)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    obj: InscripcionEspacio = form.save(commit=False)
    obj.inscripcion = insc

    # EstadoInscripcion default si el form no lo define
    estado_val = form.cleaned_data.get("estado")
    if not estado_val:
        try:
            estado_val = getattr(EstadoInscripcion, "EN_CURSO", "EN_CURSO")
        except Exception:
            estado_val = "EN_CURSO"
    obj.estado = estado_val

    obj.save()
    return JsonResponse({"ok": True, "id": obj.pk, "label": _espacio_label(obj.espacio)})

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

# =============================== FIN DEL ARCHIVO ==========================
