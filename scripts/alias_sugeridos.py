import csv, re, unicodedata, difflib
from collections import defaultdict
from academia_core.models import Profesorado, PlanEstudios, EspacioCurricular

PROF_SLUG = "profesorado-de-educacion-primaria"
PLAN_RES = "1935/14"
CSV_PATH = r"C:\proyectos\academia\correlatividades_primaria_1935-14.csv"
SEP = ";"  # cambia si tu CSV usa coma


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(s.split())


def split_reqs(s):
    if not s:
        return []
    s = s.strip()
    if not s or s.lower().startswith("ninguna"):
        return []
    s = s.replace("°", "")
    s = re.sub(r"\s*(\+|/|;|,|\sy\s|\sY\s)\s*", ",", s)
    return [x.strip(" '\"\t") for x in s.split(",") if x.strip(" '\"\t")]


p = Profesorado.objects.get(slug=PROF_SLUG)
plan = PlanEstudios.objects.get(profesorado=p, resolucion=PLAN_RES)

espacios = list(EspacioCurricular.objects.filter(profesorado=p, plan=plan))
nombres = [e.nombre for e in espacios]
n_norm = {norm(e.nombre): e.nombre for e in espacios}


def sugerir_alias(cad):
    n = norm(cad)
    if n in n_norm:
        return n_norm[n]
    # mejores coincidencias por similitud
    m = difflib.get_close_matches(cad, nombres, n=3, cutoff=0.5)
    if m:
        return m[0]
    # intentar por palabra clave normalizada
    cands = [nom for nom in nombres if n in norm(nom)]
    if len(cands) == 1:
        return cands[0]
    return None


usados = set()
sugerencias = defaultdict(set)

with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
    rdr = csv.DictReader(f, delimiter=SEP)
    for row in rdr:
        for col in (
            "Para cursar debe tener Regular",
            "Para cursar debe Aprobar",
            "Para rendir debe tener aprobada",
        ):
            for req in split_reqs(row.get(col, "")):
                if not req:
                    continue
                key = norm(req)
                if key in usados:
                    continue
                usados.add(key)
                sug = sugerir_alias(req)
                if sug:
                    sugerencias[sug].add(req)

print("=== Alias sugeridos (CSV -> DB) ===")
for sug, origs in sorted(sugerencias.items(), key=lambda x: x[0]):
    for o in sorted(origs):
        if norm(o) != norm(sug):
            print(f"'{o}'  ->  '{sug}'")
