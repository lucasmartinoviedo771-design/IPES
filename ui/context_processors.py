# ui/context_processors.py
from django.urls import reverse, NoReverseMatch
from django.templatetags.static import static
from django.conf import settings
from .menu import for_role

def _resolve_menu_paths(items):
    """Convierte url_name -> path y resuelve recursivamente."""
    for it in items:
        url_name = it.pop("url_name", None)
        if url_name and "path" not in it:
            try:
                it["path"] = reverse(url_name)
            except NoReverseMatch:
                it["path"] = "#"

        # compatibilidad: algunos templates esperan 'url'
        if "url" not in it and "path" in it:
            it["url"] = it["path"]

        if isinstance(it.get("children"), list):
            _resolve_menu_paths(it["children"])

def menu(request):
    # Tomamos el rol desde sesión (si lo usás) o desde el user si lo tenés mapeado ahí
    role = (request.session.get("rol_actual")
            or getattr(getattr(request, "user", None), "rol", None))

    # Estructura de menú según el rol
    sections = for_role(role)

    # Resolver url_name -> path para cada item del menú
    def resolve(node):
        if node.get("url_name") and not node.get("path"):
            try:
                node["path"] = reverse(node["url_name"])
            except Exception:
                node["path"] = "#"
        for child in node.get("children", []):
            resolve(child)
        return node

    return {"menu_sections": [resolve(s.copy()) for s in sections]}

def role_from_request(request):
    """
    Asegura una variable 'active_role' en el contexto (y en sesión) para los templates.
    Si no está seteado en sesión, intenta inferirlo por grupos del usuario.
    """
    role = request.session.get("active_role")

    if not role and request.user.is_authenticated:
        # Inferir por grupos (fallback simple)
        gnames = {g.name.lower() for g in request.user.groups.all()}
        if "bedel" in gnames:
            role = "BEDEL"
        elif "secretaría" in gnames or "secretaria" in gnames:
            role = "SECRETARIA"
        elif "admin" in gnames or "administrador" in gnames:
            role = "ADMIN"
        elif "docente" in gnames:
            role = "DOCENTE"
        elif "estudiante" in gnames or "alumno" in gnames:
            role = "ESTUDIANTE"

    # persistir para siguientes requests
    if role:
        request.session["active_role"] = role

    return {
        "active_role": role,
        "role": role,  # por compatibilidad con templates viejos
    }

def ui_globals(request):
    """
    Variables globales simples para las plantillas.
    Mantenelo minimal: solo cosas seguras/estáticas.
    """
    return {
        "APP_NAME": "IPES",
        "APP_BRAND": "IPES",
        "DEBUG": settings.DEBUG,
    }
