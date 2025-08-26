from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

ROLES = ["Admin", "Secretaría", "Docente", "Estudiante", "Bedel"]

class Command(BaseCommand):
    help = "Crea los grupos de roles básicos"

    def handle(self, *args, **kwargs):
        for name in ROLES:
            g, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Creado grupo: {name}"))
            else:
                self.stdout.write(f"OK grupo ya existe: {name}"))