# -*- coding: utf-8 -*-
import csv
from django.core.management.base import BaseCommand, CommandError
from academia_core.models import Profesorado, PlanEstudios, EspacioCurricular

HEADER = [
    "profesorado_slug",
    "plan_resolucion",
    "anio",
    "cuatrimestre",
    "espacio_nombre",
    "tipo",
    "requisito",
    "requiere_todos_hasta_anio",
    "requiere_espacio_anio",
    "requiere_espacio_cuatr",
    "requiere_espacio_nombre",
    "observaciones",
]


class Command(BaseCommand):
    help = "Exporta una plantilla CSV con todos los espacios de un plan para cargar correlatividades."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profesorado",
            required=True,
            help="slug del profesorado (p.ej. profesorado-de-educacion-primaria)",
        )
        parser.add_argument(
            "--plan", required=True, help="resolución del plan (p.ej. 1935/14)"
        )
        parser.add_argument("--out", required=True, help="ruta del CSV a generar")

    def handle(self, *args, **opts):
        slug = opts["profesorado"].strip()
        res = opts["plan"].strip()
        out = opts["out"].strip()

        try:
            prof = Profesorado.objects.get(slug=slug)
        except Profesorado.DoesNotExist:
            raise CommandError(f"No existe profesorado con slug='{slug}'")

        try:
            plan = PlanEstudios.objects.get(profesorado=prof, resolucion=res)
        except PlanEstudios.DoesNotExist:
            raise CommandError(f"No existe plan '{res}' para '{prof}'")

        espacios = EspacioCurricular.objects.filter(
            profesorado=prof, plan=plan
        ).order_by("anio", "cuatrimestre", "nombre")

        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            for e in espacios:
                # dos filas por materia como plantilla: una CURSAR, otra RENDIR (vacías para que las completes)
                for tipo in ("CURSAR", "RENDIR"):
                    w.writerow(
                        [
                            prof.slug,
                            plan.resolucion,
                            e.anio,
                            e.cuatrimestre,
                            e.nombre,
                            tipo,
                            "",  # requisito: APROBADA / REGULARIZADA (completar)
                            "",  # requiere_todos_hasta_anio (ej. 1, 2, 3) o vacío si usás 'requiere_espacio_*'
                            "",
                            "",
                            "",  # requiere_espacio_* (anio, cuatr, nombre) si la regla es contra una materia puntual
                            "",  # observaciones (opcional)
                        ]
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Plantilla exportada a {out} ({espacios.count()} espacios x 2 filas)"
            )
        )
