from django.core.management.base import BaseCommand
from academia_core.models import PlanEstudios, EspacioCurricular, Correlatividad


class Command(BaseCommand):
    help = "Carga correlatividades básicas por plan (ajustá a tu malla real)."

    def handle(self, *args, **opts):
        # Elegí el plan vigente que quieras configurar
        plan = (
            PlanEstudios.objects.filter(vigente=True)
            .select_related("profesorado")
            .order_by("-id")
            .first()
        )
        if not plan:
            self.stdout.write(self.style.ERROR("No hay PlanEstudios vigente."))
            return

        # Limpio reglas previas para evitar duplicados
        Correlatividad.objects.filter(plan=plan).delete()

        esp = EspacioCurricular.objects.filter(plan=plan).order_by(
            "anio", "cuatrimestre", "nombre"
        )

        # Helper por año
        esp_por_anio = {}
        for e in esp:
            esp_por_anio.setdefault(e.anio, []).append(e)

        # Regla tipo: para CURSAR 2º -> tener REGULARIZADA TODO 1º
        for e in esp_por_anio.get("2°", []):
            Correlatividad.objects.create(
                plan=plan,
                espacio=e,
                tipo="CURSAR",
                requisito="REGULARIZADA",
                requiere_todos_hasta_anio=1,
            )

        # Para CURSAR 3º -> REGULARIZADA TODO 1º y 2º
        for e in esp_por_anio.get("3°", []):
            Correlatividad.objects.create(
                plan=plan,
                espacio=e,
                tipo="CURSAR",
                requisito="REGULARIZADA",
                requiere_todos_hasta_anio=2,
            )

        # Para CURSAR 4º -> REGULARIZADA TODO 1º..3º
        for e in esp_por_anio.get("4°", []):
            Correlatividad.objects.create(
                plan=plan,
                espacio=e,
                tipo="CURSAR",
                requisito="REGULARIZADA",
                requiere_todos_hasta_anio=3,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Correlatividades base cargadas. Ajustá y re-ejecutá si hace falta."
            )
        )
