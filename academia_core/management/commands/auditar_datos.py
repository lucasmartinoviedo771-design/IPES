from django.core.management.base import BaseCommand
from decimal import Decimal
from academia_core.models import EstudianteProfesorado, Movimiento


class Command(BaseCommand):
    help = (
        "Audita notas textuales, promedios cacheados y regularidades vencidas (2 años)."
    )

    def handle(self, *args, **opts):
        # 1) Normaliza nota_texto -> nota_num cuando sea convertible
        corr_numeros = 0
        movs = Movimiento.objects.all()
        for m in movs:
            if m.nota_num is None and m.nota_texto:
                try:
                    n = int("".join(ch for ch in m.nota_texto if ch.isdigit()))
                    if 0 <= n <= 10:
                        m.nota_num = Decimal(n)
                        m.save(update_fields=["nota_num"])
                        corr_numeros += 1
                except Exception:
                    pass
        self.stdout.write(f"Notas textuales convertidas -> num: {corr_numeros}")

        # 2) Recalcula promedios cacheados
        recalc = 0
        for insc in EstudianteProfesorado.objects.all():
            insc.recalcular_promedio()
            recalc += 1
        self.stdout.write(f"Promedios recalculados: {recalc}")

        self.stdout.write(self.style.SUCCESS("Auditoría terminada (soft)."))
