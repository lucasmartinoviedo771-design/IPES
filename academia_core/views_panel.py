from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages

import unicodedata

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import redirect

def _norm(txt: str) -> str:
    if not txt:
        return ""
    # quita acentos y pasa a minúscula
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn").lower()

# ---- helpers (poner junto a los demás) ----

def _get_estudiantes_activos():
    from .models import Estudiante
    fields = {f.name for f in Estudiante._meta.get_fields()}
    qs = Estudiante.objects.all()
    if "activo" in fields:
        qs = qs.filter(activo=True)
    return list(qs.order_by("apellido", "nombre").values("id", "apellido", "nombre", "dni"))

def _get_profesorados_activos():
    from .models import Profesorado
    fields = {f.name for f in Profesorado._meta.get_fields()}
    qs = Profesorado.objects.all()
    for flag in ("activa", "activo", "habilitado", "is_active", "enabled"):
        if flag in fields:
            qs = qs.filter(**{flag: True})
            break
    qs = qs.order_by("nombre") if "nombre" in fields else qs.order_by("id")
    data = list(qs.values("id", "nombre", "tipo") if "tipo" in fields else qs.values("id", "nombre"))
    # Tipo por defecto
    for p in data:
        if "tipo" not in p or not p["tipo"]:
            name = p.get("nombre", "")
            n = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode().lower()
            p["tipo"] = "certificacion_docente" if ("certificacion" in n and "docent" in n) else "profesorado"
    return data

def _get_materias_para_select():
    """
    Devuelve materias activas con: id, nombre, profesorado_id, periodo (ANUAL/1C/2C).
    Soporta nombres de campos frecuentes y cae con defaults si no existen.
    """
    try:
        from .models import Materia
    except Exception:
        return []

    fields = {f.name for f in Materia._meta.get_fields()}
    qs = Materia.objects.all()

    # activo/activa/habilitado
    for flag in ("activa", "activo", "habilitado", "is_active", "enabled"):
        if flag in fields:
            qs = qs.filter(**{flag: True})
            break

    qs = qs.order_by("nombre") if "nombre" in fields else qs.order_by("id")

    data = []
    for m in qs:
        # id de profesorados (FK)
        pid = getattr(m, "profesorado_id", None)
        if pid is None and hasattr(m, "profesorado") and getattr(m, "profesorado", None):
            try:
                pid = m.profesorado.id
            except Exception:
                pid = None

        nombre = getattr(m, "nombre", str(m))
        # período
        if "periodo" in fields:
            per = getattr(m, "periodo", None) or "ANUAL"
        elif "cuatrimestre" in fields:
            c = getattr(m, "cuatrimestre", None)
            per = "1C" if c == 1 else ("2C" if c == 2 else "ANUAL")
        else:
            per = "ANUAL"

        data.append({"id": m.id, "nombre": nombre, "profesorado_id": pid, "periodo": per})
    return data

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

