# ui/context_processors.py
import unicodedata
from django.conf import settings

# Traemos el generador de menú y los datos demo
try:
    from .menu import build_menu, demo
except Exception:
    # Fallback mínimo si falta ui/menu.py
    def build_menu(role: str):
        return [{"label": "Inicio", "items": [{"label": "Dashboard", "path": "/dashboard", "icon": "speedometer"}]}]
    demo = {
        "resumen": {"estudiantes": 0, "docentes": 0, "espacios": 0, "inscCarrera": 0, "inscMateria": 0},
        "ventanas": {"materia": {"abierto": False, "hasta": ""}, "final": {"abierto": False, "desde": ""}},
    }

# Orden de prioridad de grupos → rol
ROLES_ORDER = ["Admin", "Secretaría", "Bedel", "Docente", "Estudiante"]

def _strip_accents_lower(s: str | None) -> str | None:
    if not s:
        return None
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).strip().lower()
    return s

def _alias_to_canonical(raw: str | None) -> str | None:
    s = _strip_accents_lower(raw)
    if not s:
        return None
    aliases = {
        "admin": "Admin", "administrador": "Admin",
        "secretaria": "Secretaría", "secretario": "Secretaría",
        "bedel": "Bedel", "bedelia": "Bedel", "bedelia/o": "Bedel",
        "docente": "Docente", "profesor": "Docente",
        "estudiante": "Estudiante", "alumno": "Estudiante",
    }
    return aliases.get(s, None)

def role_from_request(request) -> str:
    # 1) Simulador por querystring SOLO en DEBUG
    if settings.DEBUG:
        qs = _alias_to_canonical(request.GET.get("as_role"))
        if qs:
            return qs

    # 2) No autenticado → Estudiante
    if not request.user.is_authenticated:
        return "Estudiante"

    # 3) Grupos del usuario (prioridad)
    group_names = [_alias_to_canonical(n) for n in request.user.groups.values_list("name", flat=True)]
    group_names = [g for g in group_names if g]
    for r in ROLES_ORDER:
        if r in group_names:
            return r

    # 4) Fallback a perfil (si existe)
    profile = getattr(request.user, "userprofile", None)
    if profile:
        pr = _alias_to_canonical(getattr(profile, "rol", None))
        if pr:
            return pr

    # 5) Último recurso
    return "Estudiante"

# === Context processors (compatibilidad con settings.py) ===

def role(request):
    """Devuelve el rol actual en UI_ROLE (nombre histórico mantenido)."""
    return {"UI_ROLE": role_from_request(request)}

def menu(request):
    """Devuelve el menú calculado en UI_MENU (nombre histórico mantenido)."""
    r = role_from_request(request)
    return {"UI_MENU": build_menu(r)}

def ui_globals(request):
    """Opción todo-en-uno; si la usás en settings podés quitar los dos de arriba."""
    r = role_from_request(request)
    return {"UI_ROLE": r, "UI_MENU": build_menu(r), "DEMO": demo}

# Por si en algún template esperaban DEMO como CP separado
def demo_context(request):
    return {"DEMO": demo}