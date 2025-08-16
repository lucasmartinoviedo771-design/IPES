# academia_core/condiciones.py

from __future__ import annotations

from .models import EspacioCurricular

# Listas de opciones de "Condición" por formato
COND_ASIGNATURA = [
    ("REGULAR",        "Regular"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("DESAPROBADO_PA", "Desaprobado Parcial"),
    ("LIBRE_I",        "Libre por inasistencias"),
    ("LIBRE_AT",       "Libre por abandono temprano"),
]
COND_MODULO = [
    ("PROMOCION",      "Promoción"),
    ("REGULAR",        "Regular"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("DESAPROBADO_PA", "Desaprobado Parcial"),
    ("LIBRE_I",        "Libre por inasistencias"),
    ("LIBRE_AT",       "Libre por abandono temprano"),
]
COND_TALLER = [
    ("APROBADO",       "Aprobado"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("LIBRE_I",        "Libre por inasistencias"),
    ("LIBRE_AT",       "Libre por abandono temprano"),
]
COND_PRACTICAS = [
    ("APROBADO",       "Aprobado"),
    ("DESAPROBADO_TP", "Desaprobado TP"),
    ("DESAPROBADO_PA", "Desaprobado Parcial"),
    ("LIBRE_I",        "Libre por inasistencias"),
    ("LIBRE_AT",       "Libre por abandono temprano"),
]

def _normalizar_formato(raw: str | None) -> str:
    """Devuelve 'asignatura' | 'modulo' | 'taller' | 'practicas'."""
    if not raw:
        return ""
    t = str(raw).strip().lower()
    if "asig" in t:
        return "asignatura"
    if "mód" in t or "mod" in t:
        return "modulo"
    if "taller" in t or "semin" in t or "lab" in t:
        return "taller"
    if "práct" in t or "pract" in t:
        return "practicas"
    return "asignatura"

def _choices_condicion_para_espacio(espacio: EspacioCurricular | None):
    if not espacio:
        return COND_ASIGNATURA
    clave = _normalizar_formato(getattr(espacio, "formato", None))
    if clave == "modulo":
        return COND_MODULO
    if clave == "taller":
        return COND_TALLER
    if clave == "practicas":
        return COND_PRACTICAS
    return COND_ASIGNATURA
