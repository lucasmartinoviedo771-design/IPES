from __future__ import annotations
from datetime import date

import unicodedata

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST


# ========= helpers generales =========

def _norm(txt: str) -> str:
    if not txt:
        return ""
    # quita acentos y pasa a minúscula
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn").lower()


def _get_model(*names):
    """Devuelve el primer modelo existente en academia_core con alguno de estos nombres."""
    for n in names:
        try:
            return apps.get_model("academia_core", n)
        except Exception:
            continue
    return None


def _fk_name_to(model, related_model_cls) -> str | None:
    for f in model._meta.get_fields():
        if getattr(f, "is_relation", False) and getattr(f, "many_to_one", False) and f.related_model is related_model_cls:
            return f.name
    return None


def _has_field(model, *names) -> str | None:
    fields = {f.name for f in model._meta.get_fields()}
    for n in names:
        if n in fields:
            return n
    return None


# ========= modelos (robustos) =========
# estos existen en tu app
Estudiante        = _get_model("Estudiante")
Profesorado       = _get_model("Profesorado")
PlanEstudios      = _get_model("PlanEstudios")
EspacioCurricular = _get_model("EspacioCurricular")
Correlatividad    = _get_model("Correlatividad")
EstudianteProfesorado = _get_model("EstudianteProfesorado")

# estos pueden no existir o llamarse distinto
InscripcionEspacio = _get_model("InscripcionEspacio", "InscripcionCursada", "InscripcionMateria")
ResultadoFinal     = _get_model("ResultadoFinal", "ActaFinal", "Aprobacion", "CalificacionFinal")
Regularidad        = _get_model("Regularidad", "Cursada", "CondicionCursada")
Movimiento         = _get_model("Movimiento")              # alternativa a Regularidad (con condicion.codigo)
InscripcionFinal   = _get_model("InscripcionFinal", "MesaInscripcion")


# ========= helpers de datos para selects =========

def _get_estudiantes_activos():
    fields = {f.name for f in Estudiante._meta.get_fields()}
    qs = Estudiante.objects.all()
    if "activo" in fields:
        qs = qs.filter(activo=True)
    return list(qs.order_by("apellido", "nombre").values("id", "apellido", "nombre", "dni"))


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
    return data


# ========= rol/contexto =========

