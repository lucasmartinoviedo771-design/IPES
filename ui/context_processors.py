# ui/context_processors.py
from __future__ import annotations

from typing import Any, Dict, List

from django.conf import settings
from django.urls import reverse
from django.http import HttpRequest

# importa el generador de secciones de menú
try:
    from .menu import for_role as menu_for_role  # retorna las secciones según el rol
except Exception:
    menu_for_role = None


def role_from_request(request: HttpRequest) -> str:
    """
    Obtiene el rol 'lógico' para construir el menú.
    Ajustá estas heurísticas a tu proyecto si fuese necesario.
    """
    # 1) Si la vista setea algo en request (u otro middleware)
    role = getattr(request, "ui_role", None)

    # 2) Si el usuario tiene un atributo de rol
    if not role and hasattr(request.user, "rol"):
        role = getattr(request.user, "rol")

    # 3) Si guardás el rol activo en sesión
    if not role:
        role = request.session.get("rol_activo")

    # 4) Fallback por defecto
    return (role or "bedel").lower()


def _materialize_urls(sections: List[Dict[str, Any]]) -> None:
    """
    Completa cada item del menú con su href.
    - Si viene 'path', lo respeta.
    - Si viene 'urlname', hace reverse() para obtener el path.
    """
    for sec in sections or []:
        for it in sec.get("items", []):
            if "urlname" in it and not it.get("path"):
                try:
                    it["path"] = reverse(it["urlname"])
                except Exception:
                    # si falla el reverse, que no reviente el render del menú
                    it["path"] = it["urlname"]


def menu(request: HttpRequest) -> Dict[str, Any]:
    """
    Expone en el contexto:
      - menu_sections: lista de secciones con sus items e hrefs
      - menu_active: título del item 'activo'
    """
    role = role_from_request(request)

    sections: List[Dict[str, Any]] = []
    if callable(menu_for_role):
        try:
            sections = menu_for_role(role) or []
        except Exception:
            sections = []
    else:
        sections = []

    # completa paths usando reverse si hay 'urlname'
    _materialize_urls(sections)

    # marca activo por path actual
    current = request.path or ""
    active_title = ""
    for sec in sections:
        for it in sec.get("items", []):
            href = it.get("path", "") or ""
            it["active"] = current.startswith(href) and href != "/"
            if it["active"]:
                active_title = it.get("title", "")

    return {
        "menu_sections": sections,
        "menu_active": active_title,
    }


def ui_globals(request: HttpRequest) -> Dict[str, Any]:
    """
    Variables sueltas usadas por la base (header, buscador, etc.).
    """
    return {
        "DEBUG": settings.DEBUG,
        # Dejá lo que ya uses en tu base.html
        "SEARCH_DECORATIVE": "Buscar... (decorativo)",
    }
