# academia_core/utils.py
from typing import Any


def get(obj: Any, key: str, default: Any = None) -> Any:
    """
    Versión segura de getattr, que también devuelve el default si el valor es None.
    """
    val = getattr(obj, key, default)
    return default if val is None else val
