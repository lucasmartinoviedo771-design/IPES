from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class StaffOrGroupsRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Permite acceso a staff/superuser o a usuarios que pertenezcan a alguno
    de los grupos indicados en `allowed_groups`.
    """

    allowed_groups: tuple[str, ...] = ()

    def test_func(self):
        u = self.request.user
        if not u.is_authenticated:
            return False
        if u.is_staff or u.is_superuser:
            return True
        if not self.allowed_groups:
            return False
        return u.groups.filter(name__in=self.allowed_groups).exists()