def _role_for(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "Invitado"
    if getattr(user, "is_superuser", False):
        return "Admin"
    try:
        if hasattr(user, "perfil") and user.perfil.rol:
            return str(user.perfil.rol)
        if user.groups.filter(name__iexact="Docente").exists():
            return "Docente"
        if user.groups.filter(name__iexact="Estudiante").exists():
            return "Estudiante"
    except Exception:
        pass
    return "Usuario"


def _base_context(request: HttpRequest):
    user = getattr(request, "user", None)
    role = _role_for(user)
    can_admin = role in ["Admin", "Secretaría", "Bedel"]
    try:
        profesorados = list(Profesorado.objects.all().order_by("nombre"))
    except Exception:
        profesorados = []
    return {"rol": role, "can_admin": can_admin, "profesorados": profesorados}


# ========= ELEGIBILIDAD: estado académico del alumno =========

def _estado_sets_para_estudiante(estudiante_id: int, plan_id: int, ciclo: int | None = None):
    """
    Devuelve 4 sets de IDs de espacios (del plan):
      - aprobadas_ids
      - regularizadas_ids (incluye aprobadas)
      - inscriptas_ids (cursada vigente; filtra por ciclo si se provee)
      - inscriptas_final_ids (si existe el modelo)
    Funciona aunque algunos modelos no existan o se llamen distinto.
    """
    aprobadas_ids        : set[int] = set()
    regularizadas_ids    : set[int] = set()
    inscriptas_ids       : set[int] = set()
    inscriptas_final_ids : set[int] = set()

    # --- Aprobadas (final/promoción) ---
    if ResultadoFinal:
        fk_est  = _fk_name_to(ResultadoFinal, Estudiante)
        fk_esp  = _fk_name_to(ResultadoFinal, EspacioCurricular)
        fk_plan = _fk_name_to(ResultadoFinal, PlanEstudios) or _has_field(ResultadoFinal, "plan", "plan_id")
        if fk_est and fk_esp:
            qs = ResultadoFinal.objects.filter(**{f"{fk_est}_id": estudiante_id})
            if fk_plan:
                key = fk_plan if fk_plan.endswith("_id") else f"{fk_plan}_id"
                qs = qs.filter(**{key: plan_id})
            f_estado = _has_field(ResultadoFinal, "estado", "situacion", "condicion", "resultado")
            f_aprob  = _has_field(ResultadoFinal, "aprobado", "is_aprobado", "ok")
            f_nota   = _has_field(ResultadoFinal, "nota", "calificacion", "puntaje")
            if f_aprob:
                qs = qs.filter(**{f_aprob: True})
            elif f_estado:
                qs = qs.filter(**{f"{f_estado}__in": ["APROBADO", "PROMOCIONADO"]})
            elif f_nota:
                qs = qs.filter(**{f"{f_nota}__gte": 4})
            aprobadas_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    # --- Regularizadas (incluye aprobadas) ---
    if Regularidad:
        fk_est  = _fk_name_to(Regularidad, Estudiante)
        fk_esp  = _fk_name_to(Regularidad, EspacioCurricular)
        fk_plan = _fk_name_to(Regularidad, PlanEstudios) or _has_field(Regularidad, "plan", "plan_id")
        if fk_est and fk_esp:
            qs = Regularidad.objects.filter(**{f"{fk_est}_id": estudiante_id})
            if fk_plan:
                key = fk_plan if fk_plan.endswith("_id") else f"{fk_plan}_id"
                qs = qs.filter(**{key: plan_id})
            f_estado = _has_field(Regularidad, "estado", "situacion", "condicion")
            f_reg    = _has_field(Regularidad, "regular", "es_regular", "is_regular")
            if f_reg:
                qs = qs.filter(**{f_reg: True})
            elif f_estado:
                qs = qs.filter(**{f"{f_estado}__in": ["REGULAR", "PROMOCIONADO", "APROBADO"]})
            regularizadas_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    elif Movimiento:
        # Alternativa: Movimiento -> inscripcion (FK) -> espacio, y Condicion con 'codigo'
        f_insc = _has_field(Movimiento, "inscripcion")
        if f_insc and InscripcionEspacio:
            # nombres en InscripcionEspacio
            fk_est_ie  = _fk_name_to(InscripcionEspacio, Estudiante) or "estudiante"
            fk_esp_ie  = _fk_name_to(InscripcionEspacio, EspacioCurricular) or "espacio"
            fk_plan_ie = _fk_name_to(InscripcionEspacio, PlanEstudios) or _has_field(InscripcionEspacio, "plan", "plan_id")
            qs = Movimiento.objects.filter(**{f"{f_insc}__{fk_est_ie}_id": estudiante_id})
            if fk_plan_ie:
                key = fk_plan_ie if fk_plan_ie.endswith("_id") else f"{fk_plan_ie}_id"
                qs = qs.filter(**{f"{f_insc}__{key}": plan_id})
            # Condiciones válidas para “regular”
            cond_field = _has_field(Movimiento, "condicion")
            if cond_field:
                qs = qs.filter(**{f"{cond_field}__codigo__in": ["REGULAR", "PROMOCIONADO", "APROBADO"]})
            regularizadas_ids = set(qs.values_list(f"{f_insc}__{fk_esp_ie}_id", flat=True))

    # incluir aprobadas dentro de regularizadas
    regularizadas_ids |= aprobadas_ids

    # --- Ya inscripto a cursada ---
    if InscripcionEspacio:
        fk_est  = _fk_name_to(InscripcionEspacio, Estudiante) or "estudiante"
        fk_esp  = _fk_name_to(InscripcionEspacio, EspacioCurricular) or "espacio"
        fk_plan = _fk_name_to(InscripcionEspacio, PlanEstudios) or _has_field(InscripcionEspacio, "plan", "plan_id")
        f_ciclo = _has_field(InscripcionEspacio, "ciclo", "anio", "anio_lectivo", "anio_academico")
        qs = InscripcionEspacio.objects.filter(**{f"{fk_est}_id": estudiante_id})
        if fk_plan:
            key = fk_plan if fk_plan.endswith("_id") else f"{fk_plan}_id"
            qs = qs.filter(**{key: plan_id})
        if ciclo and f_ciclo:
            qs = qs.filter(**{f_ciclo: ciclo})
        inscriptas_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    # --- Ya inscripto a final (opcional) ---
    if InscripcionFinal:
        fk_est  = _fk_name_to(InscripcionFinal, Estudiante) or "estudiante"
        fk_esp  = _fk_name_to(InscripcionFinal, EspacioCurricular) or "espacio"
        fk_plan = _fk_name_to(InscripcionFinal, PlanEstudios) or _has_field(InscripcionFinal, "plan", "plan_id")
        qs = InscripcionFinal.objects.filter(**{f"{fk_est}_id": estudiante_id})
        if fk_plan:
            key = fk_plan if fk_plan.endswith("_id") else f"{fk_plan}_id"
            qs = qs.filter(**{key: plan_id})
        inscriptas_final_ids = set(qs.values_list(f"{fk_esp}_id", flat=True))

    return aprobadas_ids, regularizadas_ids, inscriptas_ids, inscriptas_final_ids


def _correlativas_para(espacio_id: int, plan_id: int, para: str):
    para = (para or "PARA_CURSAR").upper()
    qs = Correlatividad.objects.filter(plan_id=plan_id, espacio_id=espacio_id)
    if para == "PARA_CURSAR":
        return qs.filter(Q(tipo__iexact="PARA_CURSAR") | Q(tipo__isnull=True))
    return qs.filter(tipo__iexact="PARA_RENDIR")


def _cumple_correlatividad(c, aprobadas_ids: set[int], regularizadas_ids: set[int], plan_id: int) -> bool:
    req = (c.requisito or "").upper()
    objetivo = aprobadas_ids if req.startswith("APROB") else regularizadas_ids

    if c.requiere_espacio_id:
        return c.requiere_espacio_id in objetivo

    if c.requiere_todos_hasta_anio:
        hasta = int(c.requiere_todos_hasta_anio)
        ids_hasta = set(
            EspacioCurricular.objects.filter(plan_id=plan_id, anio__lte=hasta).values_list("id", flat=True)
        )
        return ids_hasta.issubset(objetivo)

    # sin requisito explícito -> no bloquea
    return True


def _habilitado(estudiante_id: int, plan_id: int, espacio, para: str, ciclo: int | None = None):
    aprobadas, regularizadas, inscriptas, insc_final = _estado_sets_para_estudiante(estudiante_id, plan_id, ciclo)

    # vetos generales
    if para == "PARA_CURSAR" and espacio.id in inscriptas:
        return False, "ya_inscripto"
    if para == "PARA_CURSAR" and espacio.id in regularizadas:
        return False, "ya_regular"
    if espacio.id in aprobadas:
        return False, "ya_aprobado"
    if para == "PARA_RENDIR" and espacio.id in insc_final:
        return False, "ya_inscripto_final"

    # correlativas
    faltantes = []
    for c in _correlativas_para(espacio.id, plan_id, para):
        if not _cumple_correlatividad(c, aprobadas, regularizadas, plan_id):
            if c.requiere_espacio_id:
                faltantes.append({
                    "tipo": (c.tipo or para).upper(),
                    "requisito": (c.requisito or "").upper(),
                    "requiere_espacio_id": c.requiere_espacio_id,
                })
            elif c.requiere_todos_hasta_anio:
                faltantes.append({
                    "tipo": (c.tipo or para).upper(),
                    "requisito": (c.requisito or "").upper(),
                    "requiere_todos_hasta_anio": int(c.requiere_todos_hasta_anio),
                })

    if faltantes:
        return False, {"motivo": "falta_correlativas", "faltantes": faltantes}

    return True, None


# ========= Vistas del panel =========

@login_required
def panel(request: HttpRequest) -> HttpResponse:
    """
    Panel unificado (Admin/Secretaría | Estudiante | Docente).
    """
    role = _role_for(request.user)

    # =================== Admin / Secretaría ===================
    if can_admin:
        ctx = _base_context(request)

        # leer 'action' (por defecto, estudiantes)
        action = request.GET.get("action", "section_est")
        ctx["action"] = action
        ctx["form"] = None
        ctx["action_title"] = "Inicio"
        ctx["action_subtitle"] = "Bienvenido al panel de gestión."

        # Métricas para el dashboard
        ctx['total_estudiantes'] = Estudiante.objects.count()
        ctx['total_profesorados'] = Profesorado.objects.count()
        ctx['total_espacios'] = EspacioCurricular.objects.count()
        ctx['total_inscripciones_carrera'] = EstudianteProfesorado.objects.count()
        ctx['total_inscripciones_materia'] = InscripcionEspacio.objects.count()

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
                e = Estudiante(dni=dni, apellido=apellido, nombre=nombre)

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
                # quedarse en el mismo formulario:
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

            if request.method == "POST":
                est_id = int(request.POST.get("estudiante_id") or 0)
                prof_id = int(request.POST.get("profesorado_id") or 0)
                plan_id = int(request.POST.get("plan_id") or 0)
                cohorte = int(request.POST.get("cohorte") or date.today().year)

                try:
                    insc = EstudianteProfesorado(
                        estudiante_id=est_id,
                        profesorado_id=prof_id,
                        plan_id=plan_id or None,
                        cohorte=cohorte,
                    )
                    insc.full_clean()
                    insc.save()
                    messages.success(request, "Inscripción a carrera guardada con éxito.")
                    return redirect(request.path_info)  # Redirigir a la misma página
                except ValidationError as e:
                    messages.error(request, f"Error de validación: {e}")
                except Exception as e:
                    messages.error(request, f"Error al guardar la inscripción: {e}")

            # planes por profesorado (id -> [{id, label}...])
            planes_map = {}
            try:
                Plan = apps.get_model("academia_core", "PlanEstudios")
                # label amigable: usa nombre si lo tenés; si no, resolucion o el ID
                for p in Plan.objects.select_related("profesorado").all().order_by("profesorado_id","id"):
                    label = getattr(p, "nombre", None) or getattr(p, "resolucion", None) or f"Plan {p.id}"
                    planes_map.setdefault(p.profesorado_id, []).append({"id": p.id, "label": label})
            except Exception:
                pass
            ctx["planes_map"] = planes_map

        # --- INSCRIPCIÓN A MATERIA (cursada) ---
        elif action == "insc_esp":
            ctx["action_title"] = "Inscripción a materia (cursada)"
            ctx["action_subtitle"] = "Inscribí a un estudiante en un espacio curricular."

            # Estudiantes (activos si existe el flag)
            try:
                est_qs = Estudiante.objects.all()
                if hasattr(Estudiante, "activo"):
                    est_qs = est_qs.filter(activo=True)
                ctx["estudiantes"] = list(
                    est_qs.order_by("apellido", "nombre").values("id", "apellido", "nombre", "dni")
                )
            except Exception:
                ctx["estudiantes"] = []

            # Profesorados (activos si existe el flag; fallback a todos)
            try:
                prof_qs = Profesorado.objects.all()
                if hasattr(Profesorado, "activa"):
                    prof_qs = prof_qs.filter(activa=True)
                elif hasattr(Profesorado, "activo"):
                    prof_qs = prof_qs.filter(activo=True)
                prof_qs = prof_qs.order_by("nombre") if hasattr(Profesorado, "nombre") else prof_qs.order_by("id")
                profesorados = list(prof_qs.values("id", "nombre", "tipo") if hasattr(Profesorado, "tipo") else prof_qs.values("id", "nombre"))
                for p in profesorados:
                    p.setdefault("tipo", "profesorado")
                ctx["profesorados"] = profesorados
            except Exception:
                ctx["profesorados"] = []

            # Espacios curriculares (activos si existe el flag) -> id, nombre, profesorado_id, periodo
            try:
                ec_qs = EspacioCurricular.objects.all()
                if hasattr(EspacioCurricular, "activa"):
                    ec_qs = ec_qs.filter(activa=True)
                elif hasattr(EspacioCurricular, "activo"):
                    ec_qs = ec_qs.filter(activo=True)
                ec_qs = ec_qs.order_by("nombre") if hasattr(EspacioCurricular, "nombre") else ec_qs.order_by("id")

                espacios = []
                for e in ec_qs:
                    # FK a profesorado
                    prof_id = getattr(e, "profesorado_id", None)
                    if prof_id is None and hasattr(e, "profesorado") and getattr(e, "profesorado", None):
                        try:
                            prof_id = e.profesorado.id
                        except Exception:
                            prof_id = None
                    # nombre y periodo
                    nombre = getattr(e, "nombre", str(e))
                    if hasattr(e, "periodo") and getattr(e, "periodo", None):
                        per = str(getattr(e, "periodo")).upper()
                    elif hasattr(e, "cuatrimestre") and getattr(e, "cuatrimestre", None) in (1, 2):
                        per = "1C" if int(getattr(e, "cuatrimestre")) == 1 else "2C"
                    else:
                        per = "ANUAL"
                    espacios.append({
                        "id": e.id,
                        "nombre": nombre,
                        "profesorado_id": prof_id,
                        "periodo": per,
                    })
                ctx["espacios"] = espacios
            except Exception:
                ctx["espacios"] = []

            # Ciclos lectivos y períodos (para el formulario)
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

    # =================== Docente (si lo usaras) ===================
    if role == "Docente":
        return panel_docente(request)

    # =================== Estudiante (si lo usaras) ===================
    if role == "Estudiante":
        try:
            estudiante = Estudiante.objects.get(email=request.user.email)
            inscripciones = EstudianteProfesorado.objects.filter(estudiante=estudiante)
            
            ctx = {
                'estudiante': estudiante,
                'inscripciones': inscripciones,
                'action': request.GET.get('action', 'tray'),
            }

            if ctx['action'] == 'tray':
                ctx['cursadas'] = InscripcionEspacio.objects.filter(inscripcion__in=inscripciones)
            elif ctx['action'] == 'hist':
                ctx['movimientos'] = Movimiento.objects.filter(inscripcion__in=inscripciones).order_by('-fecha')

            return render(request, "academia_core/panel_estudiante.html", ctx)
        except Estudiante.DoesNotExist:
            return HttpResponse("No se encontró un estudiante asociado a este usuario.", status=404)
        except Exception as e:
            return HttpResponse(f"Ocurrió un error: {e}", status=500)

    # fallback
    return render(request, "academia_core/panel_inicio.html", {"action": "section_est"})


# ========= APIs =========

@require_GET
def api_espacios_habilitados(request):
    est = int(request.GET["est"])
    plan = int(request.GET["plan"])
    para = request.GET.get("para", "PARA_CURSAR").upper()
    ciclo = request.GET.get("ciclo")
    ciclo = int(ciclo) if ciclo and ciclo.isdigit() else None
    periodo = (request.GET.get("periodo") or "").upper()

    qs = EspacioCurricular.objects.filter(plan_id=plan)
    if periodo and hasattr(EspacioCurricular, "periodo"):
        if periodo == "ANUAL":
            qs = qs.filter(periodo="ANUAL")
        else:
            qs = qs.filter(Q(periodo=periodo) | Q(periodo="ANUAL"))

    items = []
    # ordenar robusto
    order_fields = []
    if _has_field(EspacioCurricular, "anio"): order_fields.append("anio")
    if _has_field(EspacioCurricular, "nombre"): order_fields.append("nombre")
    qs = qs.order_by(*order_fields) if order_fields else qs

    for e in qs:
        ok, info = _habilitado(est, plan, e, para, ciclo)
        row = {"id": e.id, "nombre": getattr(e, "nombre", str(e)), "anio": getattr(e, "anio", None), "habilitado": ok}
        if not ok:
            row["bloqueo"] = info
        items.append(row)

    return JsonResponse({"items": items})


@require_POST
def post_inscribir_espacio(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido"}, status=405)
    if InscripcionEspacio is None or EstudianteProfesorado is None:
        return JsonResponse({"ok": False, "error": "Modelo de inscripción no disponible."}, status=500)

    estudiante_id  = int(request.POST["estudiante_id"])
    plan_id        = int(request.POST["plan_id"])
    espacio_id     = int(request.POST["espacio_id"])
    anio_academico = int(request.POST.get("ciclo") or 0) or None

    # Validar que el estudiante esté inscripto en ese plan (EstudianteProfesorado)
    insc_prof = get_object_or_404(
        EstudianteProfesorado,
        estudiante_id=estudiante_id,
        plan_id=plan_id
    )

    e_obj = get_object_or_404(EspacioCurricular, id=espacio_id, plan_id=plan_id)
    ok, info = _habilitado(estudiante_id, plan_id, e_obj, "PARA_CURSAR", anio_academico)
    if not ok:
        return JsonResponse({"ok": False, "error": info}, status=400)

    # nombres de campos por introspección
    fk_est  = _fk_name_to(InscripcionEspacio, Estudiante) or "estudiante"
    fk_esp  = _fk_name_to(InscripcionEspacio, EspacioCurricular) or "espacio"
    fk_plan = _fk_name_to(InscripcionEspacio, PlanEstudios) or _has_field(InscripcionEspacio, "plan", "plan_id")
    f_ciclo = _has_field(InscripcionEspacio, "ciclo", "anio", "anio_lectivo", "anio_academico")

    create_kwargs = {
        "inscripcion": insc_prof,  # tu modelo usa FK 'inscripcion' a EstudianteProfesorado
        f"{fk_esp}_id": espacio_id,
    }
    if f_ciclo and anio_academico:
        create_kwargs[f_ciclo] = anio_academico
    if fk_plan:
        key = fk_plan if fk_plan.endswith("_id") else f"{fk_plan}_id"
        create_kwargs[key] = plan_id

    # evitar duplicado
    exists = InscripcionEspacio.objects.filter(
        inscripcion=insc_prof,
        **{f"{fk_esp}_id": espacio_id}
    )
    if f_ciclo and anio_academico:
        exists = exists.filter(**{f_ciclo: anio_academico})
    if exists.exists():
        return JsonResponse({"ok": False, "error": "ya_inscripto"}, status=400)

    obj = InscripcionEspacio.objects.create(**create_kwargs)
    return JsonResponse({"ok": True, "id": obj.id})


from .forms_carga import CargaNotaForm

@login_required
def cargar_nota(request: HttpRequest) -> HttpResponse:
    if _role_for(request.user) not in ["Admin", "Secretaría", "Bedel"]:
        return HttpResponse("No tiene permisos para acceder a esta página.", status=403)

    if request.method == 'POST':
        form = CargaNotaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Nota guardada con éxito.")
            return redirect('cargar_nota')
        else:
            messages.error(request, "Error al guardar la nota. Por favor, revise los datos.")
    else:
        form = CargaNotaForm()

    ctx = {
        'form': form,
        'action_title': 'Cargar Nota',
    }
    return render(request, "academia_core/cargar_nota.html", ctx)


# ========= STUBS (por si alguna URL los referencia y aún no existen) =========

from .models import Correlatividad, PlanEstudios, EspacioCurricular

@login_required
def panel_correlatividades(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    ctx['action_title'] = "Gestión de Correlatividades"
    ctx['action_subtitle'] = "Visualizá y administrá las correlatividades entre espacios curriculares."

    correlatividades = Correlatividad.objects.all().select_related('plan', 'espacio', 'requiere_espacio').order_by('plan__nombre', 'espacio__nombre')

    ctx['correlatividades'] = correlatividades

    return render(request, "academia_core/panel_correlatividades.html", ctx)

from .models import Horario, EspacioCurricular, Docente

@login_required
def panel_horarios(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    ctx['action_title'] = "Gestión de Horarios"
    ctx['action_subtitle'] = "Visualizá y administrá los horarios de los espacios curriculares."

    horarios = Horario.objects.all().select_related('espacio', 'docente').order_by('dia_semana', 'hora_inicio')

    # Filtros (ejemplo: por espacio, por docente)
    espacio_id = request.GET.get('espacio')
    docente_id = request.GET.get('docente')

    if espacio_id:
        horarios = horarios.filter(espacio_id=espacio_id)
    if docente_id:
        horarios = horarios.filter(docente_id=docente_id)

    ctx['horarios'] = horarios
    ctx['espacios_curriculares'] = EspacioCurricular.objects.all().order_by('nombre')
    ctx['docentes'] = Docente.objects.all().order_by('apellido', 'nombre')

    return render(request, "academia_core/panel_horarios.html", ctx)

from .models import Docente, DocenteEspacio, InscripcionEspacio

@login_required
def panel_docente(request: HttpRequest) -> HttpResponse:
    try:
        docente = Docente.objects.get(email=request.user.email)
        asignaciones = DocenteEspacio.objects.filter(docente=docente).select_related('espacio')
        
        espacios_con_alumnos = []
        for asignacion in asignaciones:
            espacio = asignacion.espacio
            inscripciones = InscripcionEspacio.objects.filter(espacio=espacio).select_related('inscripcion__estudiante')
            alumnos = [insc.inscripcion.estudiante for insc in inscripciones]
            espacios_con_alumnos.append({
                'espacio': espacio,
                'alumnos': alumnos,
            })

        ctx = {
            'docente': docente,
            'espacios_con_alumnos': espacios_con_alumnos,
        }
        return render(request, "academia_core/panel_docente.html", ctx)
    except Docente.DoesNotExist:
        return HttpResponse("No se encontró un docente asociado a este usuario.", status=404)
    except Exception as e:
        return HttpResponse(f"Ocurrió un error: {e}", status=500)

if "get_espacios_por_inscripcion" not in globals():
    @require_GET
    def get_espacios_por_inscripcion(request, insc_id: int):
        return JsonResponse({"ok": True, "items": []})

if "get_correlatividades" not in globals():
    @require_GET
    def get_correlatividades(request, espacio_id: int, insc_id: int = None):
        return JsonResponse({"ok": True, "rules": [], "puede_cursar": True})

if "crear_inscripcion_cursada" not in globals():
    @require_POST
    def crear_inscripcion_cursada(request, insc_prof_id: int):
        return JsonResponse({"ok": False, "error": "No implementado"}, status=501)

if "crear_movimiento" not in globals():
    @require_POST
    def crear_movimiento(request, insc_cursada_id: int):
        return JsonResponse({"ok": False, "error": "No implementado"}, status=501)

if "redir_estudiante" not in globals():
    def redir_estudiante(request, dni: str):
        return redirect(f"/panel/?action=section_est&dni={dni}")

if "redir_inscripcion" not in globals():
    def redir_inscripcion(request, insc_id: int):
        return redirect(f"/panel/estudiante/{insc_id}/")
