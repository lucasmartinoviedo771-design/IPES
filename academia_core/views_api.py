from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from django.shortcuts import get_object_or_404
from academia_core.models import EspacioCurricular, PlanEstudios, Estudiante, Profesorado, Docente, Movimiento, Correlatividad # Added Correlatividad
from academia_core.eligibilidad import habilitado
from django.apps import apps

Estudiante = apps.get_model("academia_core", "Estudiante")
Docente = apps.get_model("academia_core", "Docente")
Profesorado = apps.get_model("academia_core", "Profesorado")
PlanEstudios = apps.get_model("academia_core", "PlanEstudios")


@require_GET
def api_listar_estudiantes(request):
    estudiantes = Estudiante.objects.filter(activo=True).order_by("apellido", "nombre")
    data = [
        {
            "id": e.id,
            "nombre_completo": f"{e.apellido}, {e.nombre}",
            "dni": e.dni,
            "email": e.email,
        }
        for e in estudiantes
    ]
    return JsonResponse({"items": data})


@require_GET
def api_listar_docentes(request):
    docentes = Docente.objects.filter(activo=True).order_by("apellido", "nombre")
    data = [
        {
            "id": d.id,
            "nombre_completo": f"{d.apellido}, {d.nombre}",
            "dni": d.dni,
            "email": d.email,
        }
        for d in docentes
    ]
    return JsonResponse({"items": data})


@require_GET
def api_listar_profesorados(request):
    profesorados = Profesorado.objects.all().order_by("nombre")
    data = [
        {
            "id": p.id,
            "nombre": p.nombre,
        }
        for p in profesorados
    ]
    return JsonResponse({"items": data})


@require_GET
def api_listar_planes_estudios(request):
    profesorado_id = request.GET.get("profesorado_id")
    planes = PlanEstudios.objects.all().order_by("profesorado__nombre", "nombre")
    if profesorado_id:
        planes = planes.filter(profesorado_id=profesorado_id)
    data = [
        {
            "id": p.id,
            "nombre": p.nombre,
            "resolucion": p.resolucion,
            "profesorado_id": p.profesorado_id,
        }
        for p in planes
    ]
    return JsonResponse({"items": data})


@require_GET
def api_get_estudiante_detalle(request, pk):
    estudiante = get_object_or_404(Estudiante, pk=pk)
    data = {
        "id": estudiante.id,
        "dni": estudiante.dni,
        "apellido": estudiante.apellido,
        "nombre": estudiante.nombre,
        "fecha_nacimiento": estudiante.fecha_nacimiento,
        "lugar_nacimiento": estudiante.lugar_nacimiento,
        "email": estudiante.email,
        "telefono": estudiante.telefono,
        "localidad": estudiante.localidad,
        "activo": estudiante.activo,
    }
    return JsonResponse(data)


@require_GET
def api_get_docente_detalle(request, pk):
    docente = get_object_or_404(Docente, pk=pk)
    data = {
        "id": docente.id,
        "dni": docente.dni,
        "apellido": docente.apellido,
        "nombre": docente.nombre,
        "email": docente.email,
        "activo": docente.activo,
    }
    return JsonResponse(data)


@require_GET
def api_get_espacio_curricular_detalle(request, pk):
    espacio = get_object_or_404(EspacioCurricular, pk=pk)
    data = {
        "id": espacio.id,
        "plan_id": espacio.plan_id,
        "nombre": espacio.nombre,
        "anio": espacio.anio,
        "cuatrimestre": espacio.cuatrimestre,
        "horas": espacio.horas,
        "formato": espacio.formato,
        "libre_habilitado": espacio.libre_habilitado,
    }
    return JsonResponse(data)


# NUEVO: API para listar espacios curriculares (filtrado por plan)
@require_GET
def api_listar_espacios_curriculares(request):
    plan_id = request.GET.get("plan_id")
    espacios = EspacioCurricular.objects.all().order_by("nombre")
    if plan_id:
        espacios = espacios.filter(plan_id=plan_id)
    data = [
        {
            "id": e.id,
            "nombre": e.nombre,
            "anio": e.anio,
            "cuatrimestre": e.cuatrimestre,
        }
        for e in espacios
    ]
    return JsonResponse({"items": data})


@require_GET
def api_get_movimientos_estudiante(request, estudiante_id):
    movimientos = (
        Movimiento.objects.filter(inscripcion__estudiante_id=estudiante_id)
        .select_related("espacio", "condicion")
        .order_by("-fecha")
    )
    data = [
        {
            "id": m.id,
            "espacio": m.espacio.nombre,
            "tipo": m.get_tipo_display(),
            "fecha": m.fecha,
            "condicion": m.condicion.nombre,
            "nota_num": m.nota_num,
            "nota_texto": m.nota_texto,
        }
        for m in movimientos
    ]
    return JsonResponse({"items": data})


@require_GET
def api_get_correlatividades(request, espacio_id, insc_id=None):
    # This endpoint will now return all other spaces in the same plan
    # for the correlativas multi-select fields.
    espacio_principal = get_object_or_404(EspacioCurricular, pk=espacio_id)
    plan = espacio_principal.plan

    # Get all other spaces in the same plan, excluding the principal space
    all_other_spaces_in_plan = EspacioCurricular.objects.filter(plan=plan).exclude(pk=espacio_id).order_by("nombre")

    data = []
    for esp in all_other_spaces_in_plan:
        data.append({
            "id": esp.id,
            "nombre": esp.nombre,
            "anio": esp.anio,
            "cuatrimestre": esp.cuatrimestre,
        })

    return JsonResponse({"items": data})


