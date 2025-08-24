import json
import re

with open(r'C:\proyectos\academia\parsed_correlatividades.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

profesorado_name = data['profesorado']
plan_resolucion = data['plan_resolucion']

missing_espacios = []

for year_data in data['years']:
    year_name = year_data['year_name']
    anio_num_match = re.match(r'(.+) Año', year_name)
    if anio_num_match:
        anio_str = anio_num_match.group(1).lower()
        if anio_str == 'primer':
            anio = '1°'
        elif anio_str == 'segundo':
            anio = '2°'
        else:
            anio = None # Handle other years if necessary
    else:
        anio = None

    if anio:
        for espacio_data in year_data['espacios']:
            espacio_name = espacio_data['name'].strip()
            # Corrected regex: escape parentheses
            espacio_name_for_query = re.sub(r'\s*\([A-Z]\)\'', '', espacio_name).strip()
            espacio_format = espacio_data['format']

            # Assuming cuatrimestre is not directly in the input, or needs to be inferred
            # For now, let's assume a default or leave it for manual input if not provided
            # This part needs careful consideration based on actual data and requirements
            cuatrimestre = "A" # Default to Anual, needs to be confirmed with user or data

            missing_espacios.append({
                'name': espacio_name_for_query,
                'anio': anio,
                'cuatrimestre': cuatrimestre, # This needs to be accurate
                'format': espacio_format # Store format for reference
            })

# Remove duplicates
unique_espacios = []
seen = set()
for esp in missing_espacios:
    esp_tuple = (esp['name'], esp['anio'], esp['cuatrimestre'])
    if esp_tuple not in seen:
        unique_espacios.append(esp)
        seen.add(esp_tuple)

# Print as Python code to create objects
print(f"# Missing EspacioCurricular objects for {profesorado_name} (Plan {plan_resolucion})")
print(f"# Run this in Django shell or a management command")
print(f"# from academia_core.models import Profesorado, PlanEstudios, EspacioCurricular")
print(f"# prof = Profesorado.objects.get(nombre='{profesorado_name}')")
print(f"# plan = PlanEstudios.objects.get(profesorado=prof, resolucion='{plan_resolucion}')")

for esp in unique_espacios:
    # Placeholder for hours and libre_habilitado
    print(f"EspacioCurricular.objects.get_or_create(")
    print(f"    plan=plan,")
    print(f"    anio='{esp['anio']}',")
    print(f"    cuatrimestre='{esp['cuatrimestre']}',")
    print(f"    nombre='{esp['name']}',")
    print(f"    defaults={{ 'horas': 0, 'formato': '{esp['format']}', 'libre_habilitado': False }}")
    print(f")")