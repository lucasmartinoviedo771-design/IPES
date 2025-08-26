from django.conf import settings

# === Menú (tu build_menu ya lo tenías) ===
from .menu import build_menu, demo  # ajusta el import si lo tenés en otro archivo

# Normalización simple para nombres con/ sin acento
def _norm(s: str) -> str:
    return (
        s.lower()
        .replace("í", "i")
        .replace("á", "a")
        .replace("é", "e")
        .replace("ó", "o")
        .replace("ú", "u")
        .strip()
    )

def _role_from_user(user) -> str:
    if not user.is_authenticated:
        return "Invitado"
    if getattr(user, "is_superuser", False):
        return "Admin"

    group_names = [_norm(g.name) for g in user.groups.all()]
    if "admin" in group_names:
        return "Admin"
    if "secretaria" in group_names or "secretaría" in group_names:
        return "Secretaría"
    if "bedel" in group_names or "bedeles" in group_names:
        return "Bedel"
    if "docente" in group_names:
        return "Docente"
    if "estudiante" in group_names:
        return "Estudiante"

    # por defecto: Estudiante (ajústalo si querés otro default)
    return "Estudiante"

def role_from_request(request) -> str:
    """
    Obtiene el rol lógico para la UI.
    En desarrollo (DEBUG=True) permite override por querystring ?as_role=...
    """
    role = _role_from_user(request.user)
    if settings.DEBUG:
        override = request.GET.get("as_role")
        if override:
            return override
    return role

def menu(request):
    role = role_from_request(request)
    return {
        "UI_ROLE": role,
        "UI_MENU": build_menu(role),
        "UI_RESUMEN": demo["resumen"],
        "UI_VENTANAS": demo["ventanas"],
    }