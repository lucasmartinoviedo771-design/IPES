# ui/api.py
import logging
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.apps import apps
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

"""
Ajustá estos candidatos si tus modelos/fields tienen otros nombres.
El código probará en orden hasta encontrar el modelo/campo existente.
"""

# Modelos candidatos (app_label, model_name)
CARRERA_MODELS = [
    ("academico", "Carrera"),
    ("academico", "Profesorado"),
    ("ui", "Carrera"),
    ("ui", "Profesorado"),
]
PLAN_MODELS = [
    ("academico", "Plan"),
    ("academico", "PlanEstudio"),
    ("ui", "Plan"),
    ("ui", "PlanEstudio"),
]
ESPACIO_MODELS = [
    ("academico", "Espacio"),
    ("academico", "Materia"),
    ("academico", "Asignatura"),
    ("ui", "Espacio"),
    ("ui", "Materia"),
    ("ui", "Asignatura"),
]

# Campos de etiqueta candidatos para .label (en orden de preferencia)
LABEL_FIELDS = ["nombre", "descripcion", "titulo", "name", "label"]

# FK del Plan → Carrera/Profesorado (names probables)
PLAN_FK_TO_CARRERA = ["carrera", "profesorado", "carrera_fk", "profesorado_fk"]

# FK del Espacio/Materia → Plan
ESPACIO_FK_TO_PLAN = ["plan", "plan_estudio", "plan_fk"]


def _resolve_model(candidates):
    """Devuelve el primer modelo existente de la lista (app_label, model).""" 
    for app_label, model_name in candidates:
        try:
            m = apps.get_model(app_label, model_name)
            if m is not None:
                return m
        except LookupError:
            continue
    return None


def _obj_label(obj):
    """Intenta LABEL_FIELDS; si no, usa str(obj).""" 
    for f in LABEL_FIELDS:
        if hasattr(obj, f):
            val = getattr(obj, f)
            return str(val)
    return str(obj)


def _filter_by_fk(model, parent_id, fk_candidates):
    """Devuelve queryset filtrado por el primer FK candidato que exista.""" 
    if not parent_id:
        return model.objects.none()
    for fk_name in fk_candidates:
        # probamos con *_id y sin _id
        if fk_name.endswith("_id"):
            cand = fk_name
        else:
            cand = f"{fk_name}_id"
        try:
            return model.objects.filter(**{cand: parent_id})
        except Exception:
            # Si falla (campo inexistente), probamos sin _id por si es FK directo
            try:
                return model.objects.filter(**{fk_name: parent_id})
            except Exception:
                continue
    # sin match: devolvemos vacío
    return model.objects.none()


def _order_qs(qs):
    """Ordena por 'nombre' si existe; si no, por 'titulo', si no por 'id'.""" 
    for field in ["nombre", "titulo", "descripcion", "id"]:
        try:
            return qs.order_by(field)
        except Exception:
            continue
    return qs


@login_required
@require_GET
def api_planes_por_carrera(request):
    """
    GET /ui/api/planes?prof_id=ID
    Retorna: {"items":[{"id":..., "label":"..."}]}
    """
    prof_id = request.GET.get("prof_id")
    logger.info(f"api_planes_por_carrera: prof_id={prof_id}")

    if not prof_id:
        logger.warning("api_planes_por_carrera: falta prof_id")
        return HttpResponseBadRequest("Falta prof_id")

    try:
        Plan = _resolve_model(PLAN_MODELS)
        if Plan is None:
            logger.error("api_planes_por_carrera: No se encontró el modelo Plan/PlanEstudio.")
            return HttpResponseBadRequest("No encuentro el modelo Plan/PlanEstudio")

        qs = _filter_by_fk(Plan, prof_id, PLAN_FK_TO_CARRERA)
        qs = _order_qs(qs)

        items = [{"id": obj.pk, "label": _obj_label(obj)} for obj in qs]
        logger.info(f"api_planes_por_carrera: {len(items)} planes encontrados.")
        return JsonResponse({"items": items})

    except Exception as e:
        logger.exception("api_planes_por_carrera: error inesperado.")
        return HttpResponseBadRequest(f"Error en servidor: {e}")


@login_required
@require_GET
def api_materias_por_plan(request):
    """
    GET /ui/api/materias?plan_id=ID
    Retorna: {"items":[{"id":..., "label":"..."}]}
    """
    plan_id = request.GET.get("plan_id")
    if not plan_id:
        return HttpResponseBadRequest("Falta plan_id")

    Espacio = _resolve_model(ESPACIO_MODELS)
    if Espacio is None:
        return HttpResponseBadRequest("No encuentro el modelo Espacio/Materia/Asignatura")

    qs = _filter_by_fk(Espacio, plan_id, ESPACIO_FK_TO_PLAN)
    qs = _order_qs(qs)

    items = [{"id": obj.pk, "label": _obj_label(obj)} for obj in qs]
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
    Cor = _resolve_model([("academico", "Correlatividad"), ("ui", "Correlatividad"), ("academia_core", "Correlatividad")])

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

        reg = [{"id": c.requisito.pk, "label": _obj_label(c.requisito)} for c in qs_reg]
        apr = [{"id": c.requisito.pk, "label": _obj_label(c.requisito)} for c in qs_apr]

        logger.info("api_correlatividades_por_espacio: espacio=%s reg=%s apr=%s", esp_id, len(reg), len(apr))
        return JsonResponse({"regular": reg, "aprobada": apr})

    except Exception as e:
        logger.exception(f"api_correlatividades_por_espacio: error para espacio_id={esp_id}")
        return HttpResponseBadRequest(f"Error en servidor: {e}")
