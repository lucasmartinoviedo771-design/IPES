from __future__ import annotations
from typing import Optional, Tuple, Set, Dict, Any, List
from django.apps import apps
from django.db.models import Q, Model
from academia_core.models import Correlatividad, EspacioCurricular


# ---------- utilidades de introspección ----------
def _first_model(candidates: List[str]) -> Optional[Model]:
    for name in candidates:
        try:
            return apps.get_model("academia_core", name)
        except Exception:
            continue
    return None


def _fk_name_to(model, related_model_cls) -> Optional[str]:
    for f in model._meta.get_fields():
        if (
            getattr(f, "is_relation", False)
            and getattr(f, "many_to_one", False)
            and f.related_model is related_model_cls
        ):
            return f.name  # ej. "estudiante", "espacio", "plan"
    return None


def _has_field(model, *names) -> Optional[str]:
    fields = {f.name for f in model._meta.get_fields()}
    for n in names:
        if n in fields:
            return n
    return None


# ---------- detección de modelos frecuentes ----------
Estudiante = apps.get_model("academia_core", "Estudiante")
PlanEstudios = apps.get_model("academia_core", "PlanEstudios")

# ResultadoFinal / ActaFinal / Aprobacion
ResultadoFinal = _first_model(
    ["ResultadoFinal", "ActaFinal", "Aprobacion", "CalificacionFinal"]
)
# Regularidad de cursada
Regularidad = _first_model(["Regularidad", "Cursada", "CondicionCursada"])
# Inscripción a cursada (estudiante + espacio [+ ciclo])
InscripcionEspacio = _first_model(
    ["InscripcionEspacio", "InscripcionCursada", "InscripcionMateria"]
)
# Inscripción a final (opcional)
InscripcionFinal = _first_model(["InscripcionFinal", "MesaInscripcion"])


# ---------- estado académico sets ----------
def estado_sets_para_estudiante(
    estudiante_id: int, plan_id: int, ciclo: Optional[int] = None
) -> Tuple[Set[int], Set[int], Set[int], Set[int]]:
    """aprobadas_ids, regularizadas_ids (incluye aprobadas), inscriptas_cursada_ids, inscriptas_final_ids"""
    aprobadas_ids: Set[int] = set()
    regular_ids: Set[int] = set()
    insc_cursada_ids: Set[int] = set()
    insc_final_ids: Set[int] = set()

    # Aprobadas (final/promoción)
    if ResultadoFinal:
        fk_est = _fk_name_to(ResultadoFinal, Estudiante)
        fk_esp = _fk_name_to(ResultadoFinal, EspacioCurricular)
        fk_plan = _fk_name_to(ResultadoFinal, PlanEstudios) or _has_field(
            ResultadoFinal, "plan", "plan_id"
        )
        if fk_est and fk_esp:
            qs = ResultadoFinal.objects.filter(**{f"{fk_est}_id": estudiante_id})
            if fk_plan:
                qs = qs.filter(
                    **{
                        (
                            f"{fk_plan}_id" if not fk_plan.endswith("_id") else fk_plan
                        ): plan_id
                    }
                )
            # criterios de aprobado
            f_estado = _has_field(
                ResultadoFinal, "estado", "situacion", "condicion", "resultado"
            )
            f_aprob = _has_field(ResultadoFinal, "aprobado", "is_aprobado", "ok")
            f_nota = _has_field(ResultadoFinal, "nota", "calificacion", "puntaje")
            if f_aprob:
                qs = qs.filter(**{f_aprob: True})
            elif f_estado:
                qs = qs.filter(**{f"{f_estado}__in": ["APROBADO", "PROMOCIONADO"]})
            elif f_nota:
                qs = qs.filter(**{f"{f_nota}__gte": 4})
            aprobadas_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    # Regularizadas (incluye aprobadas)
    if Regularidad:
        fk_est = _fk_name_to(Regularidad, Estudiante)
        fk_esp = _fk_name_to(Regularidad, EspacioCurricular)
        fk_plan = _fk_name_to(Regularidad, PlanEstudios) or _has_field(
            Regularidad, "plan", "plan_id"
        )
        if fk_est and fk_esp:
            qs = Regularidad.objects.filter(**{f"{fk_est}_id": estudiante_id})
            if fk_plan:
                qs = qs.filter(
                    **{
                        (
                            f"{fk_plan}_id" if not fk_plan.endswith("_id") else fk_plan
                        ): plan_id
                    }
                )
            f_estado = _has_field(Regularidad, "estado", "situacion", "condicion")
            f_reg = _has_field(Regularidad, "regular", "es_regular", "is_regular")
            if f_reg:
                qs = qs.filter(**{f_reg: True})
            elif f_estado:
                qs = qs.filter(
                    **{f"{f_estado}__in": ["REGULAR", "PROMOCIONADO", "APROBADO"]}
                )
            regular_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))
    regular_ids |= aprobadas_ids

    # Ya inscripto a cursada
    if InscripcionEspacio:
        fk_est = _fk_name_to(InscripcionEspacio, Estudiante)
        fk_esp = _fk_name_to(InscripcionEspacio, EspacioCurricular)
        fk_plan = _fk_name_to(InscripcionEspacio, PlanEstudios) or _has_field(
            InscripcionEspacio, "plan", "plan_id"
        )
        f_ciclo = _has_field(InscripcionEspacio, "ciclo", "anio", "anio_lectivo")
        if fk_est and fk_esp:
            qs = InscripcionEspacio.objects.filter(**{f"{fk_est}_id": estudiante_id})
            if fk_plan:
                qs = qs.filter(
                    **{
                        (
                            f"{fk_plan}_id" if not fk_plan.endswith("_id") else fk_plan
                        ): plan_id
                    }
                )
            if ciclo and f_ciclo:
                qs = qs.filter(**{f_ciclo: ciclo})
            insc_cursada_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    # Ya inscripto a final
    if InscripcionFinal:
        fk_est = _fk_name_to(InscripcionFinal, Estudiante)
        fk_esp = _fk_name_to(InscripcionFinal, EspacioCurricular)
        fk_plan = _fk_name_to(InscripcionFinal, PlanEstudios) or _has_field(
            InscripcionFinal, "plan", "plan_id"
        )
        if fk_est and fk_esp:
            qs = InscripcionFinal.objects.filter(**{f"{fk_est}_id": estudiante_id})
            if fk_plan:
                qs = qs.filter(
                    **{
                        (
                            f"{fk_plan}_id" if not fk_plan.endswith("_id") else fk_plan
                        ): plan_id
                    }
                )
            insc_final_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    return aprobadas_ids, regular_ids, insc_cursada_ids, insc_final_ids


