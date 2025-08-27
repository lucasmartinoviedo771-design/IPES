# ui/context_processors.py
from django.templatetags.static import static
from .auth_views import resolve_role
from .menu import for_role


def role_from_request(request):
    print("DEBUG: Ejecutando role_from_request.")
    role = request.session.get("active_role")
    print(f"DEBUG: Rol recuperado de sesión: {role}")
    if role:
        print(f"DEBUG: Retornando rol de sesión: {role}")
        return {"active_role": role}
    if request.user.is_authenticated:
        print("DEBUG: Usuario autenticado, resolviendo rol...")
        role = resolve_role(request.user)
        request.session["active_role"] = role
        print(f"DEBUG: Rol resuelto y establecido en sesión: {role}")
        return {"active_role": role}
    print("DEBUG: Usuario no autenticado o rol no encontrado.")
    return {"active_role": None}


def menu(request):
    """
    Construye el menú según el rol activo y lo expone como:
      - menu (alias)
      - menu_sections (compat para templates que usen ese nombre)
    """
    role = request.session.get("active_role")
    if not role and request.user.is_authenticated:
        role = resolve_role(request.user)
        request.session["active_role"] = role
    sections = for_role(role or "Estudiante")
    return {"menu": sections, "menu_sections": sections}


def ui_globals(request):
    """
    Variables “globales” del UI disponibles en todos los templates.
    Si no usás alguna, igual es inocuo mantenerlo.
    """
    return {
        "APP_NAME": "IPES Paulo Freire",
        "APP_VERSION": "v1",
        "BRAND_LOGO": static("ui/img/logo-ipes.svg"),
        "SEARCH_PLACEHOLDER": "Buscar... (decorativo)",
    }
