# ui/context_processors.py
from __future__ import annotations

from typing import Optional, Iterable
from django.conf import settings
from django.http import HttpRequest
from .menu import for_role  # generador de secciones del menú

# Soportamos varias claves posibles (compatibilidad con código previo)
POSSIBLE_ROLE_SESSION_KEYS = [
    "ui_current_role",
    "current_role",
    "role",
    "menu_role",
    "user_role",
]

def _first_group_name(user) -> Optional[str]:
    if not getattr(user, "is_authenticated", False):
        return None
    names: Iterable[str] = user.groups.values_list("name", flat=True)
    return next(iter(names), None)

def _role_from_session(request: HttpRequest) -> Optional[str]:
    for key in POSSIBLE_ROLE_SESSION_KEYS:
        val = request.session.get(key)
        if val:
            return str(val)
    return None

def _detect_role(request: HttpRequest) -> Optional[str]:
    """
    Orden:
      1) Cualquiera de las claves de sesión conocidas (switch_role, etc.)
      2) Superusuario -> 'Admin'
      3) Coincidencia por grupos preferidos
      4) Primer grupo del usuario (si existe)
    """
    # 1) Sesión
    role = _role_from_session(request)
    if role:
        return role

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None

    # 2) Superusuario
    if user.is_superuser:
        role = "Admin"
    else:
        # 3) Grupos preferidos
        preferred = ["Bedel", "Secretaría", "Secretaria", "Docente", "Estudiante", "Admin"]
        user_groups = set(user.groups.values_list("name", flat=True))
        role = next((g for g in preferred if g in user_groups), None)
        # 4) Primer grupo si no coincidió ninguno
        if role is None:
            role = _first_group_name(user)

    # Guardamos también en una de nuestras claves para futuras vistas
    request.session["ui_current_role"] = role
    return role

def role_from_request(request: HttpRequest) -> Optional[str]:
    return _detect_role(request)

def menu(request: HttpRequest) -> dict:
    role = role_from_request(request)
    sections = for_role(role)
    return {
        "menu_sections": sections,
        # nombres que pueden usar tus plantillas
        "role": role,
        "rol": role,
        "menu_role": role,
    }

def ui_globals(request: HttpRequest) -> dict:
    role = role_from_request(request)
    return {
        "DEBUG": getattr(settings, "DEBUG", False),
        "APP_VERSION": getattr(settings, "APP_VERSION", "v1"),
        "role": role,
        "rol": role,
    }