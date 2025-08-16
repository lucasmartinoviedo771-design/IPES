# academia_core/forms_carga.py
from __future__ import annotations

from django import forms
from django.db.models import Q

from .models import (
    Estudiante,
    Profesorado,
    EspacioCurricular,
    EstudianteProfesorado,
    InscripcionEspacio,
    InscripcionFinal,
)
from .condiciones import (
    # (moved) Condiciones y helpers de formato están en academia_core/condiciones.py
def _plan_vigente_id(profesorado: Profesorado | None) -> int | None:
    if profesorado is None:
        return None
    pv = getattr(profesorado, "plan_vigente", None)
    return getattr(pv, "id", None)


def _build_q_for_insc_space(insc: EstudianteProfesorado) -> Q:
    """
    Arma un OR dinámico para soportar distintos nombres de FK
    en InscripcionEspacio según tu modelo (inscripcion / inscripcion_cursada / inscripcion_profesorado).
    """
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
        fields = ["dni", "apellido", "nombre", "fecha_nacimiento", "lugar_nacimiento", "email", "telefono", "localidad", "activo", "foto"]


# -----------------------------------------------------------
# Inscripción a CARRERA
# -----------------------------------------------------------

class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = "__all__"

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # estilizado
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

        # checkboxes
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

        # no repetir espacios ya inscriptos para esa inscripción
        ya_ids = list(InscripcionEspacio.objects.filter(_build_q_for_insc_space(insc)).values_list("espacio_id", flat=True))
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
                # intenta descubrir nombre de la FK hacia InscripcionEspacio
                target_fks = ("inscripcion_cursada", "inscripcion_espacio", "insc_espacio", "inscripcion")
                fk_name = next((n for n in target_fks if n in self.fields), None)
                if fk_name:
                    qs = (InscripcionEspacio.objects
                          .select_related("inscripcion", "espacio")
                          .filter(inscripcion__estudiante_id=est_id)
                          .order_by("espacio__anio", "espacio__cuatrimestre", "espacio__nombre"))
                    self.fields[fk_name].queryset = qs


# Alias para no romper imports en views_panel.py
CargarFinalForm = InscripcionFinalForm


# -----------------------------------------------------------
# CARGA REGULARIDAD / PROMOCIÓN
# -----------------------------------------------------------

class CargarCursadaForm(forms.ModelForm):
    """
    Carga de Regularidad/Promoción (InscripcionEspacio).
    Campo 'estado' = “Condición” (opciones dinámicas por formato del espacio).
    """
    class Meta:
        model = InscripcionEspacio
        # Confirmado: anio_academico, espacio, estado, fecha, inscripcion
        fields = ["inscripcion", "espacio", "fecha", "estado"]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "estado": forms.Select(attrs={"class": "inp"}),  # Dinámico
        }
        labels = {"estado": "Condición"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Aseguramos que el label diga "Condición"
        self.fields["estado"].label = "Condición"

        # Si ya viene un espacio seleccionado (instance/initial/data), seteo choices server-side
        espacio_obj = None
        esp_id = (
            self.data.get("espacio")
            or self.initial.get("espacio")
            or getattr(getattr(self.instance, "espacio", None), "id", None)
        )

        if esp_id:
            try:
                espacio_obj = EspacioCurricular.objects.get(pk=esp_id)
            except EspacioCurricular.DoesNotExist:
                espacio_obj = None

        self.fields["estado"].choices = [("", "---------")] + _choices_condicion_para_espacio(espacio_obj)


# -----------------------------------------------------------
# Placeholders simples para vistas de finales
# -----------------------------------------------------------

class CargarNotaFinalForm(forms.Form):
    nota_final = forms.IntegerField(min_value=0, max_value=10, required=False, label="Nota final")
    condicion = forms.ChoiceField(
        required=False,
        choices=[("", "---------"), ("APROBADO", "Aprobado"), ("DESAPROBADO", "Desaprobado")],
        label="Condición final",
    )


class CargarResultadoFinalForm(forms.Form):
    """Placeholder liviano para no romper imports en views_panel."""
    resultado = forms.ChoiceField(
        required=False,
        choices=[("", "---------"), ("APROBADO", "Aprobado"), ("DESAPROBADO", "Desaprobado")],
        label="Resultado final",
    )
    nota_final = forms.IntegerField(min_value=0, max_value=10, required=False, label="Nota final")
