# ui/api.py
import logging
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.http import JsonResponse, HttpResponseBadRequest
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ============ Helpers robustos ============ 
def _best_label(obj):
    """
    Construye una etiqueta legible sin importar cómo se llame el campo.
    Prioriza 'nombre', luego 'descripcion', 'titulo', 'resolucion' y termina en str(obj).
    """
    for attr in ("nombre", "name", "descripcion", "descripcion_corta", "titulo", "resolucion"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if val:
                return str(val)
    return str(obj)

def _find_plan_model():
    """
    Busca un modelo que represente 'Plan' (PlanEstudio/Plan/etc.) con un FK a Profesorado/Carrera.
    """
    candidates = []
    for m in apps.get_models():
        n = m.__name__.lower()
        # el nombre del modelo debe insinuar que es un plan
        if "plan" in n:
            # Heurística: que tenga algún FK que suene a profesorados/carreras
            fks = [f for f in m._meta.get_fields() if getattr(f, "many_to_one", False)]
            for fk in fks:
                fkname = fk.name.lower()
                target = fk.related_model.__name__.lower()
                if any(k in fkname for k in ("prof", "carr")) or any(k in target for k in ("prof", "carr")):
                    candidates.append(m)
                    break
    # si hay muchos, priorizo los que incluyan 'estudio' en el nombre
    for m in candidates:
        if "estudio" in m.__name__.lower():
            return m
    return candidates[0] if candidates else None

def _find_espacio_model():
    """
    Busca un modelo de 'materias/espacios/asignaturas' asociado a Plan.
    """
    for m in apps.get_models():
        n = m.__name__.lower()
        if any(k in n for k in ("espacio", "materia", "asignatura")):
            # que tenga FK a un modelo cuyo nombre contenga 'plan'
            fks = [f for f in m._meta.get_fields() if getattr(f, "many_to_one", False)]
            for fk in fks:
                target = fk.related_model.__name__.lower()
                if "plan" in target:
                    return m
    # fallback: el primero que tenga muchos campos tipo 'anio', 'cuatrimestre' y algún FK a plan
    for m in apps.get_models():
        n = m.__name__.lower()
        if any(k in n for k in ("espacio", "materia", "asignatura")):
            return m
    return None

def _first_matching_fk_name(model, *candidates):
    """
    Devuelve el nombre de FK del 'model' cuyo nombre coincida con alguno de 'candidates'.
    Si no hay match exacto, intenta por el modelo de destino (profesorado/carrera/plan).
    """
    fks = [f for f in model._meta.get_fields() if getattr(f, "many_to_one", False)]
    # 1) por nombre del campo
    for wanted in candidates:
        for fk in fks:
            if fk.name.lower() == wanted.lower():
                return fk.name
    # 2) por nombre del modelo de destino
    for fk in fks:
        target = fk.related_model.__name__.lower()
        for wanted in candidates:
            if wanted.lower() in target:
                return fk.name
    # 3) por heurística: el primero que “suena”
    for fk in fks:
        nm = fk.name.lower()
        if any(k in nm for k in candidates):
            return fk.name
    return fks[0].name if fks else None

# ============ Endpoints ============ 

@login_required
@require_GET
def api_planes_por_carrera(request):
    """
    GET /ui/api/planes?prof_id=<id>
    Devuelve: {"items":[{"id":..., "label":"..."}]}
    """
    prof_id = request.GET.get("prof_id")
    if not prof_id:
        return HttpResponseBadRequest("Falta prof_id")

    PlanModel = _find_plan_model()
    if not PlanModel:
        logger.error("No se pudo inferir el modelo de Plan (Plan/PlanEstudio).")
        return HttpResponseBadRequest("No se pudo inferir el modelo de Plan.")

    fk_name = _first_matching_fk_name(PlanModel, "profesorado", "carrera", "titulo", "prof")
    logger.debug("PlanModel=%s, FK a profesorados=%s", PlanModel.__name__, fk_name)

    qs = PlanModel.objects.all()
    # filtrar por el FK descubierto
    if fk_name:
        qs = qs.filter(**{f"{fk_name}_id": prof_id})

    # filtros típicos de soft delete / activo si existieran
    if hasattr(PlanModel, "activo"):
        qs = qs.filter(activo=True)
    if hasattr(PlanModel, "is_active"):
        qs = qs.filter(is_active=True)

    planes_qs = qs.order_by("pk")
    items = []
    for p in planes_qs:
        # Ajustá estos getattr a tus campos reales
        nombre = getattr(p, "nombre", None) or str(p)
        resol  = getattr(p, "resolucion", "") or getattr(p, "codigo", "")
        anio   = getattr(p, "anio", "")

        partes = [nombre]
        if resol:
            partes.append(f"Res. {resol}")
        if anio:
            partes.append(str(anio))

        label = " — ".join(partes)
        items.append({"id": p.id, "label": label})

    return JsonResponse({"items": items})

@login_required
@require_GET
def api_materias_por_plan(request):
    """
    GET /ui/api/materias?plan_id=<id>
    Devuelve: {"items":[{"id":..., "label":"..."}]}
    """
    plan_id = request.GET.get("plan_id")
    if not plan_id:
        return HttpResponseBadRequest("Falta plan_id")

    EspacioModel = _find_espacio_model()
    PlanModel   = _find_plan_model()
    if not EspacioModel or not PlanModel:
        logger.error("No se pudieron inferir modelos de Espacio/Materia o Plan.")
        return HttpResponseBadRequest("No se pudieron inferir modelos (Materias/Plan).")

    fk_name = _first_matching_fk_name(EspacioModel, "plan", "plan_estudio", "planestudio")
    logger.debug("EspacioModel=%s, FK a plan=%s", EspacioModel.__name__, fk_name)

    qs = EspacioModel.objects.all()
    if fk_name:
        qs = qs.filter(**{f"{fk_name}_id": plan_id})

    if hasattr(EspacioModel, "activo"):
        qs = qs.filter(activo=True)
    if hasattr(EspacioModel, "is_active"):
        qs = qs.filter(is_active=True)

    items = [{"id": obj.pk, "label": _best_label(obj)} for obj in qs.order_by("pk")]
    return JsonResponse({"items": items})


@login_required
@require_GET
def api_cohortes_por_plan(request):
    """
    GET /ui/api/cohortes?plan_id=<ID>&start=<YYYY>&end=<YYYY>&order=asc|desc
    - plan_id es opcional (por si algún día quisieras filtrar por plan)
    - start/end y order son opcionales; por defecto 2010..año actual en asc
    Respuesta: {"items": [{"id": 2010, "label": "2010"}, ...]}
    """
    # por defecto, de 2010 hasta el año actual
    start_default = getattr(settings, "COHORTE_START_YEAR", 2010)
    end_default = timezone.now().year

    try:
        start = int(request.GET.get("start", start_default))
        end   = int(request.GET.get("end", end_default))
    except ValueError:
        return HttpResponseBadRequest("Parámetros start/end inválidos")

    if start > end:
        start, end = end, start

    order = request.GET.get("order", "asc").lower().strip()
    years = list(range(start, end + 1))
    if order == "desc":
        years.reverse()

    items = [{"id": y, "label": str(y)} for y in years]
    return JsonResponse({"items": items})


@login_required
@require_GET
def api_correlatividades_por_espacio(request):
    """
    GET /ui/api/correlatividades?espacio_id=<ID>
    Respuesta:
      {"regular": [id_requisito,...], "aprobada": [id_requisito,...]}

    Es robusto: si el modelo no existe aún, devuelve listas vacías (no rompe el frontend).
    """
    esp_id = request.GET.get("espacio_id")
    if not esp_id:
        return HttpResponseBadRequest("Falta espacio_id")

    try:
        esp_id_int = int(esp_id)
    except (ValueError, TypeError):
        return HttpResponseBadRequest("espacio_id debe ser un número")

    # Buscamos el modelo Correlatividad en posibles apps
    Cor = None
    for app_label in ("academico", "ui", "academia_core"):
        try:
            Cor = apps.get_model(app_label, "Correlatividad")
            break
        except LookupError:
            continue

    if Cor is None:
        # Aún no creaste el modelo → devolvemos vacío para que el JS no falle
        logger.warning("api_correlatividades_por_espacio: No se encontró el modelo Correlatividad.")
        return JsonResponse({"regular": [], "aprobada": []})

    try:
        # Tipos admitidos (por si en DB usás abreviaturas)
        reg_vals = ["REGULAR", "REG", "regular", "reg"]
        apr_vals = ["APROBADA", "APR", "aprobada", "apr"]

        # Asumiendo que el modelo Correlatividad tiene un FK 'requisito' a Espacio/Materia
        # y un campo de texto 'tipo'
        qs = Cor.objects.filter(espacio_id=esp_id_int).select_related('requisito')

        qs_reg = qs.filter(tipo__in=reg_vals)
        qs_apr = qs.filter(tipo__in=apr_vals)

        reg = [{"id": c.requisito.pk, "label": _best_label(c.requisito)} for c in qs_reg]
        apr = [{"id": c.requisito.pk, "label": _best_label(c.requisito)} for c in qs_apr]

        logger.info("api_correlatividades_por_espacio: espacio=%s reg=%s apr=%s", esp_id, len(reg), len(apr))
        return JsonResponse({"regular": reg, "aprobada": apr})

    except Exception as e:
        logger.exception(f"api_correlatividades_por_espacio: error para espacio_id={esp_id}")
        return HttpResponseBadRequest(f"Error en servidor: {e}")
