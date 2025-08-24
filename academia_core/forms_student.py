from __future__ import annotations

from django import forms
from django.contrib.auth.models import User

from .label_utils import espacio_etiqueta
from .models import (
    Estudiante,
    EstudianteProfesorado,
    EspacioCurricular,
    InscripcionEspacio,
    InscripcionFinal,
)


def _q_inscripciones_del_usuario(user: User):
    """
    Obtiene las inscripciones (EstudianteProfesorado) del estudiante logueado.
    Se admite:
      - relación directa user.estudiante (si existe)
      - buscar por email/username si no hay relación directa
    """
    # Caso 1: relación directa
    est = getattr(user, "estudiante", None)
    if isinstance(est, Estudiante):
        return EstudianteProfesorado.objects.filter(estudiante=est)

    # Caso 2: heurísticas simples por email o username
    qs = EstudianteProfesorado.objects.none()
    try:
        if user.email:
            qs = EstudianteProfesorado.objects.filter(
                estudiante__email__iexact=user.email
            )
        if not qs.exists() and user.username:
            qs = EstudianteProfesorado.objects.filter(estudiante__dni=user.username)
    except Exception:
        pass
    return qs


class StudentInscripcionEspacioForm(forms.ModelForm):
    """
    El propio estudiante se inscribe a un Espacio (cursada).
    - La lista de 'inscripcion' se restringe a sus legajos (EstudianteProfesorado).
    - El select de 'espacio' se filtra por profesorado/plan y usa la ETIQUETA normalizada.
    """

    class Meta:
        model = InscripcionEspacio
        fields = ["inscripcion", "anio_academico", "espacio"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # 1) restringir inscripciones al estudiante logueado
        qs_insc = _q_inscripciones_del_usuario(getattr(self.request, "user", None))
        self.fields["inscripcion"].queryset = qs_insc.order_by("profesorado__nombre")

        # Si tiene una sola inscripción, la fijamos y (opcional) podrías hacerla read-only
        if qs_insc.count() == 1:
            self.fields["inscripcion"].initial = qs_insc.first()

        # 2) etiqueta normalizada para espacio
        if "espacio" in self.fields:
            self.fields["espacio"].label_from_instance = espacio_etiqueta

        # 3) si ya hay inscripción elegida, filtramos los espacios
        insc_id = self.data.get(self.add_prefix("inscripcion")) or self.initial.get(
            "inscripcion"
        )
        if insc_id:
            try:
                insc = EstudianteProfesorado.objects.select_related("profesorado").get(
                    pk=insc_id
                )
            except EstudianteProfesorado.DoesNotExist:
                insc = None
        else:
            insc = (
                self.fields["inscripcion"].initial
                if self.fields["inscripcion"].initial
                else None
            )

        if insc:
            qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
            # Excluir ya inscriptos por esta inscripción
            ya_ids = list(
                InscripcionEspacio.objects.filter(inscripcion=insc).values_list(
                    "espacio_id", flat=True
                )
            )
            if ya_ids:
                qs = qs.exclude(pk__in=ya_ids)
            self.fields["espacio"].queryset = qs.order_by(
                "anio", "cuatrimestre", "nombre"
            )
        else:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí primero una inscripción (legajo)."


class StudentInscripcionFinalForm(forms.ModelForm):
    """
    El propio estudiante se anota a mesa de final.
    Buscamos un FK hacia InscripcionEspacio con tolerancia al nombre del campo (igual que en tu flujo).
    """

    class Meta:
        model = InscripcionFinal
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Encontrar el FK a InscripcionEspacio
        fk = None
        for f in InscripcionFinal._meta.get_fields():
            if (
                getattr(getattr(f, "related_model", None), "__name__", "")
                == "InscripcionEspacio"
            ):
                fk = f.name
                break
        self._fk = fk

        if fk and fk in self.fields:
            # Mostrar por el "espacio" con etiqueta normalizada
            self.fields[fk].label_from_instance = lambda ie: (
                espacio_etiqueta(getattr(ie, "espacio", None))
                if getattr(ie, "espacio", None)
                else str(ie)
            )

            # Restringimos cursadas al estudiante logueado
            qs_insc = _q_inscripciones_del_usuario(getattr(self.request, "user", None))
            if qs_insc.exists():
                qs_curs = InscripcionEspacio.objects.filter(inscripcion__in=qs_insc)
            else:
                qs_curs = InscripcionEspacio.objects.none()

            self.fields[fk].queryset = qs_curs.order_by("-fecha", "espacio__nombre")
