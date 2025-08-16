# academia_core/forms_carga.py
from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Estudiante,
    Profesorado,
    EspacioCurricular,
    EstudianteProfesorado,
    InscripcionEspacio,
    InscripcionFinal,
    Movimiento,
)

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def _plan_vigente_id(profesorado: Profesorado | None) -> int | None:
    if profesorado is None:
        return None
    pv = getattr(profesorado, "plan_vigente", None)
    return getattr(pv, "id", None)


def _build_q_for_insc_space(insc: EstudianteProfesorado) -> Q:
    field_names = {f.name for f in InscripcionEspacio._meta.get_fields()}
    candidates = ("inscripcion", "inscripcion_cursada", "inscripcion_profesorado")
    q = Q()
    added = False
    for fname in candidates:
        if fname in field_names:
            q |= Q(**{fname: insc})
            added = True
    return q if added else Q(pk__in=[])


# -----------------------------------------------------------
# Alta de ESTUDIANTE
# -----------------------------------------------------------

class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            "dni", "apellido", "nombre",
            "fecha_nacimiento", "lugar_nacimiento",
            "email", "telefono", "localidad",
            "activo", "foto",
        ]
        widgets = {
            "dni": forms.TextInput(attrs={"class": "inp", "placeholder": "DNI"}),
            "apellido": forms.TextInput(attrs={"class": "inp"}),
            "nombre": forms.TextInput(attrs={"class": "inp"}),
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "lugar_nacimiento": forms.TextInput(attrs={"class": "inp"}),
            "email": forms.EmailInput(attrs={"class": "inp"}),
            "telefono": forms.TextInput(attrs={"class": "inp"}),
            "localidad": forms.TextInput(attrs={"class": "inp"}),
            "activo": forms.CheckboxInput(),
            "foto": forms.ClearableFileInput(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dni"].help_text = self.fields["dni"].help_text or ""
        self.fields["activo"].initial = self.fields["activo"].initial if self.instance and self.instance.pk else True


# -----------------------------------------------------------
# Inscripción a CARRERA
# -----------------------------------------------------------

class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = "__all__"

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        for nombre in ("estudiante", "profesorado", "curso_introductorio"):
            if nombre in self.fields:
                self.fields[nombre].widget.attrs.update({"class": "inp"})

        for nombre in ("cohorte", "anio_academico", "ubicacion", "sede", "ubica", "colegio"):
            if nombre in self.fields:
                self.fields[nombre].widget.attrs.update({"class": "inp"})

        if "adeuda_detalle" in self.fields:
            self.fields["adeuda_detalle"].widget = forms.Textarea(
                attrs={"rows": 2, "class": "inp", "placeholder": "Listado (si corresponde)"}
            )

        for n in [
            "doc_dni_legalizado",
            "doc_titulo_sec_legalizado",
            "doc_cert_medico",
            "doc_fotos_carnet",
            "doc_folios_oficio",
            "nota_compromiso",
            "libreta_entregada",
            "adeuda_materias",
            "doc_titulo_superior_legalizado",
            "doc_incumbencias_titulo",
        ]:
            if n in self.fields:
                self.fields[n].widget = forms.CheckboxInput()

        if "profesorado" in self.fields:
            self.fields["profesorado"].queryset = Profesorado.objects.order_by("nombre")


# -----------------------------------------------------------
# Inscripción a MATERIA (cursada)
# -----------------------------------------------------------

class InscripcionEspacioForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for nombre in ("inscripcion", "espacio"):
            if nombre in self.fields:
                self.fields[nombre].widget.attrs.update({"class": "inp"})
        if "anio_academico" in self.fields:
            self.fields["anio_academico"].widget.attrs.update({"class": "inp"})

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            if "espacio" in self.fields:
                self.fields["espacio"].queryset = EspacioCurricular.objects.none()
                self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        self.initial["inscripcion"] = insc_id

        try:
            insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
        except EstudianteProfesorado.DoesNotExist:
            if "espacio" in self.fields:
                self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_id = _plan_vigente_id(insc.profesorado)
        if plan_id:
            base_pv = base.filter(plan_id=plan_id)
            base = base_pv if base_pv.exists() else base

        ya_ids = list(InscripcionEspacio.objects.filter(inscripcion=insc).values_list("espacio_id", flat=True))
        if ya_ids:
            base = base.exclude(id__in=ya_ids)

        if "espacio" in self.fields:
            self.fields["espacio"].queryset = base.order_by("anio", "cuatrimestre", "nombre")


# -----------------------------------------------------------
# Inscripción a MESA DE FINAL
# -----------------------------------------------------------

class InscripcionFinalForm(forms.ModelForm):
    class Meta:
        model = InscripcionFinal
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for n in self.fields:
            self.fields[n].widget.attrs.setdefault("class", "inp")

        if "estudiante" in self.fields:
            est_id = (
                self.data.get("estudiante")
                or getattr(self.initial.get("estudiante"), "pk", None)
                or getattr(getattr(self.instance, "estudiante", None), "pk", None)
            )
            if est_id:
                self.initial["estudiante"] = est_id
                target_fks = ("inscripcion_cursada", "inscripcion_espacio", "insc_espacio", "inscripcion")
                fk_name = next((n for n in target_fks if n in self.fields), None)

                if fk_name:
                    qs = (InscripcionEspacio.objects
                          .select_related("inscripcion", "espacio")
                          .filter(inscripcion__estudiante_id=est_id)
                          .order_by("espacio__anio", "espacio__cuatrimestre", "espacio__nombre"))
                    self.fields[fk_name].queryset = qs


# -----------------------------------------------------------
# CARGA REGULARIDAD / PROMOCIÓN
# -----------------------------------------------------------

class CargarRegularidadForm(forms.ModelForm):
    """
    Condición dinámica:
      - Taller/Seminario/Laboratorio/Práctica → Aprobado / No aprobado
      - Promocional → Promoción / Regular
      - Resto (con final) → Regular / Libre
    """
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],
        coerce=int, required=False, label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"}),
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num"]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
        }

    @staticmethod
    def _condiciones_para(espacio: EspacioCurricular | None) -> list[tuple[str, str]]:
        # Heurística robusta basada en nombre/formato y flags comunes
        if espacio is None:
            # Default para que NUNCA quede vacío
            return [("Regular", "Regular"), ("Libre", "Libre")]

        nombre = (getattr(espacio, "nombre", "") or "").lower()
        formato = (getattr(espacio, "formato", "") or "").lower()
        # Flags usuales si existen en tu modelo
        es_promocional = bool(
            getattr(espacio, "promociona", False) or
            getattr(espacio, "regimen_promocion", False)
        )
        es_practico = any(w in (nombre + " " + formato)
                          for w in ("taller", "seminar", "seminario", "laboratorio", "práctica", "practica"))

        if es_practico:
            return [("Aprobado", "Aprobado"), ("No aprobado", "No aprobado")]
        if es_promocional:
            return [("Promoción", "Promoción"), ("Regular", "Regular")]
        return [("Regular", "Regular"), ("Libre", "Libre")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            # Condición default para que no quede vacío
            self.fields["condicion"].choices = [("", "---------"), ("Regular", "Regular"), ("Libre", "Libre")]
            return

        self.initial["inscripcion"] = insc_id

        try:
            insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["condicion"].choices = [("", "---------"), ("Regular", "Regular"), ("Libre", "Libre")]
            return

        q = _build_q_for_insc_space(insc)
        cursadas_ids = list(
            InscripcionEspacio.objects.filter(q).values_list("espacio_id", flat=True).distinct()
        )

        if cursadas_ids:
            base = EspacioCurricular.objects.filter(id__in=cursadas_ids)
        else:
            base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
            plan_id = _plan_vigente_id(insc.profesorado)
            if plan_id:
                base_pv = base.filter(plan_id=plan_id)
                base = base_pv if base_pv.exists() else base

        self.fields["espacio"].queryset = base.order_by("anio", "cuatrimestre", "nombre")

        # Determinar condiciones según el espacio seleccionado (si viene en self.data/initial/instance)
        esp_id = (
            self.data.get("espacio")
            or getattr(self.initial.get("espacio"), "pk", None)
            or getattr(self.instance, "espacio_id", None)
        )
        espacio = None
        if esp_id:
            try:
                espacio = base.get(pk=esp_id)
            except EspacioCurricular.DoesNotExist:
                espacio = None

        conds = self._condiciones_para(espacio)
        self.fields["condicion"].choices = [("", "---------")] + conds

    def clean(self):
        cleaned = super().clean()
        cond = cleaned.get("condicion")
        nota = cleaned.get("nota_num")

        # Nota sólo obligatoria en Promoción / Aprobado / Regular
        if cond in {"Promoción", "Aprobado", "Regular"}:
            if nota is None:
                raise ValidationError("Debe seleccionar una nota (0–10).")
            if not (0 <= nota <= 10):
                raise ValidationError("La nota debe estar entre 0 y 10.")
        else:
            # Libre y No aprobado no requieren nota
            cleaned["nota_num"] = None

        return cleaned


# -----------------------------------------------------------
# CARGA FINAL (nota/resultado)
# -----------------------------------------------------------

class CargarFinalForm(forms.ModelForm):
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],
        coerce=int, required=False, label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"}),
    )

    class Meta:
        model = Movimiento
        fields = [
            "inscripcion", "espacio", "fecha", "condicion",
            "nota_num", "ausente", "ausencia_justificada",
            "nota_texto", "disposicion_interna",
        ]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
            "nota_texto": forms.TextInput(attrs={"class": "inp"}),
            "disposicion_interna": forms.TextInput(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not getattr(self.fields["condicion"], "choices", None) or len(self.fields["condicion"].choices) == 0:
            self.fields["condicion"].choices = [
                ("Regular", "Regular"),
                ("Libre", "Libre"),
                ("Equivalencia", "Equivalencia"),
            ]

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )
        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        self.initial["inscripcion"] = insc_id

        try:
            insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_id = _plan_vigente_id(insc.profesorado)
        if plan_id:
            base_pv = base.filter(plan_id=plan_id)
            base = base_pv if base_pv.exists() else base

        self.fields["espacio"].queryset = base.order_by("anio", "cuatrimestre", "nombre")

    def clean(self):
        cleaned = super().clean()
        cond = cleaned.get("condicion")
        aus = cleaned.get("ausente")
        nota = cleaned.get("nota_num")

        if cond == "Equivalencia":
            cleaned["nota_num"] = None
            return cleaned

        if aus:
            cleaned["nota_num"] = None
            return cleaned

        if nota is None:
            raise ValidationError("Debe seleccionar una nota o marcar Ausente.")
        if not (0 <= nota <= 10):
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned


class CargarResultadoFinalForm(CargarFinalForm):
    pass


class CargarNotaFinalForm(CargarFinalForm):
    pass
