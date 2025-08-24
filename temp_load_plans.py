from academia_core.models import Profesorado, PlanEstudios

data = {
    "Educación Inicial": ["1933/14"],
    "Educación Primaria": ["1935/14"],
    "Educación Especial (Discapacidad Intelectual)": ["1375/20"],
    "Educación Secundaria en Matemática": ["3769/13"],
    "Educación Secundaria en Lengua y Literatura": ["4334/12"],
    "Educación Secundaria en Historia": ["0352/12"],
    "Educación Secundaria en Biología": ["4333/12"],
    "Educación Secundaria en Geografía": ["0335/15", "1368/20"],
    "Certificación Docente para la Educación Secundaria": ["3151/21"],
}

for profesorado_name, plan_resolutions in data.items():
    try:
        profesorado = Profesorado.objects.get(nombre=profesorado_name)
        for resolution in plan_resolutions:
            plan, created = PlanEstudios.objects.get_or_create(
                profesorado=profesorado,
                resolucion=resolution,
                defaults={'nombre': f"Plan {resolution.split('/')[0]}"}
            )
            if created:
                print(f"Plan {plan.resolucion} creado para {profesorado.nombre}")
            else:
                print(f"Plan {plan.resolucion} ya existe para {profesorado.nombre}")
    except Profesorado.DoesNotExist:
        print(f"Profesorado '{profesorado_name}' no encontrado. Saltando.")
    except Exception as e:
        print(f"Error procesando {profesorado_name}: {e}")

print("Carga de datos de planes de estudio completada.")
