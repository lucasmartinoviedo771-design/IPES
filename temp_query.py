from academia_core.models import Profesorado, PlanEstudios

profesorados = Profesorado.objects.all().order_by('nombre')

output = []
for prof in profesorados:
    output.append(f"Profesorado: {prof.nombre}")
    planes = prof.planes.all().order_by('resolucion')
    if planes:
        for plan in planes:
            output.append(f"  - Plan: {plan.nombre} (Resolucion: {plan.resolucion}, Vigente: {plan.vigente})")
    else:
        output.append("  (No hay planes definidos para este profesorado)")
print("\n".join(output))