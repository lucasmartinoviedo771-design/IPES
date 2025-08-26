from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

GROUPS = {
    "Admin": ["*"],

    "Secretaría": [
        # Periodos/Ventanas
        "academia_core.view_periodo", "academia_core.add_periodo", "academia_core.change_periodo",
        "academia_core.view_ventana", "academia_core.add_ventana", "academia_core.change_ventana",
        # Personas
        "academia_core.view_estudiante", "academia_core.add_estudiante", "academia_core.change_estudiante",
        "academia_core.view_docente", "academia_core.add_docente", "academia_core.change_docente",
        # Comisiones / Inscripciones / Calificaciones
        "academia_core.view_comision", "academia_core.add_comision", "academia_core.change_comision",
        "academia_core.view_inscripcionmateria", "academia_core.add_inscripcionmateria", "academia_core.change_inscripcionmateria",
        "academia_core.view_calificacion", "academia_core.add_calificacion", "academia_core.change_calificacion",
        # Custom (si los definiste en Meta.permissions)
        "academia_core.open_close_windows",
        "academia_core.enroll_others",
        "academia_core.manage_correlatives",
        "academia_core.publish_grades",
        "academia_core.view_any_student_record",
        "academia_core.edit_student_record",
    ],

    "Bedel": [
        # Personas
        "academia_core.view_estudiante", "academia_core.add_estudiante", "academia_core.change_estudiante",  # 👈 ABM Estudiantes
        "academia_core.view_docente",  # 👈 ver Docentes

        # Inscripciones a terceros
        "academia_core.view_inscripcionmateria", "academia_core.add_inscripcionmateria", "academia_core.change_inscripcionmateria",
        "academia_core.enroll_others",  # 👈 custom si lo tenés

        # Calificaciones (borrador, sin publicar)
        "academia_core.view_calificacion", "academia_core.add_calificacion", "academia_core.change_calificacion",
        # (no agregar publish_grades para Bedel)

        # Ver ficha/cartón de cualquiera
        "academia_core.view_any_student_record",
    ],

    "Docente": [
        # Si Docente NO carga notas:
        "academia_core.view_calificacion",
        "academia_core.view_estudiante",
        # (sin add/change calificacion, sin publish_grades)
    ],

    "Estudiante": [
        "academia_core.enroll_self",
        # Ver su propio historial se maneja en la vista (filtro por request.user)
    ],
}

class Command(BaseCommand):
    help = "Sets up RBAC permissions for groups"

    def handle(self, *args, **kwargs):
        for group_name, permissions in GROUPS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {group_name}"))
            else:
                self.stdout.write(f"OK group already exists: {group_name}")

            # Clear existing permissions for the group
            group.permissions.clear()

            for perm_codename in permissions:
                if perm_codename == "*": # Wildcard for Admin
                    for p in Permission.objects.all():
                        group.permissions.add(p)
                    self.stdout.write(f"  Added all permissions to {group_name}")
                    break # No need to process other permissions for Admin

                try:
                    app_label, codename = perm_codename.split(".")
                    permission = Permission.objects.get(codename=codename, content_type__app_label=app_label)
                    group.permissions.add(permission)
                    self.stdout.write(f"  Added permission {perm_codename} to {group_name}")
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"  Permission not found: {perm_codename}"))
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"  Invalid permission format: {perm_codename}"))
