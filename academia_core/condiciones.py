# academia_core/condiciones.py
# Fuente única de verdades para "Condición" por formato de espacio curricular.

from typing import List, Tuple

# Listas de condiciones por formato
COND_ASIGNATURA: List[Tuple[str, str]] = [
    ("REGULAR", "Regular"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("DESAPROBADO_PARCIAL", "Desaprobado Parcial"),
    ("LIBRE_INASISTENCIAS", "Libre por inasistencias"),
    ("LIBRE_ABANDONO_TEMPRANO", "Libre por abandono temprano"),
]

COND_MODULO: List[Tuple[str, str]] = [
    ("PROMOCION", "Promoción"),
    ("REGULAR", "Regular"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("DESAPROBADO_PARCIAL", "Desaprobado Parcial"),
    ("LIBRE_INASISTENCIAS", "Libre por inasistencias"),
    ("LIBRE_ABANDONO_TEMPRANO", "Libre por abandono temprano"),
]

COND_TALLER: List[Tuple[str, str]] = [
    ("APROBADO", "Aprobado"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("LIBRE_INASISTENCIAS", "Libre por inasistencias"),
    ("LIBRE_ABANDONO_TEMPRANO", "Libre por abandono temprano"),
]

COND_PRACTICAS: List[Tuple[str, str]] = [
    ("APROBADO", "Aprobado"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("DESAPROBADO_PARCIAL", "Desaprobado Parcial"),
    ("LIBRE_INASISTENCIAS", "Libre por inasistencias"),
    ("LIBRE_ABANDONO_TEMPRANO", "Libre por abandono temprano"),
]


def _normalizar_formato(valor: str | None) -> str:
    """Normaliza el string de formato a: asignatura|modulo|taller|practicas."""
    s = (valor or "").strip().lower()
    if s.startswith("asignatura"):
        return "asignatura"
    if s.startswith("módulo") or s.startswith("modulo"):
        return "modulo"
    if "taller" in s or "seminario" in s or "laboratorio" in s:
        return "taller"
    if "práctica" in s or "practica" in s or "prácticas" in s or "practicas" in s:
        return "practicas"
    return "asignatura"


def _choices_condicion_para_espacio(espacio) -> List[Tuple[str, str]]:
    """Devuelve choices (value, label) según el formato del espacio."""
    fmt = _normalizar_formato(getattr(espacio, "formato", None))
    if fmt == "asignatura":
        choices = COND_ASIGNATURA
    elif fmt == "modulo":
        choices = COND_MODULO
    elif fmt == "taller":
        choices = COND_TALLER
    elif fmt == "practicas":
        choices = COND_PRACTICAS
    else:
        choices = COND_ASIGNATURA
    # Copia defensiva (evita aliasing de listas)
    return [(v, l) for (v, l) in choices]
