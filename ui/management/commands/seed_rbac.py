# ui/management/commands/seed_rbac.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

# Mapa de grupos -> codenames REALES en tu app (según tu lista)
GROUPS = {
    "Admin": ["*"],

    # Secretaría: gestiona personas, espacios/planes/horarios, correlativas, inscripciones (materia/final/carrera),
    # auditoría básica y permisos custom de operación.
    "Secretaría": [
        # Personas
        "view_estudiante", "add_estudiante", "change_estudiante",
        "view_docente", "add_docente", "change_docente",

        # Planificación / Académico
        "view_espaciocurricular", "add_espaciocurricular", "change_espaciocurricular",
        "view_docenteespacio", "add_docenteespacio", "change_docenteespacio",
        "view_horario", "add_horario", "change_horario",
        "view_planestudios", "add_planestudios", "change_planestudios",
        "view_correlatividad", "add_correlatividad", "change_correlatividad",

        # Inscripciones (materia/espacio – mesa final – carrera)
        "view_inscripcionespacio", "add_inscripcionespacio", "change_inscripcionespacio",
        "view_inscripcionfinal", "add_inscripcionfinal", "change_inscripcionfinal",
        "view_inscripcioncarrera", "add_inscripcioncarrera", "change_inscripcioncarrera",

        # Auditoría / estado
        "view_inscripcionespacioestadolog", "view_movimiento",

        # CUSTOM (creados con CorePerms.managed=False)
        "open_close_windows",        # abrir/cerrar ventanas (si aplica en tu flujo)
        "manage_correlatives",       # gestionar reglas de correlativas (UI/servicio)
        "publish_grades",            # publicar calificaciones (siempre vía Secretaría/Admin)
        "enroll_others",             # inscribir a terceros
        "view_any_student_record",   # ver Cartón/Histórico de cualquier estudiante
        "edit_student_record",       # editar ficha/cartón
    ],

    # Bedel: ABM mínimo de estudiantes + inscribir a terceros (materias/mesas/carrera) + ver docente + ver cartón
    "Bedel": [
        "view_estudiante", "add_estudiante", "change_estudiante",
        "view_docente",

        # Inscribir a terceros
        "view_inscripcionespacio", "add_inscripcionespacio", "change_inscripcionespacio",
        "view_inscripcionfinal", "add_inscripcionfinal", "change_inscripcionfinal",
        "view_inscripcioncarrera", "add_inscripcioncarrera", "change_inscripcioncarrera",

        # Custom
        "enroll_others",
        "view_any_student_record",
    ],

    # Docente: puede ver estudiantes vinculados y sus cursadas/finales + su estructura académica
    "Docente": [
        "view_estudiante",
        "view_inscripcionespacio",
        "view_inscripcionfinal",
        "view_espaciocurricular",
        "view_docenteespacio",
        "view_horario",
    ],

    # Estudiante: solo autoinscripción (el resto se controla por lógica de UI/servicio)
    "Estudiante": [
        "enroll_self",
    ],
}


class Command(BaseCommand):
    help = "Crea grupos y asigna permisos según codenames reales del proyecto."

    def handle(self, *args, **options):
        # Crear grupos si no existen
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in GROUPS.keys()}

        # Admin => todos los permisos
        if "*" in GROUPS["Admin"]:
            all_perms = Permission.objects.all()
            groups["Admin"].permissions.set(all_perms)
            self.stdout.write(self.style.SUCCESS("Admin -> todos los permisos"))
        else:
            self._apply(groups["Admin"], GROUPS["Admin"])

        # Resto de grupos
        for gname, codes in GROUPS.items():
            if gname == "Admin":
                continue
            self._apply(groups[gname], codes)

        self.stdout.write(self.style.SUCCESS("RBAC sincronizado."))

    def _apply(self, group: Group, desired_codenames: list[str]):
        resolved = []
        for code in desired_codenames:
            qs = Permission.objects.filter(codename=code)
            if not qs.exists():
                self.stdout.write(self.style.WARNING(f"Permiso no encontrado (codename): {code}"))
                continue
            for p in qs:
                resolved.append(p)
                self.stdout.write(f"  OK {group.name} + {p.content_type.app_label}.{p.codename}")
        group.permissions.set(resolved)
        self.stdout.write(self.style.SUCCESS(f"Asignados {len(resolved)} permisos a {group.name}"))