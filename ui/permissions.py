# ui/permissions.py
from django.contrib.auth.mixins import UserPassesTestMixin

class RolesPermitidosMixin(UserPassesTestMixin):
    """
    Permite acceso si el usuario es superusuario o pertenece a alguno de los grupos en `allowed`.
    """
    allowed = {"Admin", "Secretaría", "Bedel"}  # ajustá si lo necesitás

    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        if getattr(u, "is_superuser", False):
            return True
        names = set(u.groups.values_list("name", flat=True))
        return bool(self.allowed & names)

# Alias retrocompatible: cualquier vista que use RolesAllowedMixin seguirá funcionando
class RolesAllowedMixin(RolesPermitidosMixin):
    pass
