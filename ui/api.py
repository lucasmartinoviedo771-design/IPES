from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from django.apps import apps

PlanEstudios = apps.get_model("academia_core", "PlanEstudios")

@login_required
@require_GET
def api_planes_por_profesorado(request):
    prof_id = request.GET.get("prof_id")
    if not prof_id:
        return JsonResponse({"items": []})
    
    planes = PlanEstudios.objects.filter(profesorado_id=prof_id, vigente=True).order_by("-resolucion")
    data = [{"id": p.id, "label": str(p)} for p in planes]
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