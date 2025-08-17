from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from itertools import chain
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from .models import (
    Estudiante,
    EstudianteProfesorado,
    EspacioCurricular,
    InscripcionEspacio,
    InscripcionFinal,
)
from .forms_student import StudentInscripcionEspacioForm, StudentInscripcionFinalForm
from .label_utils import espacio_etiqueta


# ----------------- helpers comunes -----------------

def _role_for(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "Invitado"
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


def _base_ctx_est(request: HttpRequest) -> Dict[str, Any]:
    user = getattr(request, "user", None)
    try:
        inscs = EstudianteProfesorado.objects.filter(estudiante__user=user).select_related("profesorado")
        if not inscs.exists() and user and user.email:
            inscs = EstudianteProfesorado.objects.filter(estudiante__email__iexact=user.email).select_related("profesorado")
    except Exception:
        inscs = EstudianteProfesorado.objects.none()
    profesorados = [i.profesorado for i in inscs]
    return {"rol": _role_for(user), "profesorados": profesorados}


# ----------------- HISTÓRICO (cartón) -----------------

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

def _final_fk_name() -> Optional[str]:
    """Detecta el nombre del FK desde InscripcionFinal hacia InscripcionEspacio."""
    for f in InscripcionFinal._meta.get_fields():
        try:
            if getattr(f, "related_model", None).__name__ == "InscripcionEspacio":
                return f.name
        except Exception:
            pass
    return None

def _inscripciones_del_usuario(request: HttpRequest):
    user = request.user
    est = getattr(user, "estudiante", None)
    if est:
        return EstudianteProfesorado.objects.filter(estudiante=est)
    if user.email:
        return EstudianteProfesorado.objects.filter(estudiante__email__iexact=user.email)
    return EstudianteProfesorado.objects.none()

def _carton_rows(request: HttpRequest) -> List[Dict[str, Any]]:
    """
    Genera filas estilo 'cartón' (similar a tu Apps Script):
    - Se recorre TODO el plan del/los profesorados del alumno (todos los espacios).
    - Para cada espacio se listan eventos 'regularidad' (InscripcionEspacio) y 'final' (InscripcionFinal),
      en filas separadas. Si no hay eventos, se agrega una fila vacía de ese espacio.
    - Orden: anio, cuatrimestre, nombre, fecha.
    """
    inscs = _inscripciones_del_usuario(request)
    if not inscs.exists():
        return []

    # Todos los espacios del/los profesorados del alumno
    espacios = (
        EspacioCurricular.objects
        .filter(profesorado__in=[i.profesorado for i in inscs])
        .order_by("anio", "cuatrimestre", "nombre")
    )

    # Precalcular las cursadas y finales del alumno para cruzar por espacio
    cursadas = (
        InscripcionEspacio.objects
        .filter(inscripcion__in=inscs)
        .select_related("espacio", "inscripcion")
    )
    # finales: localizar FK dinámicamente
    fk_final = _final_fk_name()
    if fk_final:
        finales = (
            InscripcionFinal.objects
            .filter(**{f"{fk_final}__inscripcion__in": inscs})
            .select_related(fk_final)
        )
    else:
        finales = InscripcionFinal.objects.none()

    # Índices por espacio para acceso rápido
    by_esp_cursadas: Dict[int, List[InscripcionEspacio]] = {}
    for c in cursadas:
        by_esp_cursadas.setdefault(c.espacio_id, []).append(c)

    by_esp_finales: Dict[int, List[InscripcionFinal]] = {}
    if fk_final:
        for f in finales:
            ie: InscripcionEspacio = getattr(f, fk_final)
            if ie and ie.espacio_id:
                by_esp_finales.setdefault(ie.espacio_id, []).append(f)

    rows: List[Dict[str, Any]] = []
    for e in espacios:
        anio_txt = _ord(getattr(e, "anio", None))
        cuatri_txt = _cuatri_label(getattr(e, "cuatrimestre", None), getattr(e, "formato", None))

        ev_reg = sorted(by_esp_cursadas.get(e.id, []), key=lambda x: (x.fecha or date.min))
        ev_fin = sorted(by_esp_finales.get(e.id, []), key=lambda x: (getattr(x, "fecha", None) or date.min))

        # Si hay eventos de ambos tipos, los “intercalamos” como en Sheets: una fila por evento.
        eventos: List[Tuple[str, Any]] = [
            *[( "reg", it) for it in ev_reg],
            *[( "fin", it) for it in ev_fin],
        ]
        # orden por fecha dentro del mismo espacio
        def _ev_date(ev):
            kind, obj = ev
            if kind == "reg":
                return obj.fecha or date.min
            # 'fin'
            return getattr(obj, "fecha", None) or date.min

        eventos.sort(key=_ev_date)

        if not eventos:
            # fila “vacía” del espacio
            rows.append({
                "anio": anio_txt,
                "cuatri": cuatri_txt,
                "espacio": e.nombre,
                "reg_fecha": "",
                "reg_cond": "",
                "reg_nota": "",
                "fin_fecha": "",
                "fin_cond": "",
                "fin_nota": "",
                "fin_folio": "",
                "fin_libro": "",
                "fin_id": "",
                "break_after": True,  # ayuda visual para cortar grupos por espacio
            })
            continue

        for idx, (kind, obj) in enumerate(eventos):
            is_reg = (kind == "reg")
            if is_reg:
                reg_fecha = obj.fecha or ""
                reg_cond  = obj.estado or ""
                reg_nota  = ""  # InscripcionEspacio no suele tener nota numérica
                fin_fecha = fin_cond = fin_nota = fin_folio = fin_libro = fin_id = ""
            else:
                reg_fecha = reg_cond = reg_nota = ""
                fin_fecha = getattr(obj, "fecha", "")
                fin_cond  = getattr(obj, "estado", "")
                # nota_final puede llamarse distinto si personalizaste; probamos ambos
                fin_nota  = getattr(obj, "nota_final", "") or getattr(obj, "nota", "")
                fin_folio = getattr(obj, "folio", "")  # si no existe, queda vacío
                fin_libro = getattr(obj, "libro", "")  # si no existe, queda vacío
                fin_id    = getattr(obj, "id", "")

            rows.append({
                "anio": anio_txt if idx == 0 else "",     # sólo en la primera línea del espacio
                "cuatri": cuatri_txt if idx == 0 else "",
                "espacio": e.nombre if idx == 0 else "",
                "reg_fecha": reg_fecha,
                "reg_cond": reg_cond,
                "reg_nota": reg_nota,
                "fin_fecha": fin_fecha,
                "fin_cond": fin_cond,
                "fin_nota": fin_nota,
                "fin_folio": fin_folio,
                "fin_libro": fin_libro,
                "fin_id": fin_id,
                "break_after": (idx == len(eventos) - 1),
            })

    return rows


# ----------------- vista principal panel estudiante -----------------

@login_required
def panel_estudiante(request: HttpRequest) -> HttpResponse:
    """
    Panel solo para estudiantes.
      Acciones:
        tray       -> Trayectoria
        correl     -> Correlatividades (placeholder de consulta)
        sit        -> Situación académica
        horarios   -> Placeholder
        insc_esp   -> Inscribirse a materia (cursada)
        insc_final -> Inscribirse a mesa de final
        hist       -> Histórico (cartón)
    """
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
        est = getattr(request.user, "estudiante", None)
        try:
            if est is None and request.user.email:
                est = Estudiante.objects.filter(email__iexact=request.user.email).first()
        except Exception:
            est = None
        if est:
            inscs = EstudianteProfesorado.objects.filter(estudiante=est)
            posibles = EspacioCurricular.objects.filter(
                profesorado__in=[i.profesorado for i in inscs]
            ).order_by("anio", "cuatrimestre", "nombre")
        else:
            posibles = EspacioCurricular.objects.none()
        ctx["espacios_posibles"] = [(e.id, espacio_etiqueta(e)) for e in posibles]

    elif action == "sit":
        est = getattr(request.user, "estudiante", None)
        try:
            if est is None and request.user.email:
                est = Estudiante.objects.filter(email__iexact=request.user.email).first()
        except Exception:
            est = None
        if est:
            inscs = EstudianteProfesorado.objects.filter(estudiante=est)
            cursadas = InscripcionEspacio.objects.filter(inscripcion__in=inscs).select_related("espacio")
            ctx["total_cursadas"] = cursadas.count()
            ctx["cursadas"] = cursadas
        else:
            ctx["total_cursadas"] = 0
            ctx["cursadas"] = []

    elif action == "hist":
        ctx["carton_rows"] = _carton_rows(request)

    return render(request, "panel_estudiante.html", ctx)
