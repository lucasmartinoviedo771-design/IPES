from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from django.shortcuts import get_object_or_404
from academia_core.models import EspacioCurricular, PlanEstudios, Estudiante
from academia_core.eligibilidad import habilitado
from django.apps import apps

InscripcionEspacio = apps.get_model("academia_core", "InscripcionEspacio") or \
                     apps.get_model("academia_core", "InscripcionCursada") or \
                     apps.get_model("academia_core", "InscripcionMateria")

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
        row = {"id": e.id, "nombre": e.nombre, "anio": getattr(e, "anio", None), "habilitado": ok}
        if not ok:
            row["bloqueo"] = info
        items.append(row)
    return JsonResponse({"items": items})

@require_POST
def api_inscribir_espacio(request):
    if InscripcionEspacio is None:
        return JsonResponse({"ok": False, "error": "No existe el modelo de inscripción a cursada."}, status=500)

    est = int(request.POST["estudiante_id"])
    plan = int(request.POST["plan_id"])
    esp  = int(request.POST["espacio_id"])
    ciclo = request.POST.get("ciclo")
    ciclo = int(ciclo) if (ciclo and ciclo.isdigit()) else None

    e = get_object_or_404(EspacioCurricular, id=esp, plan_id=plan)
    ok, info = habilitado(est, plan, e, "PARA_CURSAR", ciclo)
    if not ok:
        return JsonResponse({"ok": False, "error": info}, status=400)

    # obtener nombres de campos por introspección (estudiante/espacio/plan/ciclo)
    def fk_name_to(model, related):
        for f in model._meta.get_fields():
            if getattr(f, "is_relation", False) and getattr(f, "many_to_one", False) and f.related_model is related:
                return f.name
        return None

    fk_est = fk_name_to(InscripcionEspacio, Estudiante) or "estudiante"
    fk_esp = fk_name_to(InscripcionEspacio, EspacioCurricular) or "espacio"
    fk_plan = fk_name_to(InscripcionEspacio, PlanEstudios) or "plan"
    f_ciclo = "ciclo" if "ciclo" in {f.name for f in InscripcionEspacio._meta.get_fields()} else None

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
