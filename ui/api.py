from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.apps import apps
import re

# ==== CONFIGURÁ ESTAS DOS CONSTANTES (una vez) ====
APP_LABEL = "academia_core"
PLAN_MODEL = "PlanEstudios"
ESPACIO_MODEL = "EspacioCurricular"
CORR_MODEL = "Correlatividad"
# ===================================================

@login_required
@require_GET
def api_planes_por_profesorado(request):
    Plan = apps.get_model(APP_LABEL, PLAN_MODEL)

    prof_id = request.GET.get("prof_id")
    if not prof_id:
        return JsonResponse({"items": []})

    # Detecta automáticamente el nombre del FK (profesorado/carrera)
    fk_field = None
    for cand in ("profesorado_id", "carrera_id"):
        if cand in [f.attname for f in Plan._meta.fields]:
            fk_field = cand
            break
    if not fk_field:
        return JsonResponse({"items": [], "error": "FK a profesorado/carrera no encontrada en Plan."})

    qs = Plan.objects.all()
    # Si tu modelo tiene un booleano 'vigente', se filtra
    if "vigente" in [f.name for f in Plan._meta.fields]:
        qs = qs.filter(vigente=True)

    qs = qs.filter(**{fk_field: prof_id}).order_by("nombre")
    data = [{"id": p.pk, "label": str(p)} for p in qs]
    return JsonResponse({"items": data})

@login_required
@require_GET
def api_cohortes_por_plan(request):
    plan_id = request.GET.get("plan_id")
    if not plan_id:
        return JsonResponse({"items": []})
    # TODO: filtrar por tu modelo Cohorte (si existe)
    # cohortes = Cohorte.objects.filter(plan_id=plan_id).order_by("inicio")
    cohortes = []  # ← reemplazar por queryset
    data = [{"id": c.id, "label": str(c)} for c in cohortes]
    return JsonResponse({"items": data})

def _infer_year_from_label(label: str) -> int | None:
    """
    Deducción robusta del año 1..4.
    Regla: tomamos el PRIMER número 1..4 que aparece ANTES de 'año/ano/anual/cuatr...'.
    Soporta: '1° 1º Cuatr.', '3º 2º Cuatr.', '2º Anual', etc.
    """
    s = (label or "").lower()

    # Buscamos la primera ocurrencia de la palabra clave (año/cuatr..)
    kw = re.search(r"(año|ano|anual|cuatr(?:\.|imestre)?)", s)
    seg = s[:kw.start()] if kw else s[:32]  # tomamos el texto hasta ahí (o 32 chars como fallback)

    # En ese segmento tomamos el PRIMER número 1..4 (con o sin º/°/er/ro)
    nums = re.findall(r"([1-4])\s*(?:º|°|er|ro)?", seg)
    if nums:
        try:
            y = int(nums[0])
            return y if y in (1, 2, 3, 4) else None
        except Exception:
            pass

    # Fallback muy laxo: primer dígito 1..4 que aparezca en todo el string
    m = re.search(r"(?:^|\s)([1-4])(?:\D|$)", s)
    return int(m.group(1)) if m else None

@login_required
@require_GET
def api_materias_por_plan(request):
    """
    Devuelve materias del plan ordenadas por año (1..4, otros) y luego por nombre,
    incluyendo el año inferido o del modelo si existe.
    """
    plan_id = request.GET.get("plan_id")
    if not plan_id:
        return JsonResponse({"items": []})

    Plan = apps.get_model(APP_LABEL, PLAN_MODEL)
    Espacio = apps.get_model(APP_LABEL, ESPACIO_MODEL)

    try:
        plan = Plan.objects.get(pk=plan_id)
    except Plan.DoesNotExist:
        return JsonResponse({"items": []})

    qs = Espacio.objects.filter(plan=plan).order_by("nombre")

    # Si tu modelo tiene un campo de año, lo usamos:
    espacio_fields = {f.name for f in Espacio._meta.fields}
    year_field = next((n for n in ("anio", "anio_cursado", "año") if n in espacio_fields), None)

    items = []
    for e in qs:
        label = str(e)
        year = getattr(e, year_field) if year_field else _infer_year_from_label(label)
        items.append({"id": e.pk, "label": label, "year": year})

    # Orden: año (1..4, sino 99) y luego alfabético
    items.sort(key=lambda d: (d["year"] if d["year"] is not None else 99, (d["label"] or "").lower()))
    return JsonResponse({"items": items})

@login_required
@require_GET
def api_correlatividades_por_espacio(request):
    """
    Devuelve ids de correlativas REGULAR/APROBADA ya guardadas para un espacio.
    """
    esp_id = request.GET.get("espacio_id")
    if not esp_id:
        return JsonResponse({"regular": [], "aprobada": []})

    Correlatividad = apps.get_model(APP_LABEL, CORR_MODEL)
    reg = list(
        Correlatividad.objects.filter(espacio_id=esp_id, tipo="CURSAR", requisito="REGULARIZADA")
        .values_list("requiere_espacio_id", flat=True)
    )
    apr = list(
        Correlatividad.objects.filter(espacio_id=esp_id, tipo="CURSAR", requisito="APROBADA")
        .values_list("requiere_espacio_id", flat=True)
    )
    return JsonResponse({"regular": reg, "aprobada": apr})