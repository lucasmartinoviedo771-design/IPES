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
from django.template.loader import get_template
from django.utils.text import slugify
from django.db.models import Q

from xhtml2pdf import pisa

from .models import (
    Profesorado,
    PlanEstudios,
    Estudiante,
    EstudianteProfesorado,
    EspacioCurricular,
    Movimiento,
    Docente,
    DocenteEspacio,
)

from .forms_correlativas import CorrelatividadForm # Import the new form


# ---------- Helpers de formato ----------
def _fmt_fecha(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _fmt_nota(m):
    if m.nota_num is not None:
        return str(m.nota_num).rstrip("0").rstrip(".")
    return m.nota_texto or ""


# Resolver rutas /media y /static cuando generamos PDF
def _link_callback(uri):
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        return path
    if uri.startswith(getattr(settings, "STATIC_URL", "/static/")):
        static_root = getattr(settings, "STATIC_ROOT", "")
        if static_root:
            return os.path.join(static_root, uri.replace(settings.STATIC_URL, ""))
    # Si es una URL absoluta http(s), xhtml2pdf suele bloquear; devolvemos tal cual.
    return uri


# ---------- Permisos ----------
def _puede_ver_carton(user, prof, dni):
    if not user.is_authenticated:
        return False
    # superuser / staff
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    perfil = getattr(user, "perfil", None)
    if not perfil:
        return False

    if perfil.rol == "SECRETARIA":
        return True

    if perfil.rol == "ESTUDIANTE":
        return bool(perfil.estudiante) and perfil.estudiante.dni == dni

    if perfil.rol in ("BEDEL", "TUTOR"):
        return prof in perfil.profesorados_permitidos.all()

    if perfil.rol == "DOCENTE" and perfil.docente:
        # puede ver cartones del profesorado donde dicta algún espacio
        return perfil.docente.espacios.filter(profesorado=prof).exists()

    return False


# ---------- Helpers para slugs (sin necesitar campos en DB) ----------
def _get_prof_by_slug(prof_slug: str) -> Profesorado:
    for p in Profesorado.objects.all():
        if slugify(p.nombre) == prof_slug:
            return p
    raise Profesorado.DoesNotExist


def _get_plan_by_res_slug(prof: Profesorado, res_slug: str) -> PlanEstudios:
    # "1935-14" -> "1935/14"
    resol = (res_slug or "").replace("-", "/")
    return PlanEstudios.objects.get(profesorado=prof, resolucion=resol)


def _ensure_slug_attrs(prof: Profesorado, plan: PlanEstudios):
    # Les agregamos atributos .slug y .resolucion_slug en runtime para los templates
    try:
        prof.slug = getattr(prof, "slug", slugify(prof.nombre))
    except Exception:
        prof.slug = slugify(prof.nombre)
    try:
        plan.resolucion_slug = getattr(
            plan, "resolucion_slug", (plan.resolucion or "").replace("/", "-")
        )
    except Exception:
        plan.resolucion_slug = (plan.resolucion or "").replace("/", "-")


# ---------- Builder base (reutilizable) ----------
def _build_carton_ctx_base(prof, plan, dni: str):
    """
    Construye el contexto del cartón para un profesorado y plan dados.
    Lo usan la vista fija de Primaria y la vista genérica por slugs.
    """
    # Estudiante e inscripción
    estudiante = get_object_or_404(Estudiante, dni=dni)
    insc = get_object_or_404(
        EstudianteProfesorado, estudiante=estudiante, profesorado=prof
    )

    # Espacios del plan
    espacios = EspacioCurricular.objects.filter(profesorado=prof, plan=plan).order_by(
        "anio", "cuatrimestre", "nombre"
    )

    # Todos los movimientos del alumno en esos espacios (relación inversa)
    movs_qs = insc.movimientos.filter(espacio__in=espacios).select_related("espacio")

    # Agrupar por espacio
    por_espacio = defaultdict(list)
    for m in movs_qs:
        por_espacio[m.espacio_id].append(m)

    bloques = []
    for e in espacios:
        movs = por_espacio.get(e.id, [])

        # Orden cronológico asc; si empatan fecha: REG antes que FIN; luego id asc.
        movs.sort(
            key=lambda m: (m.fecha or date.min, 0 if m.tipo == "REG" else 1, m.id)
        )

        filas = []
        for m in movs:
            row = {
                "reg_fecha": "",
                "reg_cond": "",
                "reg_nota": "",
                "fin_fecha": "",
                "fin_cond": "",
                "fin_nota": "",
                "folio": "",
                "libro": "",
            }
            if m.tipo == "REG":
                row["reg_fecha"] = _fmt_fecha(m.fecha)
                row["reg_cond"] = m.condicion
                row["reg_nota"] = _fmt_nota(m)
            else:  # FIN
                row["fin_fecha"] = _fmt_fecha(m.fecha)
                row["fin_cond"] = m.condicion
                row["fin_nota"] = _fmt_nota(m)
                row["folio"] = m.folio
                row["libro"] = m.libro
            filas.append(row)

        if not filas:
            filas = [
                {
                    "reg_fecha": "",
                    "reg_cond": "",
                    "reg_nota": "",
                    "fin_fecha": "",
                    "fin_cond": "",
                    "fin_nota": "",
                    "folio": "",
                    "libro": "",
                }
            ]

        bloques.append(
            {
                "anio": e.anio,
                "cuatri": e.cuatrimestre,
                "espacio": e.nombre,
                "rows": filas,
            }
        )

    # Slugs calculados (para templates que los usen)
    _ensure_slug_attrs(prof, plan)

    return {
        "profesorado": prof,
        "plan": plan,
        "estudiante": estudiante,
        "inscripcion": insc,
        "bloques": bloques,
    }


# ---------- Builder original: Primaria fija ----------
def _build_carton_ctx(dni: str):
    prof = get_object_or_404(Profesorado, nombre="Profesorado de Educación Primaria")
    plan = get_object_or_404(PlanEstudios, profesorado=prof, resolucion="1935/14")
    return _build_carton_ctx_base(prof, plan, dni)


# ---------- Vistas HTML / PDF (Primaria) ----------
@login_required
def carton_primaria_por_dni(request, dni):
    ctx = _build_carton_ctx(dni)
    if not _puede_ver_carton(request.user, ctx["profesorado"], dni):
        return HttpResponseForbidden("No tenés permiso para ver este cartón.")
    return render(request, "carton_primaria.html", ctx)


@login_required
def carton_primaria_pdf(request, dni):
    ctx = _build_carton_ctx(dni)
    if not _puede_ver_carton(request.user, ctx["profesorado"], dni):
        return HttpResponseForbidden("No tenés permiso para ver este cartón.")
    html = get_template("carton_primaria.html").render(ctx)
    out = io.BytesIO()
    pisa.CreatePDF(html, dest=out, encoding="utf-8", link_callback=_link_callback)
    resp = HttpResponse(out.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="carton_{dni}.pdf"'
    return resp


# ---------- Vista GENÉRICA por slugs (HTML) ----------
@login_required
def carton_por_prof_y_plan(request, prof_slug, res_slug, dni):
    """
    Ejemplo URL:
    /carton/profesorado-de-educacion-primaria/1935-14/40000002/
    """
    try:
        prof = _get_prof_by_slug(prof_slug)
        plan = _get_plan_by_res_slug(prof, res_slug)
    except Exception:
        return HttpResponseForbidden("Plan o profesorado inválido.")
    if not _puede_ver_carton(request.user, prof, dni):
        return HttpResponseForbidden("No tenés permiso para ver este cartón.")
    ctx = _build_carton_ctx_base(prof, plan, dni)
    return render(request, "carton_primaria.html", ctx)


# ---------- PDF GENÉRICO por slugs ----------
@login_required
def carton_generico_pdf(request, prof_slug, res_slug, dni):
    try:
        prof = _get_prof_by_slug(prof_slug)
        plan = _get_plan_by_res_slug(prof, res_slug)
    except Exception:
        return HttpResponseForbidden("Plan o profesorado inválido.")
    if not _puede_ver_carton(request.user, prof, dni):
        return HttpResponseForbidden("No tenés permiso para ver este cartón.")
    ctx = _build_carton_ctx_base(prof, plan, dni)
    html = get_template("carton_primaria.html").render(ctx)
    out = io.BytesIO()
    pisa.CreatePDF(html, dest=out, encoding="utf-8", link_callback=_link_callback)
    resp = HttpResponse(out.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="carton_{dni}.pdf"'
    return resp


# ---------- Buscador por DNI (opcional) ----------
def buscar_carton_primaria(request):
    dni = request.GET.get("dni")
    if dni:
        return redirect("carton_primaria", dni=dni)
    return render(request, "buscar_carton.html")


# ---------- Helpers de estado (Mi Cursada y Docente) ----------
def _es_aprobada(m):
    # Final aprobado por regularidad o libre (>=6) o equivalencia
    if m.tipo == "FIN":
        if m.condicion == "Equivalencia":
            return True
        if (
            m.condicion in ("Regular", "Libre")
            and m.nota_num is not None
            and m.nota_num >= 6
        ):
            return True
    # Aprobado/Promoción por REG con nota >=6 (numérica o en texto)
    if m.tipo == "REG" and m.condicion in ("Promoción", "Aprobado"):
        if m.nota_num is not None and m.nota_num >= 6:
            return True
        n = EstudianteProfesorado._parse_num(m.nota_texto)
        if n is not None and n >= 6:
            return True
    return False


def _es_desaprobada(m):
    if m.tipo == "REG" and str(m.condicion).startswith("Desaprobado"):
        return True
    if m.nota_num is not None and m.nota_num < 6:
        return True
    return False


# ---------- Router post-login (evita mandar Bedel/Tutor a /alumno/) ----------
@login_required
def home_router(request):
    perfil = getattr(request.user, "perfil", None)
    # Estudiante → Mi Cursada
    if perfil and perfil.rol == "ESTUDIANTE" and perfil.estudiante:
        return redirect("alumno_home")
    # Staff/otros roles → Admin
    if request.user.is_staff:
        return redirect("/admin/")
    # Fallback: login público
    return redirect("login")


# ---------- Vista "Mi Cursada" (solo alumno) ----------
@login_required
def alumno_home(request):
    perfil = getattr(request.user, "perfil", None)
    if not perfil or perfil.rol != "ESTUDIANTE" or not perfil.estudiante:
        return HttpResponseForbidden("Solo para estudiantes.")

    est = perfil.estudiante
    inscs = EstudianteProfesorado.objects.filter(estudiante=est).select_related(
        "profesorado"
    )

    items = []
    for ins in inscs:
        plan = (
            PlanEstudios.objects.filter(
                profesorado=ins.profesorado, vigente=True
            ).first()
            or PlanEstudios.objects.filter(profesorado=ins.profesorado).first()
        )

        aprobadas = 0
        desaprobadas = 0
        pendientes = 0
        pendientes_list = []
        todas = []

        if plan:
            # Slugs para templates (aunque no haya campos en DB)
            ins.profesorado.slug = slugify(ins.profesorado.nombre)
            plan.resolucion_slug = (plan.resolucion or "").replace("/", "-")

            espacios = EspacioCurricular.objects.filter(
                profesorado=ins.profesorado, plan=plan
            ).order_by("anio", "cuatrimestre", "nombre")

            for e in espacios:
                movs = list(ins.movimientos.filter(espacio=e).order_by("fecha", "id"))
                last = movs[-1] if movs else None

                # Estado por materia
                if any(_es_aprobada(m) for m in movs):
                    estado = "Aprobada"
                elif last and _es_desaprobada(last):
                    estado = "Desaprobada"
                else:
                    estado = "Pendiente"

                # Texto del último movimiento (si hubo)
                ult = f"{last.tipo} • {last.condicion} • {_fmt_nota(last)} • {_fmt_fecha(last.fecha)}".strip(
                    " •"
                )

                # Contadores
                if estado == "Aprobada":
                    aprobadas += 1
                elif estado == "Desaprobada":
                    desaprobadas += 1
                else:
                    pendientes += 1
                    pendientes_list.append(
                        {
                            "anio": e.anio,
                            "cuatri": e.cuatrimestre,
                            "espacio": e.nombre,
                            "ultimo": ult or "—",
                        }
                    )

                # Lista completa (para la tabla principal)
                todas.append(
                    {
                        "id": e.id,
                        "nombre": e.nombre,
                        "anio": e.anio,
                        "cuatri": e.cuatrimestre,
                        "estado": estado,
                        "ultimo": ult or "—",
                    }
                )

        items.append(
            {
                "ins": ins,
                "plan": plan,
                "cuentas": {
                    "aprobadas": aprobadas,
                    "desaprobadas": desaprobadas,
                    "pendientes": pendientes,
                },
                "pendientes": pendientes_list,
                "todas": todas,
            }
        )

    return render(request, "alumno_home.html", {"estudiante": est, "items": items})


# ---------- Panel DOCENTE ----------


@login_required
def docente_espacio_detalle(request, espacio_id: int):
    perfil = getattr(request.user, "perfil", None)
    if not perfil or perfil.rol != "DOCENTE" or not perfil.docente:
        return HttpResponseForbidden("Solo para docentes.")

    # el docente debe tener asignado este espacio
    de = get_object_or_404(
        DocenteEspacio, docente=perfil.docente, espacio_id=espacio_id
    )
    esp = de.espacio
    prof = esp.profesorado

    q = (request.GET.get("q") or "").strip()

    # movimientos del espacio (trae estudiante/inscripción)
    movs_qs = (
        Movimiento.objects.filter(espacio=esp)
        .select_related("inscripcion__estudiante")
        .order_by("inscripcion_id", "fecha", "id")
    )

    if q:
        movs_qs = movs_qs.filter(
            Q(inscripcion__estudiante__apellido__icontains=q)
            | Q(inscripcion__estudiante__nombre__icontains=q)
            | Q(inscripcion__estudiante__dni__icontains=q)
        )

    # agrupar por inscripción (alumno)
    alumnos = []
    cur_insc = None
    cur_movs = []
    for m in movs_qs:
        if cur_insc is None:
            cur_insc = m.inscripcion
        if m.inscripcion_id != cur_insc.id:
            alumnos.append((cur_insc, cur_movs))
            cur_insc = m.inscripcion
            cur_movs = []
        cur_movs.append(m)
    if cur_insc is not None:
        alumnos.append((cur_insc, cur_movs))

    # calcular estado por alumno en este espacio
    filas = []
    aprob, desa, pend = 0, 0, 0
    for insc, movs in alumnos:
        last = movs[-1] if movs else None
        if any(_es_aprobada(m) for m in movs):
            estado = "Aprobada"
            aprob += 1
        elif last and _es_desaprobada(last):
            estado = "Desaprobada"
            desa += 1
        else:
            estado = "Pendiente"
            pend += 1

        ult = f"{last.tipo} • {last.condicion} • {_fmt_nota(last)} • {_fmt_fecha(last.fecha)}".strip(
            " •"
        )

        e = insc.estudiante
        filas.append(
            {
                "apellido": e.apellido,
                "nombre": e.nombre,
                "dni": e.dni,
                "cohorte": insc.cohorte or "—",
                "estado": estado,
                "ultimo": ult or "—",
            }
        )

    # ordenar por estado (pendientes primero), luego apellido
    order_key = {"Pendiente": 0, "Desaprobada": 1, "Aprobada": 2}
    filas.sort(
        key=lambda r: (order_key.get(r["estado"], 9), r["apellido"], r["nombre"])
    )

    ctx = {
        "docente": perfil.docente,
        "espacio": esp,
        "profesorado": prof,
        "resumen": {
            "aprobadas": aprob,
            "desaprobadas": desa,
            "pendientes": pend,
            "total": len(filas),
        },
        "filas": filas,
        "q": q,
    }
    return render(request, "docente_espacio_detalle.html", ctx)


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
    if _has_field(EspacioCurricular, "anio"):
        order_fields.append("anio")
    if _has_field(EspacioCurricular, "nombre"):
        order_fields.append("nombre")
    qs = qs.order_by(*order_fields) if order_fields else qs

    for e in qs:
        ok, info = _habilitado(est, plan, e, para, ciclo)
        row = {
            "id": e.id,
            "nombre": getattr(e, "nombre", str(e)),
            "anio": getattr(e, "anio", None),
            "habilitado": ok,
        }
        if not ok:
            row["bloqueo"] = info
        items.append(row)

    return JsonResponse({"items": items})


@require_POST
def post_inscribir_espacio(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido"}, status=405)
    if InscripcionEspacio is None or EstudianteProfesorado is None:
        return JsonResponse(
            {"ok": False, "error": "Modelo de inscripción no disponible."}, status=500
        )

    estudiante_id = int(request.POST["estudiante_id"])
    plan_id = int(request.POST["plan_id"])
    espacio_id = int(request.POST["espacio_id"])
    anio_academico = int(request.POST.get("ciclo") or 0) or None

    # Validar que el estudiante esté inscripto en ese plan (EstudianteProfesorado)
    insc_prof = get_object_or_404(
        EstudianteProfesorado, estudiante_id=estudiante_id, plan_id=plan_id
    )

    e_obj = get_object_or_404(EspacioCurricular, id=espacio_id, plan_id=plan_id)
    ok, info = _habilitado(estudiante_id, plan_id, e_obj, "PARA_CURSAR", anio_academico)
    if not ok:
        return JsonResponse({"ok": False, "error": info}, status=400)

    # nombres de campos por introspección
    fk_est = _fk_name_to(InscripcionEspacio, Estudiante) or "estudiante"
    fk_esp = _fk_name_to(InscripcionEspacio, EspacioCurricular) or "espacio"
    fk_plan = _fk_name_to(InscripcionEspacio, PlanEstudios) or _has_field(
        InscripcionEspacio, "plan", "plan_id"
    )
    f_ciclo = _has_field(
        InscripcionEspacio, "ciclo", "anio", "anio_lectivo", "anio_academico"
    )

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
        inscripcion=insc_prof, **{f"{fk_esp}_id": espacio_id}
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

    if request.method == "POST":
        form = CargaNotaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Nota guardada con éxito.")
            return redirect("cargar_nota")
        else:
            messages.error(
                request, "Error al guardar la nota. Por favor, revise los datos."
            )
    else:
        form = CargaNotaForm()

    ctx = {
        "form": form,
        "action_title": "Cargar Nota",
    }
    return render(request, "academia_core/cargar_nota.html", ctx)


# ========= STUBS (por si alguna URL los referencia y aún no existen) =========

from .models import Correlatividad, PlanEstudios, EspacioCurricular


@login_required
def panel_correlatividades(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    ctx["action_title"] = "Gestión de Correlatividades"
    ctx["action_subtitle"] = (
        "Visualizá y administrá las correlatividades entre espacios curriculares."
    )

    correlatividades = (
        Correlatividad.objects.all()
        .select_related("plan", "espacio", "requiere_espacio")
        .order_by("plan__nombre", "espacio__nombre")
    )

    ctx["correlatividades"] = correlatividades

    return render(request, "academia_core/panel_correlatividades.html", ctx)


from .models import Horario, EspacioCurricular, Docente


@login_required
def panel_horarios(request: HttpRequest) -> HttpResponse:
    ctx = _base_context(request)
    ctx["action_title"] = "Gestión de Horarios"
    ctx["action_subtitle"] = (
        "Visualizá y administrá los horarios de los espacios curriculares."
    )

    horarios = (
        Horario.objects.all()
        .select_related("espacio", "docente")
        .order_by("dia_semana", "hora_inicio")
    )

    # Filtros (ejemplo: por espacio, por docente)
    espacio_id = request.GET.get("espacio")
    docente_id = request.GET.get("docente")

    if espacio_id:
        horarios = horarios.filter(espacio_id=espacio_id)
    if docente_id:
        horarios = horarios.filter(docente_id=docente_id)

    ctx["horarios"] = horarios
    ctx["espacios_curriculares"] = EspacioCurricular.objects.all().order_by("nombre")
    ctx["docentes"] = Docente.objects.all().order_by("apellido", "nombre")

    return render(request, "academia_core/panel_horarios.html", ctx)


from .models import Docente, DocenteEspacio, InscripcionEspacio


@login_required
def panel_docente(request: HttpRequest) -> HttpResponse:
    try:
        docente = Docente.objects.get(email=request.user.email)
        asignaciones = DocenteEspacio.objects.filter(docente=docente).select_related(
            "espacio"
        )

        espacios_con_alumnos = []
        for asignacion in asignaciones:
            espacio = asignacion.espacio
            inscripciones = InscripcionEspacio.objects.filter(
                espacio=espacio
            ).select_related("inscripcion__estudiante")
            alumnos = [insc.inscripcion.estudiante for insc in inscripciones]
            espacios_con_alumnos.append(
                {
                    "espacio": espacio,
                    "alumnos": alumnos,
                }
            )

        ctx = {
            "docente": docente,
            "espacios_con_alumnos": espacios_con_alumnos,
        }
        return render(request, "academia_core/panel_docente.html", ctx)
    except Docente.DoesNotExist:
        return HttpResponse(
            "No se encontró un docente asociado a este usuario.", status=404
        )
    except Exception as e:
        return HttpResponse(f"Ocurrió un error: {e}", status=500)


@login_required
def correlatividades_form_view(request):
    if request.method == 'POST':
        form = CorrelatividadForm(request.POST)
        if form.is_valid():
            form.save() # Call the custom save method on the form
            messages.success(request, "Correlatividades guardadas con éxito.")
            return redirect('correlatividades_form') # Redirect to a success page or back to the form
        else:
            messages.error(request, "Error al guardar las correlatividades. Por favor, revise los datos.")
    else:
        form = CorrelatividadForm()

    ctx = {
        "form": form,
        "action_title": "Gestión de Correlatividades",
        "action_subtitle": "Carga y administración de correlatividades.",
    }
    return render(request, "academia_core/panel_correlatividades_form.html", ctx)


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