# --- helpers al inicio del archivo (debajo de los imports y modelos) ---
def _profesorados_para_select():
    fields = {f.name for f in Profesorado._meta.get_fields()}
    qs = Profesorado.objects.all()
    for flag in ("activa", "activo", "habilitado", "is_active", "enabled"):
        if flag in fields:
            qs = qs.filter(**{flag: True})
            break
    qs = qs.order_by("nombre") if "nombre" in fields else qs.order_by("id")

    data = list(qs.values("id", "nombre", "tipo") if "tipo" in fields else qs.values("id", "nombre"))

    # Normalizamos 'tipo' si viene vacío
    for p in data:
        nombre = p.get("nombre", "")
        t = p.get("tipo") if "tipo" in p else None
        if not t:
            n = _norm(nombre)
            p["tipo"] = "certificacion_docente" if ("certificacion" in n and "docent" in n) else "profesorado"

    # Fallback: si quedó vacío, mostramos todos (útil para probar UI)
    if not data:
        all_qs = Profesorado.objects.all().order_by("nombre" if "nombre" in fields else "id")
        data = list(all_qs.values("id", "nombre", "tipo") if "tipo" in fields else all_qs.values("id", "nombre"))
        for p in data:
            nombre = p.get("nombre", "")
            t = p.get("tipo") if "tipo" in p else None
            if not t:
                n = _norm(nombre)
                p["tipo"] = "certificacion_docente" if ("certificacion" in n and "docent" in n) else "profesorado"
    return data


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

        if action == "add_est":
            ctx["action_title"] = "Nuevo estudiante"
            # mostrar el formulario por defecto
            ctx["form"] = True

            if request.method == "POST":
                data = request.POST
                files = request.FILES
                errors = {}

                # campos obligatorios
                dni = (data.get("dni") or "").strip()
                apellido = (data.get("apellido") or "").strip()
                nombre = (data.get("nombre") or "").strip()

                if not dni: errors["dni"] = "El DNI es obligatorio."
                if not apellido: errors["apellido"] = "El apellido es obligatorio."
                if not nombre: errors["nombre"] = "El nombre es obligatorio."

                # DNI duplicado
                if dni and Estudiante.objects.filter(dni=dni).exists():
                    errors["dni"] = "Ya existe un estudiante con ese DNI."

                if errors:
                    ctx["errors"] = errors
                    ctx["post"] = data  # opcional: para re-pintar valores en el form
                    # no redirect: volvemos a renderizar el formulario con los errores
                    return render(request, "academia_core/panel_inicio.html", ctx)

                # crear instancia
                e = Estudiante(
                    dni=dni,
                    apellido=apellido,
                    nombre=nombre,
                )

                # opcionales (si existen en el modelo)
                if hasattr(e, "fecha_nacimiento"):
                    fn = (data.get("fecha_nacimiento") or "").strip()
                    if fn:
                        e.fecha_nacimiento = fn  # Django parsea YYYY-MM-DD

                for f in ["lugar_nacimiento", "email", "telefono", "localidad",
                          "telefono_emergencia", "parentesco"]:
                    if hasattr(e, f):
                        setattr(e, f, (data.get(f) or "").strip())

                if hasattr(e, "activo"):
                    e.activo = bool(data.get("activo"))

                if hasattr(e, "foto") and "foto" in files and files["foto"]:
                    e.foto = files["foto"]

                # guardar
                e.save()
                messages.success(request, "Estudiante guardado con éxito.")
                return redirect(f"{reverse('panel')}?action=add_est")

        # --- INSCRIPCIÓN A CARRERA (alias insc_carrera / insc_prof) ---
        elif action in ("insc_carrera", "insc_prof"):
            ctx["action_title"] = "Inscripción a carrera"

            try:
                ctx["estudiantes"] = Estudiante.objects.filter(activo=True).order_by("apellido", "nombre")
            except Exception:
                ctx["estudiantes"] = []

            # Profesorados (activos si existe flag; si no hay, mostrar todos)
            try:
                ctx["profesorados"] = _profesorados_para_select()
            except Exception:
                # último fallback: al menos todos, con tipo por defecto
                ctx["profesorados"] = [{"id": p.id, "nombre": getattr(p, "nombre", str(p)), "tipo": "profesorado"}
                                       for p in Profesorado.objects.all().order_by("nombre")]

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
            ctx["action_title"] = "Inscripción a materia (cursada)"

            try:
                ctx["estudiantes"] = _get_estudiantes_activos()
            except Exception:
                ctx["estudiantes"] = []

            try:
                ctx["profesorados"] = _get_profesorados_activos()
            except Exception:
                ctx["profesorados"] = []

            try:
                ctx["materias"] = _get_materias_para_select()
            except Exception:
                ctx["materias"] = []

            # Ciclo lectivo (año) y períodos
            anio = date.today().year
            ctx["ciclos"] = list(range(anio - 1, anio + 2))  # ej. 2024–2026
            ctx["periodos"] = [("ANUAL", "Anual"), ("1C", "1° cuatrimestre"), ("2C", "2° cuatrimestre")]

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