InscripcionEspacio = (
    apps.get_model("academia_core", "InscripcionEspacio")
    or apps.get_model("academia_core", "InscripcionCursada")
    or apps.get_model("academia_core", "InscripcionMateria")
)


@require_GET
def api_espacios_habilitados(request):
    est = int(request.GET["est"])
    plan = int(request.GET["plan"])
    para = (request.GET.get("para") or "PARA_CURSAR").upper()
    periodo = (request.GET.get("periodo") or "").upper()
    ciclo = request.GET.get("ciclo")
    ciclo = int(ciclo) if (ciclo and ciclo.isdigit()) else None

    qs = EspacioCurricular.objects.filter(plan_id=plan)
    if periodo and hasattr(EspacioCurricular, "periodo"):
        if periodo == "ANUAL":
            qs = qs.filter(periodo="ANUAL")
        else:
            qs = qs.filter(Q(periodo=periodo) | Q(periodo="ANUAL"))

    items = []
    for e in qs.order_by("anio", "nombre"):
        ok, info = habilitado(est, plan, e, para, ciclo)
        row = {
            "id": e.id,
            "nombre": e.nombre,
            "anio": getattr(e, "anio", None),
            "habilitado": ok,
        }
        if not ok:
            row["bloqueo"] = info
        items.append(row)
    return JsonResponse({"items": items})


@require_POST
def api_inscribir_espacio(request):
    if InscripcionEspacio is None:
        return JsonResponse(
            {"ok": False, "error": "No existe el modelo de inscripción a cursada."},
            status=500,
        )

    est = int(request.POST["estudiante_id"])
    plan = int(request.POST["plan_id"])
    esp = int(request.POST["espacio_id"])
    ciclo = request.POST.get("ciclo")
    ciclo = int(ciclo) if (ciclo and ciclo.isdigit()) else None

    e = get_object_or_404(EspacioCurricular, id=esp, plan_id=plan)
    ok, info = habilitado(est, plan, e, "PARA_CURSAR", ciclo)
    if not ok:
        return JsonResponse({"ok": False, "error": info}, status=400)

    # obtener nombres de campos por introspección (estudiante/espacio/plan/ciclo)
    def fk_name_to(model, related):
        for f in model._meta.get_fields():
            if (
                getattr(f, "is_relation", False)
                and getattr(f, "many_to_one", False)
                and f.related_model is related
            ):
                return f.name
        return None

    fk_est = fk_name_to(InscripcionEspacio, Estudiante) or "estudiante"
    fk_esp = fk_name_to(InscripcionEspacio, EspacioCurricular) or "espacio"
    fk_plan = fk_name_to(InscripcionEspacio, PlanEstudios) or "plan"
    f_ciclo = (
        "ciclo"
        if "ciclo" in {f.name for f in InscripcionEspacio._meta.get_fields()}
        else None
    )

    # evitar duplicado por servidor
    create_kwargs = {
        f"{fk_est}_id": est,
        f"{fk_esp}_id": esp,
        f"{fk_plan}_id": plan,
    }
    if f_ciclo and ciclo:
        create_kwargs[f_ciclo] = ciclo

    exists = InscripcionEspacio.objects.filter(**create_kwargs).exists()
    if exists:
        return JsonResponse({"ok": False, "error": "ya_inscripto"}, status=400)

    obj = InscripcionEspacio.objects.create(**create_kwargs)
    return JsonResponse({"ok": True, "id": obj.id})

@require_GET
def api_get_planes_for_profesorado(request):
    profesorado_id = request.GET.get("profesorado_id")
    if not profesorado_id:
        return JsonResponse({"items": []})
    
    planes = PlanEstudios.objects.filter(profesorado_id=profesorado_id).order_by("resolucion")
    data = [
        {
            "id": p.id,
            "nombre": str(p),
            "resolucion": p.resolucion,
        }
        for p in planes
    ]
    return JsonResponse({"items": data})

@require_GET
def api_get_espacios_for_plan(request):
    plan_id = request.GET.get("plan_id")
    if not plan_id:
        return JsonResponse({"items": []})
    
    espacios = EspacioCurricular.objects.filter(plan_id=plan_id).order_by("anio", "cuatrimestre", "nombre")
    data = [
        {
            "id": e.id,
            "nombre": str(e),
            "anio": e.anio,
            "cuatrimestre": e.cuatrimestre,
        }
        for e in espacios
    ]
    return JsonResponse({"items": data})

@require_GET
def api_correlatividades_por_materia(request):
    materia_id = request.GET.get('materia_id')
    plan_id = request.GET.get('plan_id')

    if not materia_id or not plan_id:
        return JsonResponse({'error': 'materia_id and plan_id are required'}, status=400)

    try:
        materia_principal = EspacioCurricular.objects.get(id=materia_id)
        plan = PlanEstudios.objects.get(id=plan_id)
    except (EspacioCurricular.DoesNotExist, PlanEstudios.DoesNotExist):
        return JsonResponse({'error': 'Materia or Plan not found'}, status=404)

    regulares_ids = Correlatividad.objects.filter(
        plan=plan,
        espacio=materia_principal,
        requisito='REGULARIZADA'
    ).values_list('requiere_espacio__id', flat=True)

    aprobadas_ids = Correlatividad.objects.filter(
        plan=plan,
        espacio=materia_principal,
        requisito='APROBADA'
    ).values_list('requiere_espacio__id', flat=True)

    return JsonResponse({
        'regulares': list(regulares_ids),
        'aprobadas': list(aprobadas_ids)
    })
