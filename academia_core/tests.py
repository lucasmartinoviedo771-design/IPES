from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from academia_core.models import (
    Estudiante,
    Profesorado,
    PlanEstudios,
    EstudianteProfesorado,
    EspacioCurricular,
    Movimiento,
    Condicion,
    InscripcionEspacio,
    Docente,
    UserProfile,
)


class EstudianteProfesoradoModelTest(TestCase):
    def setUp(self):
        self.estudiante = Estudiante.objects.create(
            dni="12345678", apellido="Perez", nombre="Juan"
        )
        self.profesorado1 = Profesorado.objects.create(nombre="Profesorado de Historia")
        self.profesorado2 = Profesorado.objects.create(
            nombre="Profesorado de Matemática"
        )
        self.plan1_prof1 = PlanEstudios.objects.create(
            profesorado=self.profesorado1, resolucion="Res. 001/2020"
        )
        self.plan2_prof1 = PlanEstudios.objects.create(
            profesorado=self.profesorado1, resolucion="Res. 002/2020"
        )
        self.plan1_prof2 = PlanEstudios.objects.create(
            profesorado=self.profesorado2, resolucion="Res. 003/2020"
        )

    def test_clean_method_valid_plan(self):
        # Plan pertenece al profesorado
        inscripcion = EstudianteProfesorado(
            estudiante=self.estudiante,
            profesorado=self.profesorado1,
            plan=self.plan1_prof1,
            cohorte=2023,
        )
        try:
            inscripcion.full_clean()
        except ValidationError as e:
            self.fail(f"Validación falló inesperadamente: {e}")

    def test_clean_method_invalid_plan(self):
        # Plan no pertenece al profesorado
        inscripcion = EstudianteProfesorado(
            estudiante=self.estudiante,
            profesorado=self.profesorado1,
            plan=self.plan1_prof2,  # Plan de Profesorado2
            cohorte=2023,
        )
        with self.assertRaisesRegex(
            ValidationError, "El plan seleccionado no pertenece al profesorado."
        ):
            inscripcion.full_clean()

    def test_unique_estudiante_plan_constraint(self):
        # Crear una inscripción válida
        EstudianteProfesorado.objects.create(
            estudiante=self.estudiante,
            profesorado=self.profesorado1,
            plan=self.plan1_prof1,
            cohorte=2023,
        )
        # Intentar crear otra inscripción con el mismo estudiante y plan
        with self.assertRaises(IntegrityError):
            EstudianteProfesorado.objects.create(
                estudiante=self.estudiante,
                profesorado=self.profesorado1,
                plan=self.plan1_prof1,
                cohorte=2024,  # Cohorte diferente, pero mismo estudiante y plan
            )

    def test_unique_estudiante_plan_different_plan(self):
        # Crear una inscripción válida
        EstudianteProfesorado.objects.create(
            estudiante=self.estudiante,
            profesorado=self.profesorado1,
            plan=self.plan1_prof1,
            cohorte=2023,
        )
        # Crear otra inscripción con el mismo estudiante pero diferente plan (del mismo profesorado)
        try:
            EstudianteProfesorado.objects.create(
                estudiante=self.estudiante,
                profesorado=self.profesorado1,
                plan=self.plan2_prof1,
                cohorte=2023,
            )
        except IntegrityError:
            self.fail(
                "No debería haber fallado al crear inscripción con diferente plan."
            )


class EspacioCurricularModelTest(TestCase):
    def setUp(self):
        self.profesorado = Profesorado.objects.create(nombre="Profesorado de Historia")
        self.plan = PlanEstudios.objects.create(
            profesorado=self.profesorado, resolucion="Res. 001/2020"
        )

    def test_unique_espacio_plan_nombre_constraint(self):
        EspacioCurricular.objects.create(
            plan=self.plan, nombre="Matemática I", anio="1°", cuatrimestre="1"
        )
        with self.assertRaises(IntegrityError):
            EspacioCurricular.objects.create(
                plan=self.plan,
                nombre="Matemática I",
                anio="2°",
                cuatrimestre="1",  # Mismo plan y nombre
            )

    def test_anio_valido_constraint(self):
        # Año válido
        EspacioCurricular.objects.create(
            plan=self.plan, nombre="Historia I", anio="1°", cuatrimestre="1"
        )
        # Año inválido
        with self.assertRaises(IntegrityError):
            EspacioCurricular.objects.create(
                plan=self.plan, nombre="Historia V", anio="5°", cuatrimestre="1"
            )


