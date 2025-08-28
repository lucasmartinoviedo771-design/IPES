from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group

class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')

    def test_dashboard_view_redirects_for_student(self):
        # Un usuario con rol de estudiante es redirigido
        student_group = Group.objects.create(name="Estudiante")
        self.user.groups.add(student_group)
        self.user.perfil.rol = 'ESTUDIANTE'
        self.user.perfil.save()

        session = self.client.session
        session['active_role'] = 'ESTUDIANTE'
        session.save()

        response = self.client.get(reverse("ui:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("ui:carton_estudiante"))

    def test_dashboard_view_for_staff(self):
        # Un usuario staff (no estudiante) ve el dashboard
        staff_group = Group.objects.create(name="Bedel")
        self.user.groups.add(staff_group)
        self.user.perfil.rol = 'BEDEL'
        self.user.perfil.save()

        session = self.client.session
        session['active_role'] = 'BEDEL'
        session.save()

        response = self.client.get(reverse("ui:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ui/dashboard.html")

    def test_dashboard_view_unauthenticated(self):
        self.client.logout()
        response = self.client.get(reverse("ui:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'{reverse("login")}?next={reverse("ui:dashboard")}')
