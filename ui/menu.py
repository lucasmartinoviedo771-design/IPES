# ui/menu.py

# === Datos mock (se usan en badges del menú / dashboard) ===
demo = {
    "resumen": {
        "estudiantes": 3,
        "docentes": 9,
        "espacios": 349,
        "inscCarrera": 1,
        "inscMateria": 0,
    },
    "ventanas": {
        "materia": {"abierto": True, "hasta": "12/03 23:59"},
        "final": {"abierto": False, "desde": "18/03 08:00"},
    },
}

def build_menu(role: str):
    """
    Construye el menú por secciones.
    - Se puede filtrar por sección (section["roles"])
    - Y/o por ítem (item["roles"])
    Si no se especifica "roles" ni en sección ni en ítem, el elemento es visible para todos.
    """

    sections = [
        # ===== INICIO =====
        {
            "label": "INICIO",
            "items": [
                # Dashboard: NO para Estudiante
                {
                    "label": "Dashboard",
                    "path": "/dashboard",
                    "icon": "speedometer",
                    "roles": ["Secretaría", "Admin", "Docente", "Bedel"],
                },
            ],
        },

        # ===== ACADÉMICO =====
        {
            "label": "Académico",
            "items": [
                {
                    "label": "Nuevo Estudiante",
                    "path": "/personas/estudiantes/nuevo",
                    "icon": "user-plus",
                    "roles": ["Secretaría", "Admin", "Bedel"],
                },
                {
                    "label": "Inscripción en Profesorado",
                    "path": "/inscripciones/profesorado",
                    "icon": "graduation-cap",
                    "roles": ["Secretaría", "Admin", "Bedel"],
                },
                { "label": "Inscribir a Carrera", "path": "/inscripciones/carrera", "icon": "check", "roles": ["Secretaría","Admin","Bedel"] },
                { "label": "Inscribir a Materias", "path": "/inscripciones/materias", "icon": "book-plus", "roles": ["Secretaría","Admin","Bedel","Estudiante"] },
                {
                    "label": "Inscribir a Mesa de Final",
                    "path": "/inscripciones/mesa-final",
                    "icon": "calendar",
                    "badge": "Abierto" if demo["ventanas"]["final"]["abierto"] else "Cerrado",
                    "roles": ["Secretaría", "Admin", "Bedel", "Estudiante"],
                },
                {
                    "label": "Cargar Notas",
                    "path": "/calificaciones/cargar",
                    "icon": "pencil",
                    "roles": ["Secretaría", "Admin", "Bedel"],
                },
                {
                    "label": "Regularidades",
                    "path": "/calificaciones/regularidades",
                    "icon": "shield",
                    "roles": ["Secretaría", "Admin"],
                },
                {
                    "label": "Correlatividades",
                    "path": "/correlatividades",
                    "icon": "diagram",
                    "roles": ["Secretaría", "Admin"],
                },
                {
                    "label": "Cartón",
                    "path": "/estudiante/carton",
                    "icon": "file-text",
                    "roles": ["Estudiante", "Bedel", "Secretaría", "Admin"],
                },
                {
                    "label": "Histórico",
                    "path": "/estudiante/historico",
                    "icon": "clock",
                    "roles": ["Estudiante", "Bedel", "Secretaría", "Admin"],
                },
            ],
        },

        # ===== PLANIFICACIÓN =====
        {
            "label": "PLANIFICACIÓN",
            "roles": ["Secretaría", "Admin", "Bedel"],
            "items": [
                {"label": "Horarios", "path": "/horarios", "icon": "calendar"},
                {"label": "Espacios Curriculares", "path": "/espacios", "icon": "book"},
                {"label": "Planes de Estudio", "path": "/planes", "icon": "layers"},
            ],
        },

        # ===== PERSONAS =====
        {
            "label": "PERSONAS",
            "roles": ["Secretaría", "Admin", "Bedel"],
            "items": [
                {"label": "Estudiantes", "path": "/estudiantes", "icon": "users", "roles": ["Secretaría","Admin","Bedel"]},
                {"label": "Docentes", "path": "/docentes", "icon": "user", "roles": ["Secretaría","Admin"]},
                {"label": "Nuevo Docente", "path": "/personas/docentes/nuevo", "icon": "plus", "roles": ["Secretaría","Admin"]},
            ],
        },

        # ===== ADMINISTRACIÓN =====
        {
            "label": "ADMINISTRACIÓN",
            "roles": ["Admin"],
            "items": [
                {"label": "Periodos y Fechas", "path": "/periodos", "icon": "hourglass"},
                {"label": "Usuarios y Permisos", "path": "/usuarios", "icon": "lock"},
                {"label": "Parámetros", "path": "/parametros", "icon": "gear"},
                {"label": "Auditoría", "path": "/auditoria", "icon": "history"},
            ],
        },

        # ===== AYUDA =====
        {
            "label": "AYUDA",
            "items": [{"label": "Documentación", "path": "/ayuda", "icon": "help"}],
        },
    ]

    def section_allowed(section) -> bool:
        return ("roles" not in section) or (role in section["roles"])

    def filter_items(items):
        out = []
        for it in items:
            if ("roles" not in it) or (role in it["roles"]):
                out.append(it)
        return out

    result = []
    for sec in sections:
        if not section_allowed(sec):
            continue
        filtered = filter_items(sec["items"])
        if filtered:  # solo mostramos secciones con al menos un item
            result.append({"label": sec["label"], "items": filtered})

    return result