class MovimientoModelTest(TestCase):
    def setUp(self):
        self.estudiante = Estudiante.objects.create(
            dni="111", apellido="Doe", nombre="John"
        )
        self.profesorado = Profesorado.objects.create(nombre="Profesorado de Prueba")
        self.plan = PlanEstudios.objects.create(
            profesorado=self.profesorado, resolucion="Res. Test"
        )
        self.inscripcion = EstudianteProfesorado.objects.create(
            estudiante=self.estudiante,
            profesorado=self.profesorado,
            plan=self.plan,
            cohorte=2023,
        )
        self.espacio = EspacioCurricular.objects.create(
            plan=self.plan, nombre="Materia Test", anio="1°", cuatrimestre="1"
        )
        self.condicion_regular = Condicion.objects.create(
            codigo="REGULAR", nombre="Regular", tipo="REG"
        )
        self.condicion_aprobado = Condicion.objects.create(
            codigo="APROBADO", nombre="Aprobado", tipo="REG"
        )
        self.condicion_final_aprobado = Condicion.objects.create(
            codigo="REGULAR", nombre="Aprobado Final", tipo="FIN"
        )

    def test_clean_method_valid_movimiento(self):
        movimiento = Movimiento(
            inscripcion=self.inscripcion,
            espacio=self.espacio,
            tipo="REG",
            fecha="2023-03-15",
            condicion=self.condicion_regular,
            nota_num=7.0,
        )
        try:
            movimiento.full_clean()
        except ValidationError as e:
            self.fail(f"Validación falló inesperadamente: {e}")

    def test_clean_method_invalid_nota_regular(self):
        movimiento = Movimiento(
            inscripcion=self.inscripcion,
            espacio=self.espacio,
            tipo="REG",
            fecha="2023-03-15",
            condicion=self.condicion_regular,
            nota_num=11.0,  # Nota inválida
        )
        with self.assertRaisesRegex(
            ValidationError, "La nota de Regularidad debe estar entre 0 y 10."
        ):
            movimiento.full_clean()

    def test_clean_method_condicional_promocion(self):
        # Estudiante condicional no puede promocionar
        self.inscripcion.condicion_admin = "CONDICIONAL"
        self.inscripcion.save()
        movimiento = Movimiento(
            inscripcion=self.inscripcion,
            espacio=self.espacio,
            tipo="REG",
            fecha="2023-03-15",
            condicion=self.condicion_aprobado,
            nota_num=8.0,
        )
        with self.assertRaisesRegex(
            ValidationError,
            "Estudiante condicional: no puede quedar Aprobado/Promoción por cursada.",
        ):
            movimiento.full_clean()

    def test_clean_method_final_nota_minima(self):
        movimiento = Movimiento(
            inscripcion=self.inscripcion,
            espacio=self.espacio,
            tipo="FIN",
            fecha="2023-07-20",
            condicion=self.condicion_final_aprobado,
            nota_num=5.0,  # Nota menor a 6
        )
        with self.assertRaisesRegex(
            ValidationError, "Nota de Final por regularidad debe ser >= 6."
        ):
            movimiento.full_clean()

    def test_clean_method_espacio_profesorado_mismatch(self):
        otro_profesorado = Profesorado.objects.create(nombre="Otro Profesorado")
        otro_plan = PlanEstudios.objects.create(
            profesorado=otro_profesorado, resolucion="Res. Otro"
        )
        otro_espacio = EspacioCurricular.objects.create(
            plan=otro_plan, nombre="Otra Materia", anio="1°", cuatrimestre="1"
        )
        movimiento = Movimiento(
            inscripcion=self.inscripcion,
            espacio=otro_espacio,
            tipo="REG",
            fecha="2023-03-15",
            condicion=self.condicion_regular,
            nota_num=7.0,
        )
        with self.assertRaisesRegex(
            ValidationError,
            "El espacio no pertenece al mismo profesorado de la inscripción del estudiante.",
        ):
            movimiento.full_clean()


class PanelViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.login(username="testuser", password="password")

    def test_panel_view_for_student(self):
        # Asignar el rol de estudiante al usuario
        # Esto puede variar dependiendo de cómo hayas implementado los roles
        # Por ejemplo, si usas grupos:
        from django.contrib.auth.models import Group

        student_group = Group.objects.create(name="Estudiante")
        self.user.groups.add(student_group)

        response = self.client.get(reverse("panel"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "panel_estudiante.html")

    def test_panel_correlatividades_view(self):
        response = self.client.get(reverse("panel_correlatividades"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "panel_correlatividades.html")

    def test_panel_horarios_view(self):
        response = self.client.get(reverse("panel_horarios"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "panel_horarios.html")

    def test_panel_docente_view(self):
        # Asignar el rol de docente al usuario
        from django.contrib.auth.models import Group

        docente_group = Group.objects.create(name="Docente")
        self.user.groups.add(docente_group)

        response = self.client.get(reverse("panel_docente"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "panel_docente.html")
