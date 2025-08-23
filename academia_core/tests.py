from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

class PanelViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')

    def test_panel_view_for_student(self):
        # Asignar el rol de estudiante al usuario
        # Esto puede variar dependiendo de cómo hayas implementado los roles
        # Por ejemplo, si usas grupos:
        from django.contrib.auth.models import Group
        student_group = Group.objects.create(name='Estudiante')
        self.user.groups.add(student_group)

        response = self.client.get(reverse('panel'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel_estudiante.html')

    def test_panel_correlatividades_view(self):
        response = self.client.get(reverse('panel_correlatividades'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel_correlatividades.html')

    def test_panel_horarios_view(self):
        response = self.client.get(reverse('panel_horarios'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel_horarios.html')

    def test_panel_docente_view(self):
        # Asignar el rol de docente al usuario
        from django.contrib.auth.models import Group
        docente_group = Group.objects.create(name='Docente')
        self.user.groups.add(docente_group)

        response = self.client.get(reverse('panel_docente'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'panel_docente.html')