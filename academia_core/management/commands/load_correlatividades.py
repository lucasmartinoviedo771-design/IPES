import csv
from django.core.management.base import BaseCommand, CommandError
from academia_core.models import Correlatividad, PlanEstudios, EspacioCurricular


class Command(BaseCommand):
    help = "Carga/actualiza correlatividades desde un CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    def handle(self, *args, **opts):
        path = opts["csv_path"]
        created = updated = skipped = 0
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    plan_id = row.get("plan_id")
                    esp_id = row.get("espacio_id")
                    req_id = row.get("requiere_espacio_id") or None
                    tipo = (row.get("tipo") or "").strip().upper() or None
                    reqtxt = (row.get("requisito") or "").strip().upper() or None
                    hasta = row.get("requiere_todos_hasta_anio") or None
                    obs = row.get("observaciones") or ""

                    if not plan_id or not esp_id:
                        skipped += 1
                        continue

                    plan = PlanEstudios.objects.get(id=plan_id)
                    esp = EspacioCurricular.objects.get(id=esp_id)
                    req = EspacioCurricular.objects.get(id=req_id) if req_id else None

                    obj, was_created = Correlatividad.objects.get_or_create(
                        plan=plan,
                        espacio=esp,
                        requiere_espacio=req,
                        requiere_todos_hasta_anio=(int(hasta) if hasta else None),
                        defaults={
                            "tipo": tipo,
                            "requisito": reqtxt,
                            "observaciones": obs,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        obj.tipo = tipo
                        obj.requisito = reqtxt
                        obj.observaciones = obs
                        obj.save(update_fields=["tipo", "requisito", "observaciones"])
                        updated += 1
        except FileNotFoundError:
            raise CommandError(f"No se encontró el archivo: {path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Creadas: {created} | Actualizadas: {updated} | Omitidas: {skipped}"
            )
        )
