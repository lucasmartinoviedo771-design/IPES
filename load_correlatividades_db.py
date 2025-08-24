import json
import os
import re
from django.apps import apps

# Configure Django settings (if not already configured)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'academia_project.settings')
import django
django.setup()

from academia_core.models import Profesorado, PlanEstudios, EspacioCurricular, Correlatividad

# Load the parsed JSON data
with open(r'C:\proyectos\academia\parsed_correlatividades.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

profesorado_name = data['profesorado']
plan_resolucion = data['plan_resolucion']

print(f"\n--- Loading Correlativities for {profesorado_name} (Plan {plan_resolucion}) ---")

try:
    profesorado = Profesorado.objects.get(nombre=profesorado_name)
    print(f"Found Profesorado: {profesorado.nombre}")
except Profesorado.DoesNotExist:
    print(f"Error: Profesorado '{profesorado_name}' not found. Please create it first.")
    exit()

try:
    plan = PlanEstudios.objects.get(profesorado=profesorado, resolucion=plan_resolucion)
    print(f"Found Plan de Estudios: {plan.resolucion}")
except PlanEstudios.DoesNotExist:
    print(f"Error: Plan de Estudios '{plan_resolucion}' for {profesorado_name} not found. Please create it first.")
    exit()

for year_data in data['years']:
    year_name = year_data['year_name']
    # Extract year number from 'Primer Año', 'Segundo Año'
    anio_num_match = re.match(r'(.+) Año', year_name)
    if anio_num_match:
        anio_str = anio_num_match.group(1).lower()
        if anio_str == 'primer':
            anio = '1°'
        elif anio_str == 'segundo':
            anio = '2°'
        # Add more years as needed
        else:
            print(f"Warning: Unknown year name '{year_name}'. Skipping spaces for this year.")
            continue
    else:
        print(f"Warning: Could not parse year name '{year_name}'. Skipping spaces for this year.")
        continue

    print(f"\n--- Processing {year_name} ---")
    for espacio_data in year_data['espacios']:
        espacio_name = espacio_data['name'].strip()
        # Remove format from name for matching EspacioCurricular
        espacio_name_for_query = re.sub(r'\s*\([A-Z]\)$', '', espacio_name).strip()

        try:
            # Assuming EspacioCurricular name is unique within a plan and year
            espacio_curricular = EspacioCurricular.objects.get(
                plan=plan, anio=anio, nombre=espacio_name_for_query
            )
            print(f"  Found Espacio Curricular: {espacio_curricular.nombre} ({anio})")
        except EspacioCurricular.DoesNotExist:
            print(f"  Error: Espacio Curricular '{espacio_name_for_query}' (Año {anio}) not found for Plan {plan.resolucion}. Skipping correlativities for this space.")
            continue
        except EspacioCurricular.MultipleObjectsReturned:
            print(f"  Error: Multiple Espacio Curricular objects found for '{espacio_name_for_query}' (Año {anio}) for Plan {plan.resolucion}. Skipping correlativities for this space.")
            continue

        # Process 'Aprobadas' correlativities
        for req_aprobada in espacio_data['correlativas_cursar']['aprobadas']:
            req_espacio_name = req_aprobada['name'].strip()
            req_espacio_name_for_query = re.sub(r'\s*\([A-Z]\)$', '', req_espacio_name).strip()

            try:
                req_espacio_curricular = EspacioCurricular.objects.get(
                    plan=plan, nombre=req_espacio_name_for_query
                )
                correlatividad, created = Correlatividad.objects.get_or_create(
                    plan=plan,
                    espacio=espacio_curricular,
                    tipo="CURSAR",
                    requisito="APROBADA",
                    requiere_espacio=req_espacio_curricular,
                )
                if created:
                    print(f"    Created APROBADA correlativity: {espacio_curricular.nombre} requires {req_espacio_curricular.nombre} (APROBADA)")
                else:
                    print(f"    Correlativity already exists: {espacio_curricular.nombre} requires {req_espacio_curricular.nombre} (APROBADA)")
            except EspacioCurricular.DoesNotExist:
                print(f"    Error: Required Espacio Curricular '{req_espacio_name_for_query}' not found for Plan {plan.resolucion}. Skipping this correlativity.")
            except EspacioCurricular.MultipleObjectsReturned:
                print(f"    Error: Multiple required Espacio Curricular objects found for '{req_espacio_name_for_query}' for Plan {plan.resolucion}. Skipping this correlativity.")

        # Process 'Regularizadas' correlativities
        for req_regularizada in espacio_data['correlativas_cursar']['regularizadas']:
            req_espacio_name = req_regularizada['name'].strip()
            req_espacio_name_for_query = re.sub(r'\s*\([A-Z]\)$', '', req_espacio_name).strip()

            try:
                req_espacio_curricular = EspacioCurricular.objects.get(
                    plan=plan, nombre=req_espacio_name_for_query
                )
                correlatividad, created = Correlatividad.objects.get_or_create(
                    plan=plan,
                    espacio=espacio_curricular,
                    tipo="CURSAR",
                    requisito="REGULARIZADA",
                    requiere_espacio=req_espacio_curricular,
                )
                if created:
                    print(f"    Created REGULARIZADA correlativity: {espacio_curricular.nombre} requires {req_espacio_curricular.nombre} (REGULARIZADA)")
                else:
                    print(f"    Correlativity already exists: {espacio_curricular.nombre} requires {espacio_curricular.nombre} (REGULARIZADA)")
            except EspacioCurricular.DoesNotExist:
                print(f"    Error: Required Espacio Curricular '{req_espacio_name_for_query}' not found for Plan {plan.resolucion}. Skipping this correlativity.")
            except EspacioCurricular.MultipleObjectsReturned:
                print(f"    Error: Multiple required Espacio Curricular objects found for '{req_espacio_name_for_query}' for Plan {plan.resolucion}. Skipping this correlativity.")

print("\n--- Correlativity loading process completed. ---")