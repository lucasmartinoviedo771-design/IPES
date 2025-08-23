from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import redirect

from .models import (
    Estudiante, Profesorado,
    EstudianteProfesorado, EspacioCurricular,
)

def _role_for(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "Invitado"
    if getattr(user, "is_superuser", False):
        return "Admin"
    if getattr(user, "is_staff", False):
        return "Secretaría"
    try:
        if hasattr(user, "rol") and user.rol:
            return str(user.rol)
        if user.groups.filter(name__iexact="Docente").exists():
            return "Docente"
        if user.groups.filter(name__iexact="Estudiante").exists():
            return "Estudiante"
    except Exception:
        pass
    return "Usuario"

def _base_context(request: HttpRequest):
    user = getattr(request, "user", None)
    can_admin = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    try:
        profesorados = list(Profesorado.objects.all().order_by("nombre"))
    except Exception:
        profesorados = []
    return {"rol": _role_for(user), "can_admin": can_admin, "profesorados": profesorados}

@login_required
def panel(request: HttpRequest) -> HttpResponse:
    """
    Panel unificado (Admin/Secretaría | Estudiante | Docente).
    """
    role = _role_for(request.user)

    # =================== Admin / Secretaría ===================
    if role in ["Admin", "Secretaría"]:
        ctx = _base_context(request)

        # leer 'action' (por defecto, estudiantes)
        action = request.GET.get("action", "section_est")
        ctx["action"] = action
        ctx["form"] = None
        ctx["action_title"] = "Inicio"
        ctx["action_subtitle"] = "Bienvenido al panel de gestión."

        # --- ALTA DE ESTUDIANTE ---
        if action == "add_est":
            ctx["action_title"] = "Nuevo estudiante"
            ctx["form"] = True  # solo aquí se usa el bloque {% elif form %} del template

        # --- INSCRIPCIÓN A CARRERA (alias insc_carrera / insc_prof) ---
        elif action in ("insc_carrera", "insc_prof"):
            ctx["action_title"] = "Inscripción a carrera"

            try:
                ctx["estudiantes"] = Estudiante.objects.filter(activo=True).order_by("apellido", "nombre")
            except Exception:
                ctx["estudiantes"] = []

            # Profesorados activos (campo 'activa' o 'activo', según tu modelo)
            try:
                ctx["profesorados"] = list(Profesorado.objects.filter(activa=True).values("id", "nombre", "tipo"))
                if not ctx["profesorados"]:
                    # fallback por si el boolean se llama 'activo'
                    ctx["profesorados"] = list(Profesorado.objects.filter(activo=True).values("id", "nombre", "tipo"))
            except Exception:
                ctx["profesorados"] = []

            # Cohortes 2010..año actual (desc)
            anio_actual = date.today().year
            ctx["cohortes"] = list(range(2010, anio_actual + 1))[::-1]

            # Requisitos base para el template
            ctx["base_checks"] = [
                ("dni_legalizado", "DNI legalizado"),
                ("certificado_medico", "Certificado médico"),
                ("fotocarnet", "Foto carnet"),
                ("folio_oficio", "Folio oficio"),
            ]

        # --- INSCRIPCIÓN A MATERIA (cursada) ---
        elif action == "insc_esp":
            ctx["action_title"] = "Inscribir a Espacio Curricular"
            ctx["action_subtitle"] = "Inscribe a un estudiante en una materia para el ciclo académico actual."
            # si más adelante querés un form Django, preparalo y ponelo en ctx["form"]

        # --- SECCIONES ---
        elif action == "section_est":
            ctx["action_title"] = "Estudiantes"
            ctx["action_subtitle"] = "Gestioná los estudiantes o creá uno nuevo."

        elif action == "section_insc":
            ctx["action_title"] = "Inscripciones"
            ctx["action_subtitle"] = "Inscribí a carrera, materias y mesas."

        elif action == "section_calif":
            ctx["action_title"] = "Calificaciones"
            ctx["action_subtitle"] = "Carga y gestión de calificaciones."

        elif action == "section_admin":
            ctx["action_title"] = "Administración"
            ctx["action_subtitle"] = "Configuración de espacios, planes y correlatividades."

        elif action == "section_help":
            ctx["action_title"] = "Ayuda"
            ctx["action_subtitle"] = "Información y soporte."

        return render(request, "academia_core/panel_inicio.html", ctx)

    # =================== Estudiante (si lo usaras) ===================
    if role == "Estudiante":
        # si tuvieras un panel específico de estudiante:
        return render(request, "panel_estudiante.html", {"action": request.GET.get("action") or "tray"})

    # =================== Docente (si lo usaras) ===================
    if role == "Docente":
        return render(request, "panel_docente.html", {})

    # fallback
    return render(request, "academia_core/panel_inicio.html", {"action": "section_est"})

# === STUBS / FALLBACKS PARA EVITAR ImportError (pegar AL FINAL de views_panel.py) ===

# panel_correlatividades
if "panel_correlatividades" not in globals():
    def panel_correlatividades(request):
        return HttpResponse("Correlatividades — en construcción.")

# panel_horarios
if "panel_horarios" not in globals():
    def panel_horarios(request):
        return HttpResponse("Horarios — en construcción.")

# panel_docente
if "panel_docente" not in globals():
    def panel_docente(request):
        return HttpResponse("Panel Docente — en construcción.")

# API: espacios por inscripción (GET)
if "get_espacios_por_inscripcion" not in globals():
    @require_GET
    def get_espacios_por_inscripcion(request, insc_id: int):
        return JsonResponse({"ok": True, "items": []})

# API: correlatividades (GET)
if "get_correlatividades" not in globals():
    @require_GET
    def get_correlatividades(request, espacio_id: int, insc_id: int = None):
        return JsonResponse({"ok": True, "rules": [], "puede_cursar": True})

# Guardados (POST)
if "crear_inscripcion_cursada" not in globals():
    @require_POST
    def crear_inscripcion_cursada(request, insc_prof_id: int):
        return JsonResponse({"ok": False, "error": "No implementado"}, status=501)

if "crear_movimiento" not in globals():
    @require_POST
    def crear_movimiento(request, insc_cursada_id: int):
        return JsonResponse({"ok": False, "error": "No implementado"}, status=501)

# Redirecciones utilitarias
if "redir_estudiante" not in globals():
    def redir_estudiante(request, dni: str):
        return redirect(f"/panel/?action=section_est&dni={dni}")

if "redir_inscripcion" not in globals():
    def redir_inscripcion(request, insc_id: int):
        return redirect(f"/panel/estudiante/{insc_id}/")