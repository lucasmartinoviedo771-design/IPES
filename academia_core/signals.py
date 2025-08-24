# academia_core/signals.py

from django.apps import apps
from django.dispatch import receiver

# ¡Importante! Faltaba importar las señales de autenticación
from django.contrib.auth.signals import user_logged_in, user_logged_out

# No obtengas los modelos aquí arriba


def _rol_de(user):
    perfil = getattr(user, "perfil", None)
    return getattr(perfil, "rol", "")


@receiver(user_logged_in)
def _on_login(sender, user, **kwargs):
    # Obtén el modelo JUSTO cuando lo necesites
    Actividad = apps.get_model("academia_core", "Actividad")

    try:
        Actividad.objects.create(
            user=user,
            rol_cache=_rol_de(user),
            accion="LOGIN",
            detalle="Ingreso al sistema",
        )
    except Exception:
        # Es mejor registrar el error que dejar un 'pass' vacío
        # import logging
        # logging.exception("No se pudo crear la actividad de LOGIN")
        pass


@receiver(user_logged_out)
def _on_logout(sender, user, **kwargs):
    # Obtén el modelo JUSTO cuando lo necesites
    Actividad = apps.get_model("academia_core", "Actividad")

    try:
        Actividad.objects.create(
            user=user,
            rol_cache=_rol_de(user),
            accion="LOGOUT",
            detalle="Salida del sistema",
        )
    except Exception:
        pass
