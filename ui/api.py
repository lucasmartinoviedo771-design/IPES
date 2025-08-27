from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.apps import apps

# ==== CONFIGURÁ ESTAS DOS CONSTANTES (una vez) ====
APP_LABEL = "academia_core"
PLAN_MODEL = "PlanEstudios"
ESPACIO_MODEL = "EspacioCurricular"
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

@login_required
@require_GET
def api_materias_por_plan(request):
    plan_id = request.GET.get("plan_id")
    if not plan_id:
        return JsonResponse({"items": []})

    Plan = apps.get_model(APP_LABEL, PLAN_MODEL)
    Espacio = apps.get_model(APP_LABEL, ESPACIO_MODEL)

    try:
        plan = Plan.objects.get(pk=plan_id)
    except Plan.DoesNotExist:
        return JsonResponse({"items": []})

    qs = Espacio.objects.filter(plan=plan).order_by("anio", "nombre")
    data = [{"id": e.pk, "label": str(e)} for e in qs]
    return JsonResponse({"items": data})
