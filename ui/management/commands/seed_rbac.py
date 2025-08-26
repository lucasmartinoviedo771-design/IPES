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

ALIAS = {
    # Calificaciones / Notas / Evaluaciones
    "view_calificacion": ["view_calificacion", "view_nota", "view_evaluacion", "view_acta", "view_detallecalificacion"],
    "add_calificacion":  ["add_calificacion",  "add_nota",  "add_evaluacion",  "add_acta",  "add_detallecalificacion"],
    "change_calificacion":["change_calificacion","change_nota","change_evaluacion","change_acta","change_detallecalificacion"],

    # Comisiones / Cursos / Secciones
    "view_comision": ["view_comision", "view_comisioncursada", "view_curso", "view_seccion"],
    "add_comision":  ["add_comision",  "add_comisioncursada",  "add_curso",  "add_seccion"],
    "change_comision":["change_comision","change_comisioncursada","change_curso","change_seccion"],

    # Inscripción a Materia / Cursada
    "view_inscripcionmateria":   ["view_inscripcionmateria", "view_inscripcioncursada", "view_inscripcion"],
    "add_inscripcionmateria":    ["add_inscripcionmateria",  "add_inscripcioncursada",  "add_inscripcion"],
    "change_inscripcionmateria": ["change_inscripcionmateria","change_inscripcioncursada","change_inscripcion"],

    # Periodo / Ciclo / PeriodoLectivo / Term
    "view_periodo":  ["view_periodo", "view_periodolectivo", "view_ciclo", "view_term"],
    "add_periodo":   ["add_periodo",  "add_periodolectivo",  "add_ciclo",  "add_term"],
    "change_periodo":["change_periodo","change_periodolectivo","change_ciclo","change_term"],

    # Ventana / VentanaInscripcion
    "view_ventana":  ["view_ventana", "view_ventanainscripcion"],
    "add_ventana":   ["add_ventana",  "add_ventanainscripcion"],
    "change_ventana":["change_ventana","change_ventanainscripcion"],

    # Inscripción a Carrera / Programa
    "view_inscripcioncarrera":  ["view_inscripcioncarrera", "view_inscripcionprograma"],
    "add_inscripcioncarrera":   ["add_inscripcioncarrera",  "add_inscripcionprograma"],
    "change_inscripcioncarrera":["change_inscripcioncarrera","change_inscripcionprograma"],
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
            # Resolve alias
            real_codenames = ALIAS.get(code, [code])
            for real_code in real_codenames:
                found = list(Permission.objects.filter(codename=real_code))
                if not found:
                    # This is not a fatal error, just a warning if an alias is not found
                    pass
                resolved.extend(found)
        
        # Use a set to remove duplicates
        unique_resolved = sorted(list(set(resolved)), key=lambda p: p.codename)

        group.permissions.set(unique_resolved)

        for p in unique_resolved:
            self.stdout.write(f"  OK {group.name} + {p.content_type.app_label}.{p.codename}")

        self.stdout.write(self.style.SUCCESS(f"Asignados {len(unique_resolved)} permisos a {group.name}"))
