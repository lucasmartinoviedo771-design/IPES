import csv
from django.core.management.base import BaseCommand, CommandError
from academia_core.models import Profesorado, PlanEstudios, EspacioCurricular


class Command(BaseCommand):
    help = "Importa espacios curriculares a un Plan de Estudios desde un CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--profesorado", required=True, help="Nombre exacto del profesorado"
        )
        parser.add_argument(
            "--resolucion", required=True, help="Resolución del plan (ej. 1935/14)"
        )
        parser.add_argument(
            "--csv",
            required=True,
            help="Ruta al CSV con anio,cuatrimestre,formato,nombre,horas",
        )

    def handle(self, *args, **opts):
        prof_name = opts["profesorado"]
        resol = opts["resolucion"]
        csv_path = opts["csv"]

        try:
            p = Profesorado.objects.get(nombre=prof_name)
        except Profesorado.DoesNotExist:
            raise CommandError(f"Profesorado no encontrado: {prof_name}")

        plan, _ = PlanEstudios.objects.get_or_create(
            profesorado=p, resolucion=resol, defaults={"vigente": True}
        )

        requeridos = {"anio", "cuatrimestre", "formato", "nombre", "horas"}
        mapa_cuatri = {
            "A": "A",
            "ANUAL": "A",
            "1": "1",
            "1º": "1",
            "1°": "1",
            "PRIMERO": "1",
            "2": "2",
            "2º": "2",
            "2°": "2",
            "SEGUNDO": "2",
        }

        creados = 0
        with open(
            csv_path, newline="", encoding="utf-8-sig"
        ) as f:  # acepta UTF-8 y UTF-8 con BOM
            rdr = csv.DictReader(f)
            if set(rdr.fieldnames or []) != requeridos:
                raise CommandError(
                    f"Encabezados inválidos. Deben ser: {','.join(sorted(requeridos))}"
                )

            for i, row in enumerate(rdr, start=2):
                anio = row["anio"].strip()
                token = row["cuatrimestre"].strip().upper()
                cuatri = mapa_cuatri.get(token)
                if cuatri not in {"A", "1", "2"}:
                    raise CommandError(
                        f"Fila {i}: cuatrimestre inválido '{token}'. Use A, 1 o 2."
                    )

                nombre = row["nombre"].strip()
                formato = row["formato"].strip()
                try:
                    horas = int(row["horas"])
                except ValueError:
                    raise CommandError(f"Fila {i}: 'horas' debe ser entero")

                _, created = EspacioCurricular.objects.get_or_create(
                    profesorado=p,
                    plan=plan,
                    anio=anio,
                    cuatrimestre=cuatri,
                    nombre=nombre,
                    defaults={"horas": horas, "formato": formato},
                )
                if created:
                    creados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"OK: {creados} espacios importados para {p.nombre} - Res. {plan.resolucion}"
            )
        )
