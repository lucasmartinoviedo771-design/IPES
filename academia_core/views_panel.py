from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from django.http import HttpRequest, HttpResponse
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
            try:
                # se espera que Profesorado tenga campo 'activa' y 'tipo'
                ctx["profesorados"] = Profesorado.objects.filter(activa=True).values("id", "nombre", "tipo")
            except Exception:
                ctx["profesorados"] = []
            # NO seteamos ctx["form"] aquí (para no disparar el alta de estudiante)

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
