from __future__ import annotations

import re
from statistics import mean
from typing import Any, Dict, List, Optional
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import FieldError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET

# Etiquetas (opcional)
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
    # === IMPORTE AGREGADO ===
    CondicionAdmin,
)
from .forms_carga import (
    EstudianteForm,
    InscripcionProfesoradoForm,
    InscripcionEspacioForm,
    InscripcionFinalForm,
    CargarCursadaForm,
    CargarNotaFinalForm,
    CargarResultadoFinalForm,
)
from .kpis import build_kpis

# ========================= Helpers =========================

def _make_form(FormClass, request: HttpRequest, data=None, files=None, initial=None):
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

def _role_for(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "Invitado"
    if hasattr(user, "rol") and user.rol:
        return str(user.rol)
    if getattr(user, "is_superuser", False):
        return "Administrador"
    if getattr(user, "is_staff", False):
        return "Staff"
    try:
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

def _fmt_date(d):
    try:
        if isinstance(d, (date, datetime)):
            return d.strftime("%d/%m/%Y")
    except Exception:
        pass
    return "—" if not d else str(d)

def _ord(n):
    try:
        return f"{int(n)}º"
    except Exception:
        return ""

def _cuatri_label(val):
    if val in (None, "", 0, "0"):
        return "A"  # Anual (corto). Cambiá por "Anual" si querés.
    s = str(val).strip()
    if s.lower() in ("anual", "a"):
        return "A"
    m = re.search(r"\d+", s)
    return f"{m.group(0)}º C" if m else s

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
    """
    Intenta qs.order_by(*candidato) usando el primer candidato que exista.
    """
    for cand in candidates:
        try:
            return qs.order_by(*cand)
        except FieldError:
            continue
    return qs.order_by("id")

# =============== Map formularios (panel general) ===============

FORMS_MAP: Dict[str, Any] = {
    "add_est": EstudianteForm,
    "insc_prof": InscripcionProfesoradoForm,
    "insc_esp": InscripcionEspacioForm,
    "insc_final": InscripcionFinalForm,
    "cargar_cursada": CargarCursadaForm,
    "cargar_nota_final": CargarNotaFinalForm,
    "cargar_final_resultado": CargarResultadoFinalForm,
}

ACTION_COPY: Dict[str, List[str]] = {
    "insc_esp": ["inscripcion", "anio_academico"],
    "cargar_cursada": ["inscripcion", "anio_academico"],
    "cargar_nota_final": [],
    "cargar_final_resultado": [],
    "insc_final": [],
}

# ========================= Panel general =========================

@login_required
def panel(request: HttpRequest) -> HttpResponse:
    action = request.GET.get("action") or "section_est"
    FormClass = FORMS_MAP.get(action)
    context: Dict[str, Any] = {"action": action, "FormClass": FormClass}
    context.update(_base_context(request))

    TITLES = {
        "add_est": ("Alta estudiante", ""),
        "insc_prof": ("Inscribir a carrera", ""),
        "insc_esp": ("Inscribir a materia", ""),
        "insc_final": ("Inscribir a final", ""),
        "cargar_cursada": ("Cargar cursada", ""),
        "cargar_nota_final": ("Cargar nota de final", ""),
        "cargar_final_resultado": ("Registrar resultado final", ""),
    }
    if action in TITLES:
        context["action_title"], context["action_subtitle"] = TITLES[action]

    if request.method == "GET" and not request.POST and not request.FILES:
        if FormClass:
            initial = {k: request.GET.get(k) for k in ACTION_COPY.get(action, []) if request.GET.get(k)}
            context["form"] = _make_form(FormClass, request, initial=initial or None)
        return render(request, "panel.html", context)

    if FormClass and request.method == "POST":
        form = _make_form(FormClass, request, request.POST or None, request.FILES or None)
        if hasattr(form, "is_valid") and form.is_valid():
            _ = form.save() if hasattr(form, "save") else None
            messages.success(request, "Guardado correctamente.")
            params = {"action": action, "ok": 1}
            for key in ACTION_COPY.get(action, []):
                val = form.cleaned_data.get(key)
                if hasattr(val, "pk"):
                    params[key] = str(val.pk)
                elif val not in (None, ""):
                    params[key] = str(val)
            return redirect(f"{reverse('panel')}?{urlencode(params)}")
        context["form"] = form
        return render(request, "panel.html", context)

    if FormClass:
        context["form"] = _make_form(FormClass, request)
    return render(request, "panel.html", context)

# =================== Panel de estudiante ===================

def _build_trayectoria_blocks(inscripcion) -> List[dict]:
    """
    Bloques por espacio con:
    - año / cuatr / nombre
    - REG: fecha/cond/nota
    - FIN: fecha/cond/nota/folio/libro
    Sin usar campos 'creado/created'.
    """
    out: List[dict] = []
    if not inscripcion:
        return out

    prof = inscripcion.profesorado
    espacios = (
        EspacioCurricular.objects
        .filter(profesorado=prof)
        .order_by("anio", "cuatrimestre", "nombre")
    )

    fin_fieldnames = {f.name for f in InscripcionFinal._meta.get_fields()}

    for e in espacios:
        # REG
        base_reg = InscripcionEspacio.objects.filter(inscripcion=inscripcion, espacio=e)
        reg_qs = _safe_order(base_reg, ("fecha", "id"), ("id",))
        regs = [{
            "reg_fecha": _fmt_date(getattr(r, "fecha", None)),
            "reg_cond": getattr(r, "estado", None) or getattr(r, "condicion", None) or "—",
            "reg_nota": (getattr(r, "nota", None) or getattr(r, "nota_num", None) or getattr(r, "nota_final", None) or "—"),
        } for r in reg_qs]

        # FIN
        if "inscripcion" in fin_fieldnames:
            base_fin = InscripcionFinal.objects.filter(
                inscripcion__inscripcion=inscripcion,
                inscripcion__espacio=e
            )
        elif "inscripcion_espacio" in fin_fieldnames:
            base_fin = InscripcionFinal.objects.filter(
                inscripcion_espacio__inscripcion=inscripcion,
                inscripcion_espacio__espacio=e
            )
        elif "insc_espacio" in fin_fieldnames:
            base_fin = InscripcionFinal.objects.filter(
                insc_espacio__inscripcion=inscripcion,
                insc_espacio__espacio=e
            )
        else:
            base_fin = InscripcionFinal.objects.none()

        fin_qs = _safe_order(base_fin, ("fecha_examen", "id"), ("fecha", "id"), ("id",))
        fins = []
        for f in fin_qs:
            fecha_fin = getattr(f, "fecha_examen", None) or getattr(f, "fecha", None)
            condicion = getattr(f, "condicion", None) or getattr(f, "estado", None)
            nota_fin = getattr(f, "nota_final", None) or getattr(f, "nota", None) or getattr(f, "nota_num", None)
            fins.append({
                "fin_fecha": _fmt_date(fecha_fin),
                "fin_cond": condicion or "—",
                "fin_nota": nota_fin if nota_fin not in (None, "") else "—",
                "folio": getattr(f, "folio", None) or "—",
                "libro": getattr(f, "libro", None) or "—",
            })

        rows = []
        rows_count = max(len(regs), len(fins), 1)
        for i in range(rows_count):
            r = regs[i] if i < len(regs) else {}
            ff = fins[i] if i < len(fins) else {}
            rows.append({
                "reg_fecha": r.get("reg_fecha", "—"),
                "reg_cond":  r.get("reg_cond", "—"),
                "reg_nota":  r.get("reg_nota", "—"),
                "fin_fecha": ff.get("fin_fecha", "—"),
                "fin_cond":  ff.get("fin_cond", "—"),
                "fin_nota":  ff.get("fin_nota", "—"),
                "folio":     ff.get("folio", "—"),
                "libro":     ff.get("libro", "—"),
            })

        out.append({
            "anio": _ord(getattr(e, "anio", None)) if getattr(e, "anio", None) else "",
            "cuatri": _cuatri_label(getattr(e, "cuatrimestre", None)),
            "espacio": getattr(e, "nombre", str(e)),
            "rows": rows,
        })
    return out

@login_required
def panel_estudiante(request: HttpRequest) -> HttpResponse:
    user = request.user
    can_admin = user.is_staff or user.is_superuser
    active_tab = request.GET.get("tab") or "trayectoria"

    sel_est: Optional[Estudiante] = None
    sel_prof: Optional[Profesorado] = None
    opciones_estudiantes: List[dict] = []
    opciones_profesorados: List[dict] = []

    if can_admin:
        opciones_estudiantes = [
            {"id": e.id, "label": f"{e.apellido}, {e.nombre} ({e.dni})"}
            for e in Estudiante.objects.order_by("apellido", "nombre")
        ]
        opciones_profesorados = [{"id": p.id, "label": p.nombre} for p in Profesorado.objects.order_by("nombre")]
        est_id = request.GET.get("est")
        prof_id = request.GET.get("prof")
        if est_id:
            sel_est = Estudiante.objects.filter(pk=est_id).first()
        if prof_id:
            sel_prof = Profesorado.objects.filter(pk=prof_id).first()
    else:
        sel_est = getattr(user, "estudiante", None)
        if sel_est:
            ep = (EstudianteProfesorado.objects.filter(estudiante=sel_est).select_related("profesorado").first())
            sel_prof = ep.profesorado if ep else None

    insc = None
    if sel_est and sel_prof:
        insc = EstudianteProfesorado.objects.filter(estudiante=sel_est, profesorado=sel_prof).first()

    qs_est_prof = urlencode({"est": sel_est.id, "prof": sel_prof.id}) if (sel_est and sel_prof) else ""

    context = {
        "rol": _role_for(user),
        "puede_elegir": can_admin,
        "opciones_estudiantes": opciones_estudiantes,
        "opciones_profesorados": opciones_profesorados,
        "sel_est": sel_est,
        "sel_prof": sel_prof,
        "active_tab": active_tab,
        "logout_url": reverse("logout"),
        "qs_est_prof": qs_est_prof,
    }

    if active_tab == "trayectoria":
        context["bloques_tray"] = _build_trayectoria_blocks(insc)

    return render(request, "panel_estudiante.html", context)

# =============== Cartón (ventana aparte) ===============

@login_required
def panel_estudiante_carton(request: HttpRequest) -> HttpResponse:
    est_id  = request.GET.get("est")  or request.GET.get("estudiante") or request.GET.get("est_id")
    prof_id = request.GET.get("prof") or request.GET.get("profesorado") or request.GET.get("prof_id")

    estudiante  = Estudiante.objects.filter(pk=est_id).first() if est_id else None
    profesorado = Profesorado.objects.filter(pk=prof_id).first() if prof_id else None

    inscripcion = None
    if estudiante and profesorado:
        inscripcion = (
            EstudianteProfesorado.objects
            .filter(estudiante=estudiante, profesorado=profesorado)
            .order_by("id").first()
        )

    plan = getattr(profesorado, "plan_vigente", None)

    def get(obj, attr, default=""):
        return getattr(obj, attr, default) if obj else default

    bloques: List[dict] = []
    notas_finales: List[float] = []

    if profesorado:
        esp_qs = EspacioCurricular.objects.filter(profesorado=profesorado)
        if hasattr(EspacioCurricular, "plan") and plan:
            esp_qs = esp_qs.filter(plan=plan)
        esp_qs = esp_qs.order_by("anio", "cuatrimestre", "nombre")

        fin_fieldnames = {f.name for f in InscripcionFinal._meta.get_fields()}

        for e in esp_qs:
            # REG: solo regularidades/promos/libres (no EN_CURSO/INSCRIPTO)
            reg_list = []
            if inscripcion:
                reg_qs = InscripcionEspacio.objects.filter(inscripcion=inscripcion, espacio=e)
                reg_qs = (
                    reg_qs.exclude(estado__isnull=True)
                        .exclude(estado__iexact="EN_CURSO")
                        .exclude(estado__iexact="EN CURSO")
                        .exclude(estado__iexact="CURSANDO")
                        .exclude(estado__iexact="INSCRIPTO")
                )
                reg_list = list(_safe_order(reg_qs, ("fecha", "id"), ("id",)))

            # FIN
            if "inscripcion" in fin_fieldnames:
                qs = InscripcionFinal.objects.filter(inscripcion__espacio=e)
                if estudiante:
                    qs = qs.filter(inscripcion__inscripcion__estudiante=estudiante)
                fin_list = list(_safe_order(qs, ("fecha_examen", "id"), ("fecha", "id"), ("id",)))
            elif "inscripcion_espacio" in fin_fieldnames:
                qs = InscripcionFinal.objects.filter(inscripcion_espacio__espacio=e)
                if estudiante:
                    qs = qs.filter(inscripcion_espacio__inscripcion__estudiante=estudiante)
                fin_list = list(_safe_order(qs, ("fecha_examen", "id"), ("fecha", "id"), ("id",)))
            elif "insc_espacio" in fin_fieldnames:
                qs = InscripcionFinal.objects.filter(insc_espacio__espacio=e)
                if estudiante:
                    qs = qs.filter(insc_espacio__inscripcion__estudiante=estudiante)
                fin_list = list(_safe_order(qs, ("fecha_examen", "id"), ("fecha", "id"), ("id",)))
            else:
                fin_list = []

            max_len = max(len(reg_list), len(fin_list), 1)
            rows = []
            for i in range(max_len):
                reg = reg_list[i] if i < len(reg_list) else None
                fin = fin_list[i] if i < len(fin_list) else None

                reg_estado = get(reg, "estado", "")
                reg_nota   = get(reg, "nota", "") or get(reg, "nota_num", "") or get(reg, "nota_final", "")

                fin_fecha  = get(fin, "fecha_examen", "") or get(fin, "fecha", "")
                fin_estado = get(fin, "estado", "") or get(fin, "condicion", "")
                fin_nota   = get(fin, "nota_final", "") or get(fin, "nota", "") or get(fin, "nota_num", "")

                # promedio (finales)
                def _as_num(x):
                    if x in (None, "", "Ausente", "Ausente In", "Ausente Ju"):
                        return None
                    s = str(x).strip()
                    m = re.match(r"^\s*(\d+)", s)
                    if m:
                        try:
                            return float(m.group(1).replace(",", "."))
                        except Exception:
                            return None
                    try:
                        return float(s.replace(",", "."))
                    except Exception:
                        return None

                num = _as_num(fin_nota)
                if num is not None and 0 < num <= 10:
                    notas_finales.append(num)

                rows.append({
                    "reg_fecha": _fmt_date(get(reg, "fecha")),
                    "reg_cond":  reg_estado,
                    "reg_nota":  reg_nota,
                    "fin_fecha": _fmt_date(fin_fecha),
                    "fin_cond":  fin_estado,
                    "fin_nota":  fin_nota,
                    "folio":     get(fin, "folio", ""),
                    "libro":     get(fin, "libro", ""),
                })

            bloques.append({
                "anio":    _ord(getattr(e, "anio", None)),
                "cuatri":  _cuatri_label(getattr(e, "cuatrimestre", None)),
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

# ============================ APIs ============================

@login_required
@require_GET
def get_espacios_por_inscripcion(request: HttpRequest, insc_id: int):
    try:
        insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
    except EstudianteProfesorado.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Inscripción no encontrada"}, status=404)

    # === INICIO: LÓGICA AGREGADA ===
    mode = (request.GET.get("mode") or "").strip().lower()

    # Si es para inscribirse a FINAL y el alumno es condicional => no ofrecer opciones
    if mode in {"final", "finales"} and getattr(insc, "condicion_admin", "") == CondicionAdmin.CONDICIONAL:
        return JsonResponse({
            "ok": True,
            "items": [],
            "cond_opts": [],
            "reason": "Estudiante condicional: no puede inscribirse a finales.",
        })
    # === FIN: LÓGICA AGREGADA ===

    qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado).order_by("anio", "cuatrimestre", "nombre")

    ya_ids = list(InscripcionEspacio.objects.filter(inscripcion=insc).values_list("espacio_id", flat=True))
    if ya_ids:
        qs = qs.exclude(pk__in=ya_ids)

    try:
        from .condiciones import _choices_condicion_para_espacio
        def _cond_opts_para(e):
            return [v for (v, _l) in _choices_condicion_para_espacio(e)]
    except Exception:
        def _cond_opts_para(e):
            return []

    items = [{"id": e.id, "nombre": _espacio_label(e), "cond_opts": _cond_opts_para(e)} for e in qs]
    default = _cond_opts_para(qs.first()) if qs.exists() else []
    return JsonResponse({"ok": True, "items": items, "cond_opts": default})

@login_required
@require_GET
def get_condiciones_por_espacio(request: HttpRequest, espacio_id: int):
    try:
        e = EspacioCurricular.objects.get(pk=espacio_id)
    except EspacioCurricular.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Espacio no encontrado"}, status=404)

    try:
        from .condiciones import _choices_condicion_para_espacio
        choices = _choices_condicion_para_espacio(e)
        data = [{"value": v, "label": l} for (v, l) in choices]
        return JsonResponse(data, safe=False)
    except Exception:
        return JsonResponse([], safe=False)

@login_required
@require_GET
def get_correlatividades(request: HttpRequest, espacio_id: int):
    insc_id = request.GET.get("insc_id")

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
        return JsonResponse({"ok": True, "puede_cursar": ok, "detalles": data})

    reqs = obtener_requisitos_para(espacio)
    data = [{"espacio_id": r.espacio_id, "etiqueta": r.etiqueta, "minimo": r.minimo} for r in reqs]
    return JsonResponse({"ok": True, "detalles": data})

# --- KPIs: Situación Académica ---
def get_situacion_academica(request: HttpRequest, insc_id: int):
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método no permitido"}, status=405)
    insc = get_object_or_404(EstudianteProfesorado, pk=insc_id)
    data = build_kpis(insc)
    return JsonResponse({"ok": True, "kpis": data})