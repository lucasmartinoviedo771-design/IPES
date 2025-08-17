# academia_core/kpis.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set
from django.utils import timezone

from .models import (
    EstudianteProfesorado,
    EspacioCurricular,
)

# Helpers opcionales: si existen en tu codebase, se usan; si no, se ignoran sin romper.
try:
    from .models import _tiene_regularidad_vigente  # (insc, espacio, fecha) -> bool
except Exception:  # pragma: no cover
    _tiene_regularidad_vigente = None  # type: ignore

try:
    from .models import _tiene_aprobada  # (insc, espacio[, hasta_fecha]) -> bool
except Exception:  # pragma: no cover
    _tiene_aprobada = None  # type: ignore

try:
    from .correlativas import evaluar_correlatividades
except Exception:  # pragma: no cover
    def evaluar_correlatividades(*args, **kwargs):  # type: ignore
        return True, []


def _parse_nota(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        if 0 <= f <= 10:
            return f
    except Exception:
        pass
    s = str(value)
    digits = []
    for ch in s:
        if ch.isdigit():
            digits.append(ch)
        elif digits:
            break
    if digits:
        try:
            f = float(int("".join(digits)))
            if 0 <= f <= 10:
                return f
        except Exception:
            return None
    return None


def _promedio(insc: EstudianteProfesorado) -> Optional[float]:
    # 1) si el modelo guarda un promedio_general, usarlo
    prom = getattr(insc, "promedio_general", None)
    if prom not in (None, ""):
        try:
            return float(prom)
        except Exception:
            pass

    # 2) fallback: intentar reconstruir desde "movimientos" si existe esa relación
    movs = getattr(insc, "movimientos", None)
    if movs is None:
        return None

    notas: List[float] = []
    # Si tu instancia tiene un helper para saber si un movimiento aprueba:
    aprueba_fn = getattr(insc, "_mov_aprueba", None)

    for m in movs.all():
        try:
            ok = True
            if callable(aprueba_fn):
                ok = bool(aprueba_fn(m))
            if not ok:
                continue
            # buscar nota numérica en campos típicos
            nota_val = getattr(m, "nota_num", None)
            if nota_val is None:
                nota_val = getattr(m, "nota_final", None)
            if nota_val is None:
                nota_val = getattr(m, "nota_texto", None)
            n = _parse_nota(nota_val)
            if n is not None:
                notas.append(n)
        except Exception:
            continue

    if not notas:
        return None
    return round(sum(notas) / len(notas), 2)


def _conteos(insc: EstudianteProfesorado) -> Dict[str, int]:
    total_espacios = EspacioCurricular.objects.filter(
        profesorado=insc.profesorado
    ).count()

    # aprobadas: si hay helper, usamos; si no, 0
    aprobadas = 0
    if callable(_tiene_aprobada):
        for esp in EspacioCurricular.objects.filter(profesorado=insc.profesorado).only("id"):
            try:
                if _tiene_aprobada(insc, esp):
                    aprobadas += 1
            except Exception:
                continue

    # promocionadas/libres: intentamos desde "movimientos"
    movs = getattr(insc, "movimientos", None)
    promo_ids: Set[int] = set()
    libre_ids: Set[int] = set()

    if movs is not None:
        for m in movs.all().select_related("espacio"):
            esp_id = getattr(m, "espacio_id", None)
            tipo = getattr(m, "tipo", "")
            cond = getattr(getattr(m, "condicion", None), "codigo", "") or getattr(m, "condicion", "")
            if not esp_id:
                continue
            # Heurística: REG + PROMOCION => promoción
            if str(tipo).upper().startswith("REG") and str(cond).upper().startswith("PROMOCION"):
                promo_ids.add(esp_id)
            # Heurística: REG + LIBRE* => libre
            if str(tipo).upper().startswith("REG") and str(cond).upper().startswith("LIBRE"):
                libre_ids.add(esp_id)

    pendientes = max(total_espacios - aprobadas, 0)

    return {
        "espacios": total_espacios,
        "aprobadas": aprobadas,
        "promocionadas": len(promo_ids),
        "libres": len(libre_ids),
        "pendientes": pendientes,
    }


def _proximas_regularidades_a_vencer(insc: EstudianteProfesorado, ventana_dias: int = 90) -> List[Dict[str, Any]]:
    if not callable(_tiene_regularidad_vigente):
        return []
    hoy = timezone.now().date()
    corte = hoy + timedelta(days=ventana_dias)
    out: List[Dict[str, Any]] = []
    for esp in EspacioCurricular.objects.filter(profesorado=insc.profesorado).only("id", "nombre"):
        try:
            vigente_hoy = _tiene_regularidad_vigente(insc, esp, hoy)
            vigente_corte = _tiene_regularidad_vigente(insc, esp, corte)
        except Exception:
            continue
        if vigente_hoy and not vigente_corte:
            out.append({
                "espacio_id": esp.id,
                "nombre": getattr(esp, "nombre", str(esp)),
                "vence_en_dias_est": ventana_dias,
            })
    return out


def _correlativas_faltantes(insc: EstudianteProfesorado) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for esp in EspacioCurricular.objects.filter(profesorado=insc.profesorado).only("id", "nombre"):
        # si está aprobada, no alertamos
        if callable(_tiene_aprobada):
            try:
                if _tiene_aprobada(insc, esp):
                    continue
            except Exception:
                pass
        ok, detalles = evaluar_correlatividades(insc, esp)
        if not ok:
            motivos = [d.get("motivo") for d in detalles if not d.get("cumplido")]
            out.append({
                "espacio_id": esp.id,
                "nombre": getattr(esp, "nombre", str(esp)),
                "motivos": [m for m in motivos if m],
            })
    return out


def build_kpis(insc: EstudianteProfesorado) -> Dict[str, Any]:
    return {
        "promedio": _promedio(insc),
        "totales": _conteos(insc),
        "reg_proximas_a_vencer": _proximas_regularidades_a_vencer(insc),
        "correlativas_faltantes": _correlativas_faltantes(insc),
    }
