import re
import json

correlativity_text = """
Certificación Docente para la Educación Secundaria (Plan 3151/21)
Primer Año
•Materia: Psicología Educacional (M)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Historia Social Argentina y Latinoamericana (A)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Marco Político Normativo en Educación Secundaria (S)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Curriculum (M)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Pedagogía (A)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Didáctica General (A)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Problemática de la Educación Secundaria (S)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Sujeto de la Educación I (M)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Práctica Profesional I (T)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
Segundo Año
•Materia: Alfabetización Digital (T)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Filosofía de la Educación (M)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Educación Sexual Integral (T)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Ninguna
•Materia: Procesos de Evaluación en la Educación Secundaria (S)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Problemática de la Educación Secundaria (S), Didáctica General (A)
•Materia: Sujeto de la Educación II (M)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Sujeto de la Educación I (M)
•Materia: Didáctica del Nivel Secundario (A)
	oCorrelativas para Cursar:
		•Aprobadas: Ninguna
		•Regularizadas: Didáctica General (A)
•Materia: Práctica Profesional II (T)
	oCorrelativas para Cursar:
		•Aprobadas: Práctica Profesional I (T)
		•Regularizadas: Curriculum (M), Pedagogía (A), Práctica Profesional I (T), Didáctica General (A), Sujeto de la Educación Secundaria I (M)
"""

parsed_data = {}
lines = correlativity_text.strip().split("\n")

# Parse Profesorado and Plan
profesorado_line = lines[0]
profesorado_match = re.match(r"(.+) \(Plan (.+)\)", profesorado_line)
if profesorado_match:
    parsed_data["profesorado"] = profesorado_match.group(1).strip()
    parsed_data["plan_resolucion"] = profesorado_match.group(2).strip()

parsed_data["years"] = []
current_year = None
current_materia = None

for line in lines[1:]:
    line = line.strip()
    if not line:
        continue

    year_match = re.match(r"(.+) Año", line)
    if year_match:
        current_year = {"year_name": line, "espacios": []}
        parsed_data["years"].append(current_year)
        current_materia = None
        continue

    materia_match = re.match(r"•Materia: (.+) \((.+)\)", line)
    if materia_match and current_year:
        current_materia = {
            "name": materia_match.group(1).strip(),
            "format": materia_match.group(2).strip(),
            "correlativas_cursar": {"aprobadas": [], "regularizadas": []},
        }
        current_year["espacios"].append(current_materia)
        continue

    aprobadas_match = re.match(r"•Aprobadas: (.+)", line)
    if aprobadas_match and current_materia:
        aprobadas_text = aprobadas_match.group(1).strip()
        if aprobadas_text.lower() != "ninguna":
            # Extract materia name and format from within the parentheses
            aprobadas_list = []
            # Regex to find "Materia Name (Format)"
            # It handles cases where there might be multiple entries separated by commas
            for item in re.findall(r"([A-Za-zÀ-ÿ\s]+) \(([A-Z])\)", aprobadas_text):
                aprobadas_list.append({"name": item[0].strip(), "format": item[1].strip()})
            current_materia["correlativas_cursar"]["aprobadas"] = aprobadas_list
        continue

    regularizadas_match = re.match(r"•Regularizadas: (.+)", line)
    if regularizadas_match and current_materia:
        regularizadas_text = regularizadas_match.group(1).strip()
        if regularizadas_text.lower() != "ninguna":
            # Extract materia name and format from within the parentheses
            regularizadas_list = []
            for item in re.findall(r"([A-Za-zÀ-ÿ\s]+) \(([A-Z])\)", regularizadas_text):
                regularizadas_list.append({"name": item[0].strip(), "format": item[1].strip()})
            current_materia["correlativas_cursar"]["regularizadas"] = regularizadas_list
        continue

# Write the parsed data to a JSON file
with open("C:\\proyectos\\academia\\parsed_correlatividades.json", "w", encoding="utf-8") as f:
    json.dump(parsed_data, f, indent=2, ensure_ascii=False)