# ---------- correlativas ----------
def correlativas_para(espacio_id: int, plan_id: int, para: str):
    para = (para or "PARA_CURSAR").upper()
    qs = Correlatividad.objects.filter(plan_id=plan_id, espacio_id=espacio_id)
    if para == "PARA_CURSAR":
        return qs.filter(Q(tipo__iexact="PARA_CURSAR") | Q(tipo__isnull=True))
    return qs.filter(tipo__iexact="PARA_RENDIR")


def _cumple_correlatividad(
    c: Correlatividad, aprob: Set[int], regs: Set[int], plan_id: int
) -> bool:
    reqtxt = (c.requisito or "").upper()
    objetivo = aprob if reqtxt.startswith("APROB") else regs

    if c.requiere_espacio_id:
        return c.requiere_espacio_id in objetivo

    if c.requiere_todos_hasta_anio:
        hasta = int(c.requiere_todos_hasta_anio)
        ids_hasta = set(
            EspacioCurricular.objects.filter(
                plan_id=plan_id, anio__lte=hasta
            ).values_list("id", flat=True)
        )
        return ids_hasta.issubset(objetivo)

    return True


def habilitado(
    estudiante_id: int,
    plan_id: int,
    espacio: EspacioCurricular,
    para: str = "PARA_CURSAR",
    ciclo: Optional[int] = None,
) -> Tuple[bool, Any]:
    aprob, regs, insc_curs, insc_final = estado_sets_para_estudiante(
        estudiante_id, plan_id, ciclo
    )

    # Vetos generales
    if para == "PARA_CURSAR" and espacio.id in insc_curs:
        return False, "ya_inscripto"
    if para == "PARA_CURSAR" and espacio.id in regs:
        return False, "ya_regular"
    if espacio.id in aprob:
        return False, "ya_aprobado"
    if para == "PARA_RENDIR" and espacio.id in insc_final:
        return False, "ya_inscripto_final"

    # Correlativas
    faltantes = []
    for c in correlativas_para(espacio.id, plan_id, para):
        if not _cumple_correlatividad(c, aprob, regs, plan_id):
            if c.requiere_espacio_id:
                faltantes.append(
                    {
                        "tipo": (c.tipo or para).upper(),
                        "requisito": (c.requisito or "").upper(),
                        "requiere_espacio_id": c.requiere_espacio_id,
                    }
                )
            elif c.requiere_todos_hasta_anio:
                faltantes.append(
                    {
                        "tipo": (c.tipo or para).upper(),
                        "requisito": (c.requisito or "").upper(),
                        "requiere_todos_hasta_anio": int(c.requiere_todos_hasta_anio),
                    }
                )
    if faltantes:
        return False, {"motivo": "falta_correlativas", "faltantes": faltantes}
    return True, None
