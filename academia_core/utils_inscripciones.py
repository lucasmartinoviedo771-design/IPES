from typing import Iterable
from django.db.models import Q
from academia_core.models import (
    EspacioCurricular,
    EstudianteProfesorado,
    InscripcionEspacio,
    InscripcionFinal,
    Correlatividad,
)


def _tiene_regularizada(
    est_prof: EstudianteProfesorado, espacio: EspacioCurricular
) -> bool:
    # Regular si tiene una InscripcionEspacio previa con estado EN_CURSO o REGULAR (ajusta según tu flujo)
    return InscripcionEspacio.objects.filter(
        inscripcion=est_prof,
        espacio=espacio,
        estado__in=[
            InscripcionEspacio.Estado.EN_CURSO
        ],  # si tu flujo usa "REGULAR", agregalo aquí
    ).exists()


def _tiene_aprobada(
    est_prof: EstudianteProfesorado, espacio: EspacioCurricular
) -> bool:
    # Aprobada si tiene final con nota aprobada (ajusta la condición de nota)
    return InscripcionFinal.objects.filter(
        inscripcion__estudiante=est_prof.estudiante,
        espacio=espacio,
        nota_final__isnull=False,
    ).exists()


def _cumple_correlativas(
    est_prof: EstudianteProfesorado, destino: EspacioCurricular
) -> bool:
    reqs = Correlatividad.objects.filter(destino=destino)
    if not reqs.exists():
        return True

    for req in reqs:
        origen = req.origen  # ajusta si tu campo se llama distinto
        tipo = getattr(
            req, "tipo", "APROBADA"
        )  # por defecto exigimos aprobada si no hay campo

        if tipo == "REGULAR":
            if not (
                _tiene_regularizada(est_prof, origen)
                or _tiene_aprobada(est_prof, origen)
            ):
                return False
        else:  # "APROBADA"
            if not _tiene_aprobada(est_prof, origen):
                return False

    return True


def espacios_habilitados_para(
    est_prof: EstudianteProfesorado,
) -> Iterable[EspacioCurricular]:
    base = EspacioCurricular.objects.filter(profesorado=est_prof.profesorado)
    ids = []
    for esp in base:
        if _cumple_correlativas(est_prof, esp):
            ids.append(esp.id)
    return base.filter(id__in=ids)
