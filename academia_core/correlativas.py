# academia_core/correlativas.py
# Utilidades para evaluar correlatividades (server-side) en InscripcionEspacio.

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Dict, Any

from django.apps import apps
from django.conf import settings
from django.db.models import Q

# Estados "fuerza" para comparar mínimos
# 3 = máximo (PROMOCION/APROBADO), 2 = REGULAR, 1 = desaprobados, 0 = libres
RANK_ESTADO: Dict[str, int] = {
    "PROMOCION": 3,
    "APROBADO": 3,
    "REGULAR": 2,
    "DESAPROBADO_TP": 1,
    "DESAPROBADO_PARCIAL": 1,
    "LIBRE_INASISTENCIAS": 0,
    "LIBRE_ABANDONO_TEMPRANO": 0,
}


def _rank(estado: Optional[str]) -> int:
    if not estado:
        return -1
    return RANK_ESTADO.get(estado.upper(), -1)


@dataclass(frozen=True)
class Requisito:
    """Un requisito para cursar/rendir.
    - espacio_id: id del espacio requerido
    - etiqueta: nombre legible del espacio requerido
    - tipo: 'CURSAR' o 'RENDIR_FINAL' (por ahora usamos 'CURSAR')
    - minimo: 'APROBADO' | 'PROMOCION' | 'REGULAR'
    """

    espacio_id: int
    etiqueta: str
    tipo: str = "CURSAR"
    minimo: str = "REGULAR"


def _get_model(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None


def _requisitos_desde_modelo(espacio) -> List[Requisito]:
    """Intenta leer requisitos desde un modelo Correlatividad si existe.
    Supuesto de campos (flexible): espacio_objetivo, espacio_requerido, tipo, minimo
    """
    Model = _get_model("academia_core", "Correlatividad")
    if Model is None:
        return []
    # Campos tolerantes
    fields = {f.name for f in Model._meta.fields}
    target_fk = (
        "espacio_objetivo"
        if "espacio_objetivo" in fields
        else "espacio" if "espacio" in fields else None
    )
    req_fk = "espacio_requerido" if "espacio_requerido" in fields else None
    tipo_f = "tipo" if "tipo" in fields else None
    min_f = "minimo" if "minimo" in fields else None
    if not target_fk or not req_fk:
        return []
    qs = Model.objects.filter(**{target_fk: espacio})
    out: List[Requisito] = []
    for row in qs.select_related(req_fk):
        req = getattr(row, req_fk, None)
        if not req:
            continue
        tipo = getattr(row, tipo_f, "CURSAR") if tipo_f else "CURSAR"
        minimo = (getattr(row, min_f, "REGULAR") if min_f else "REGULAR") or "REGULAR"
        out.append(
            Requisito(
                espacio_id=req.id,
                etiqueta=getattr(req, "nombre", str(req)),
                tipo=tipo,
                minimo=minimo,
            )
        )
    return out


# Fallback: mapa estático (editable).
# Podés completar este dict si aún no tenés el modelo Correlatividad.
# Formato: { espacio_objetivo_id: [ (espacio_requerido_id, "Etiqueta", "CURSAR", "REGULAR") ] }
MAPA_REQUISITOS: Dict[int, List[Tuple[int, str, str, str]]] = {
    # ejemplo: 11: [(10, "Pedagogía", "CURSAR", "REGULAR")],
}


def _requisitos_desde_mapa(espacio) -> List[Requisito]:
    arr = MAPA_REQUISITOS.get(getattr(espacio, "id", None), [])
    return [
        Requisito(eid, etiqueta, tipo, minimo) for (eid, etiqueta, tipo, minimo) in arr
    ]


def obtener_requisitos_para(espacio) -> List[Requisito]:
    reqs = _requisitos_desde_modelo(espacio)
    if reqs:
        return reqs
    return _requisitos_desde_mapa(espacio)


def _buscar_cursadas_de(inscripcion, espacio_ids: Iterable[int]):
    InscripcionEspacio = _get_model("academia_core", "InscripcionEspacio")
    if InscripcionEspacio is None:
        return []
    return list(
        InscripcionEspacio.objects.filter(
            Q(inscripcion=inscripcion) & Q(espacio_id__in=list(espacio_ids))
        ).values("espacio_id", "estado")
    )


def evaluar_correlatividades(inscripcion, espacio) -> Tuple[bool, List[Dict[str, Any]]]:
    """Evalúa si inscripcion puede cursar 'espacio'.
    Devuelve (ok, detalles). 'detalles' es una lista de dicts con:
      - 'requisito': Requisito
      - 'cumplido': bool
      - 'estado_encontrado': str | None
      - 'motivo': str (si no cumple)
    """
    reqs = obtener_requisitos_para(espacio)
    if not reqs:
        return True, []  # no hay requisitos

    target_ids = [r.espacio_id for r in reqs]
    cursadas = _buscar_cursadas_de(inscripcion, target_ids)
    estado_por_espacio: Dict[int, Optional[str]] = {
        row["espacio_id"]: row["estado"] for row in cursadas
    }

    detalles: List[Dict[str, Any]] = []
    ok_global = True

    for r in reqs:
        estado = estado_por_espacio.get(r.espacio_id)
        requerido = r.minimo.upper()
        minimo_rank = _rank("APROBADO" if requerido == "PROMOCION" else requerido)
        actual_rank = _rank(estado)
        cumple = actual_rank >= minimo_rank
        if not cumple:
            ok_global = False
        motivo = (
            ""
            if cumple
            else (
                f"Requiere {requerido} en «{r.etiqueta}»"
                + (f" (actual: {estado})" if estado else " (sin cursada previa)")
            )
        )
        detalles.append(
            {
                "requisito": r,
                "cumplido": cumple,
                "estado_encontrado": estado,
                "motivo": motivo,
            }
        )

    return ok_global, detalles
