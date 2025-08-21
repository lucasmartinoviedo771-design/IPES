# academia_core/utils.py
from typing import Any
from django.utils import timezone

def get(obj: Any, key: str, default: Any = None) -> Any:
    """
    Versión segura de getattr, que también devuelve el default si el valor es None.
    """
    val = getattr(obj, key, default)
    return default if val is None else val

def coalesce(*args):
    """
    Devuelve el primer valor del listado que no sea None.
    """
    for arg in args:
        if arg is not None:
            return arg
    return None

def year_now() -> int:
    """
    Devuelve el año actual de forma segura.
    """
    return timezone.now().year