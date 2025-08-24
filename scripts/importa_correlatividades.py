import csv, re

from academia_core.models import (
    Profesorado,
    PlanEstudios,
    EspacioCurricular,
    Correlatividad,
)

# === CONFIGURACIÓN ===
PROF_SLUG = "profesorado-de-educacion-primaria"
PLAN_RES = "1935/14"
CSV_PATH = r"C:\proyectos\academia\correlatividades_primaria_1935-14.csv"
SEP = ";"  # cambia a "," si tu CSV usa coma


def split_reqs(s: str):
    """Convierte el texto de requisitos del CSV en una lista de tuplas:
    ('ESP', 'Pedagogía')  -> requisito por espacio
    ('TODOS', 2)          -> 'todos hasta 2°'
    """
    if not s:
        return []
    s = s.strip()
    if not s or s.lower().startswith("ninguna"):
        return []
    s = s.replace("°", "")
    s = re.sub(r"\s*(\+|/|;|,|\sy\s|\sY\s)\s*", ",", s)
    parts = [x.strip(" '\"\t") for x in s.split(",") if x.strip(" '\"\t")]
    out = []
    for x in parts:
        m = re.search(r"todos\s+hasta\s+(\d+)", x.lower())
        if m:
            out.append(("TODOS", int(m.group(1))))
        else:
            out.append(("ESP", x))
    return out


def importar_correlatividades(prof_slug, plan_res, csv_path, sep=";"):
    p = Profesorado.objects.get(slug=prof_slug)
    plan = PlanEstudios.objects.get(profesorado=p, resolucion=plan_res)

    def add_rule(espacio, tipo, requisito, req_tuple):
        if req_tuple[0] == "TODOS":
            n = req_tuple[1]
            obj, created = Correlatividad.objects.update_or_create(
                plan=plan,
                espacio=espacio,
                tipo=tipo,
                requisito=requisito,
                requiere_todos_hasta_anio=n,
                defaults={"requiere_espacio": None, "observaciones": ""},
            )
            return created
        else:
            req_name = req_tuple[1]
            try:
                req_esp = EspacioCurricular.objects.get(
                    profesorado=p, plan=plan, nombre__iexact=req_name
                )
            except EspacioCurricular.DoesNotExist:
                print(f"!! No existe REQUERIDO '{req_name}' para {espacio.nombre}")
                return None
            obj, created = Correlatividad.objects.update_or_create(
                plan=plan,
                espacio=espacio,
                tipo=tipo,
                requisito=requisito,
                requiere_espacio=req_esp,
                requiere_todos_hasta_anio=None,
                defaults={"observaciones": ""},
            )
            return created

    created = updated = errors = 0

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rdr = csv.DictReader(f, delimiter=sep)
        for i, row in enumerate(rdr, start=2):  # encabezado = fila 1
            nombre = (row.get("Espacio Curricular") or row.get("Espacio") or "").strip()
            if not nombre:
                continue
            try:
                esp = EspacioCurricular.objects.get(
                    profesorado=p, plan=plan, nombre__iexact=nombre
                )
            except EspacioCurricular.DoesNotExist:
                print(f"Fila {i}: NO existe espacio '{nombre}' en el plan {plan_res}")
                errors += 1
                continue

            for req in split_reqs(row.get("Para cursar debe tener Regular", "")):
                res = add_rule(esp, "CURSAR", "REGULARIZADA", req)
                if res is None:
                    errors += 1
                else:
                    created += int(res)
                    updated += int(not res)

            for req in split_reqs(row.get("Para cursar debe Aprobar", "")):
                res = add_rule(esp, "CURSAR", "APROBADA", req)
                if res is None:
                    errors += 1
                else:
                    created += int(res)
                    updated += int(not res)

            for req in split_reqs(row.get("Para rendir debe tener aprobada", "")):
                res = add_rule(esp, "RENDIR", "APROBADA", req)
                if res is None:
                    errors += 1
                else:
                    created += int(res)
                    updated += int(not res)

    print(f"OK - Creadas: {created} | Actualizadas: {updated} | Errores: {errors}")


# --- Ejecutar ---
importar_correlatividades(PROF_SLUG, PLAN_RES, CSV_PATH, SEP)
