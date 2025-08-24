from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from academia_core.models import (
    Profesorado,
    PlanEstudios,
    Estudiante,
    EstudianteProfesorado,
    EspacioCurricular,
    Movimiento,
    Docente,
    DocenteEspacio,
    UserProfile,
)


def perms_for(model, kinds=("view",)):
    ct = ContentType.objects.get_for_model(model)
    out = []
    for k in kinds:
        codename = f"{k}_{model._meta.model_name}"
        try:
            out.append(Permission.objects.get(content_type=ct, codename=codename))
        except Permission.DoesNotExist:
            # si falta algún permiso, lo ignoramos
            pass
    return out


class Command(BaseCommand):
    help = "Crea grupos y asigna permisos base para roles."

    def handle(self, *args, **kwargs):
        modelos_catalogo = [
            Profesorado,
            PlanEstudios,
            EspacioCurricular,
            Docente,
            DocenteEspacio,
        ]
        modelos_alumnos = [Estudiante, EstudianteProfesorado, Movimiento]
        perfil = [UserProfile]

        # Grupos
        g_est, _ = Group.objects.get_or_create(name="ESTUDIANTE")
        g_doc, _ = Group.objects.get_or_create(name="DOCENTE")
        g_bed, _ = Group.objects.get_or_create(name="BEDEL")
        g_tut, _ = Group.objects.get_or_create(name="TUTOR")
        g_sec, _ = Group.objects.get_or_create(name="SECRETARIA")

        # ---- Permisos base ----
        view_all = []
        for M in modelos_catalogo + modelos_alumnos:
            view_all += perms_for(M, ("view",))

        # ESTUDIANTE: sin permisos de modelo (verá lo suyo vía vistas)
        g_est.permissions.set([])

        # DOCENTE: solo ver (catálogo + alumnos + movimientos)
        g_doc.permissions.set(view_all)

        # TUTOR: solo ver
        g_tut.permissions.set(view_all)

        # BEDEL: ver + agregar/cambiar en alumnos/movimientos (sin borrar)
        bed_perms = list(view_all)
        for M in modelos_alumnos:
            bed_perms += perms_for(M, ("add", "change"))
        g_bed.permissions.set(bed_perms)

        # SECRETARIA: ver/agregar/cambiar/borrar todo (incluye perfil)
        sec_perms = []
        for M in modelos_catalogo + modelos_alumnos + perfil:
            sec_perms += perms_for(M, ("view", "add", "change", "delete"))
        g_sec.permissions.set(sec_perms)

        self.stdout.write(self.style.SUCCESS("Grupos y permisos creados/asignados."))
