from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

# Mapeo de grupos -> lista de codenames (SOLO codenames, sin app_label)
# Esto hace que funcione aunque tu app NO se llame "academia_core".
GROUPS = {
    "Admin": ["*"],  # todos los permisos

    "Secretaría": [
        # Periodos/Ventanas
        "view_periodo", "add_periodo", "change_periodo",
        "view_ventana", "add_ventana", "change_ventana",

        # Personas
        "view_estudiante", "add_estudiante", "change_estudiante",
        "view_docente", "add_docente", "change_docente",

        # Comisiones / Inscripciones / Calificaciones
        "view_comision", "add_comision", "change_comision",
        "view_inscripcionmateria", "add_inscripcionmateria", "change_inscripcionmateria",
        "view_calificacion", "add_calificacion", "change_calificacion",

        # CUSTOM (deben existir en Meta.permissions de algún modelo)
        "open_close_windows",
        "enroll_others",
        "manage_correlatives",
        "publish_grades",
        "view_any_student_record",
        "edit_student_record",
    ],

    "Bedel": [
        # ABM Estudiantes + ver Docentes
        "view_estudiante", "add_estudiante", "change_estudiante",
        "view_docente",

        # Inscripciones a terceros (materias/mesas/carrera si existe ese modelo)
        "view_inscripcionmateria", "add_inscripcionmateria", "change_inscripcionmateria",
        "enroll_others",
        "view_inscripcioncarrera", "add_inscripcioncarrera", "change_inscripcioncarrera",

        # Calificaciones en borrador (sin publicar)
        "view_calificacion", "add_calificacion", "change_calificacion",

        # Ver cartón/histórico de cualquier estudiante
        "view_any_student_record",
    ],

    "Docente": [
        # Según tu política actual, Docente NO carga notas.
        "view_calificacion",
        "view_estudiante",  # filtrarás “solo sus alumnos” en las vistas
    ],

    "Estudiante": [
        # Inscribirse a sí mismo (custom)
        "enroll_self",
        # Ver su propia ficha: lo resolvés por vista (filtro por request.user)
    ],
}


class Command(BaseCommand):
    help = "Crea grupos y asigna permisos por codename (independiente del app_label)."

    def handle(self, *args, **options):
        # Asegurar grupos
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in GROUPS.keys()}

        # Admin -> todos los permisos
        if "*" in GROUPS["Admin"]:
            all_perms = Permission.objects.all()
            groups["Admin"].permissions.set(all_perms)
            self.stdout.write(self.style.SUCCESS("Admin -> todos los permisos"))
        else:
            self._apply(groups["Admin"], GROUPS["Admin"])

        # Resto
        for gname, codenames in GROUPS.items():
            if gname == "Admin":
                continue
            self._apply(groups[gname], codenames)

        self.stdout.write(self.style.SUCCESS("RBAC sincronizado."))

    def _apply(self, group: Group, codenames: list[str]):
        resolved = []
        for code in codenames:
            found = list(Permission.objects.filter(codename=code))
            if not found:
                self.stdout.write(self.style.WARNING(f"Permiso no encontrado (codename): {code}"))
                continue
            resolved.extend(found)
            for p in found:
                self.stdout.write(f"  OK {group.name} + {p.content_type.app_label}.{p.codename}")
        group.permissions.set(resolved)
        self.stdout.write(self.style.SUCCESS(f"Asignados {len(resolved)} permisos a {group.name}"))