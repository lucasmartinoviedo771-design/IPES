# ui/menu.py

# Estructura: lista de secciones. Cada sección tiene un título y sus items.
# Usamos rutas absolutas (strings) para evitar errores de reverse si las views aún son “stub”.

BEDEL_MENU = [
    {
        "title": "INICIO",
        "items": [
            {"label": "Dashboard", "path": "/dashboard", "icon": "home"},
        ],
    },
    {
        "title": "ACADÉMICO",
        "items": [
            {"label": "Estudiante nuevo",        "path": "/personas/estudiantes/nuevo",        "icon": "user-plus"},
            {"label": "Inscribir a Carrera",     "path": "/inscripciones/carrera",    "icon": "check"},
            {"label": "Inscribir a Materias",    "path": "/inscripciones/materia",    "icon": "book-plus",  "badge": {"text": "Abierto",  "tone": "success"}},
            {"label": "Inscribir a Mesa de Final","path": "/inscripciones/mesa-final","icon": "calendar-x", "badge": {"text": "Cerrado",  "tone": "danger"}},
            {"label": "Cartón",                  "path": "/carton",                   "icon": "id-card"},
            {"label": "Histórico",               "path": "/historico",                "icon": "clock"},
        ],
    },
    {
        "title": "PLANIFICACIÓN",
        "items": [
            {"label": "Horarios", "path": "/horarios", "icon": "clock"},
            {"label": "Espacios Curriculares", "path": "/espacios", "icon": "layers"},
            {"label": "Planes de Estudio", "path": "/planes", "icon": "map"},
        ],
    },
    {
        "title": "PERSONAS",
        "items": [
            {"label": "Estudiantes", "path": "/estudiantes", "icon": "users"},
            {"label": "Docentes", "path": "/docentes", "icon": "user"},
            {"label": "Nuevo Estudiante", "path": "/personas/estudiantes/nuevo", "icon": "user-plus"},
        ],
    },
    {
        "title": "AYUDA",
        "items": [
            {"label": "Documentación", "path": "/docs", "icon": "book"},
        ],
    },
]

# Secretaría y Admin ven lo mismo que Bedel + (si tenés) extras.
SECRETARIA_MENU = BEDEL_MENU
ADMIN_MENU = BEDEL_MENU

# Docente y Estudiante (si los necesitás ahora) — simplificados
DOCENTE_MENU = [
    {
        "title": "INICIO",
        "items": [{"label": "Dashboard", "path": "/dashboard", "icon": "home"}],
    },
]
ESTUDIANTE_MENU = [
    {
        "title": "INICIO",
        "items": [{"label": "Dashboard", "path": "/dashboard", "icon": "home"}],
    },
    {
        "title": "ACADÉMICO",
        "items": [
            {"label": "Inscribirme a Materias",     "path": "/inscripciones/materia",    "icon": "book-plus"},
            {"label": "Inscribirme a Mesa de Final","path": "/inscripciones/mesa-final","icon": "calendar-x"},
        ],
    },
    {
        "title": "TRAYECTORIA",
        "items": [
            {"label": "Cartón", "path": "/carton", "icon": "id-card"},
            {"label": "Histórico", "path": "/historico", "icon": "clock"},
        ],
    },
]

def for_role(role: str | None):
    role = (role or "").strip()
    if role == "Admin":
        return ADMIN_MENU
    if role == "Secretaría":
        return SECRETARIA_MENU
    if role == "Bedel":
        return BEDEL_MENU
    if role == "Docente":
        return DOCENTE_MENU
    if role == "Estudiante":
        return ESTUDIANTE_MENU
    # Fallback sensato
    return ESTUDIANTE_MENU