# academia_core/signals.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import Actividad

def _rol_de(user):
    perfil = getattr(user, "perfil", None)
    return getattr(perfil, "rol", "")

@receiver(user_logged_in)
def _on_login(sender, user, **kwargs):
    try:
        Actividad.objects.create(user=user, rol_cache=_rol_de(user),
                                 accion="LOGIN", detalle="Ingreso al sistema")
    except Exception:
        pass

@receiver(user_logged_out)
def _on_logout(sender, user, **kwargs):
    try:
        Actividad.objects.create(user=user, rol_cache=_rol_de(user),
                                 accion="LOGOUT", detalle="Salida del sistema")
    except Exception:
        pass
