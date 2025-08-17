from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from .label_utils import espacio_etiqueta

from .models import (
    Estudiante,
    Profesorado,
    EspacioCurricular,
    EstudianteProfesorado,
    InscripcionEspacio,
    InscripcionFinal,
)

def _pop_req(kwargs):
    kwargs.pop("request", None); kwargs.pop("user", None)
    return None

def _has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name); return True
    except Exception:
        return False

def _text(v) -> str:
    if v is None: return ""
    return str(v).strip()

class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            "dni","apellido","nombre","fecha_nacimiento","lugar_nacimiento",
            "email","telefono","localidad","activo","foto"
        ]

class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)

class InscripcionEspacioForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)

        insc_id = self.data.get(self.add_prefix("inscripcion")) or self.initial.get("inscripcion")

        # Etiqueta normalizada: "1º, 1º C Nombre" / "1º, Anual Nombre"
        if "espacio" in self.fields:
            self.fields["espacio"].label_from_instance = espacio_etiqueta

        if not self.fields.get("espacio"):
            return

        # Filtrado por profesorado (y plan vigente si aplica), y excluir ya inscriptos
        if insc_id:
            try:
                insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
            except EstudianteProfesorado.DoesNotExist:
                insc = None
        else:
            insc = None

        if insc is None:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Seleccione primero la inscripción."
        else:
            qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
            if _has_field(EspacioCurricular, "plan") and getattr(insc.profesorado, "plan_vigente", None):
                qs = qs.filter(plan=insc.profesorado.plan_vigente)
            ya_ids = list(InscripcionEspacio.objects.filter(inscripcion=insc).values_list("espacio_id", flat=True))
            if ya_ids: qs = qs.exclude(pk__in=ya_ids)
            self.fields["espacio"].queryset = qs.order_by("anio","cuatrimestre","nombre")

    def clean(self):
        cleaned = super().clean()
        insc = cleaned.get("inscripcion"); espacio = cleaned.get("espacio")
        if insc and espacio and (espacio.profesorado_id != insc.profesorado_id):
            self.add_error("espacio", "El espacio no pertenece al profesorado de la inscripción seleccionada.")
        return cleaned

class InscripcionFinalForm(forms.ModelForm):
    estudiante = forms.ModelChoiceField(queryset=Estudiante.objects.all(), required=False)

    class Meta:
        model = InscripcionFinal
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)

        # Buscar el FK a InscripcionEspacio con tolerancia al nombre del campo
        fk = None
        for f in InscripcionFinal._meta.get_fields():
            if getattr(getattr(f, "related_model", None), "__name__", "") == "InscripcionEspacio":
                fk = f.name; break
        self._fk = fk

        if fk and fk in self.fields:
            # Etiquetar por el espacio de la inscripción (normalizado)
            self.fields[fk].label_from_instance = (
                lambda ie: espacio_etiqueta(getattr(ie, "espacio", None))
                if getattr(ie, "espacio", None) else str(ie)
            )
            # Filtrar cursadas por estudiante (si se eligió)
            est_id = self.data.get(self.add_prefix("estudiante")) or self.initial.get("estudiante")
            if est_id:
                try:
                    est = Estudiante.objects.get(pk=est_id)
                    qs = InscripcionEspacio.objects.filter(inscripcion__estudiante=est)
                except Estudiante.DoesNotExist:
                    qs = InscripcionEspacio.objects.none()
            else:
                qs = InscripcionEspacio.objects.none()
            self.fields[fk].queryset = qs.order_by("-fecha","espacio__nombre")

class CargarNotaFinalForm(forms.ModelForm):
    estudiante = forms.ModelChoiceField(queryset=Estudiante.objects.all(), required=False)

    class Meta:
        model = InscripcionFinal
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)
        if "nota_final" in self.fields:
            self.fields["nota_final"].min_value = 0
            self.fields["nota_final"].max_value = 10

        fk = None
        for f in InscripcionFinal._meta.get_fields():
            if getattr(getattr(f, "related_model", None), "__name__", "") == "InscripcionEspacio":
                fk = f.name; break
        self._fk = fk

        if fk and fk in self.fields:
            self.fields[fk].label_from_instance = (
                lambda ie: espacio_etiqueta(getattr(ie, "espacio", None))
                if getattr(ie, "espacio", None) else str(ie)
            )
            est_id = self.data.get(self.add_prefix("estudiante")) or self.initial.get("estudiante")
            if est_id:
                try:
                    est = Estudiante.objects.get(pk=est_id)
                    qs = InscripcionEspacio.objects.filter(inscripcion__estudiante=est)
                except Estudiante.DoesNotExist:
                    qs = InscripcionEspacio.objects.none()
            else:
                qs = InscripcionEspacio.objects.none()
            self.fields[fk].queryset = qs.order_by("-fecha","espacio__nombre")

    def clean_nota_final(self):
        nota = self.cleaned_data.get("nota_final")
        if nota is None:
            return nota
        try:
            iv = int(nota)
        except Exception:
            raise ValidationError("La nota debe ser un entero (0..10).")
        if iv < 0 or iv > 10:
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return iv

class CargarResultadoFinalForm(forms.ModelForm):
    estudiante = forms.ModelChoiceField(queryset=Estudiante.objects.all(), required=False)

    class Meta:
        model = InscripcionFinal
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)

        fk = None
        for f in InscripcionFinal._meta.get_fields():
            if getattr(getattr(f, "related_model", None), "__name__", "") == "InscripcionEspacio":
                fk = f.name; break
        self._fk = fk

        if fk and fk in self.fields:
            self.fields[fk].label_from_instance = (
                lambda ie: espacio_etiqueta(getattr(ie, "espacio", None))
                if getattr(ie, "espacio", None) else str(ie)
            )
            est_id = self.data.get(self.add_prefix("estudiante")) or self.initial.get("estudiante")
            if est_id:
                try:
                    est = Estudiante.objects.get(pk=est_id)
                    qs = InscripcionEspacio.objects.filter(inscripcion__estudiante=est)
                except Estudiante.DoesNotExist:
                    qs = InscripcionEspacio.objects.none()
            else:
                qs = InscripcionEspacio.objects.none()
            self.fields[fk].queryset = qs.order_by("-fecha","espacio__nombre")

class CargarCursadaForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = ["inscripcion","espacio","fecha","estado"]

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)

        # Etiqueta normalizada
        if "espacio" in self.fields:
            self.fields["espacio"].label_from_instance = espacio_etiqueta

        # Filtrado de espacios según inscripción/plan
        insc_id = self.data.get(self.add_prefix("inscripcion")) or self.initial.get("inscripcion")
        if insc_id:
            try:
                insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
            except EstudianteProfesorado.DoesNotExist:
                insc = None
        else:
            insc = None

        if "espacio" in self.fields:
            if insc is None:
                self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            else:
                qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
                if _has_field(EspacioCurricular, "plan") and getattr(insc.profesorado, "plan_vigente", None):
                    qs = qs.filter(plan=insc.profesorado.plan_vigente)
                self.fields["espacio"].queryset = qs.order_by("anio","cuatrimestre","nombre")

        # Si ya hay espacio seleccionado, cargar choices de "estado" en caliente
        espacio_id = self.data.get(self.add_prefix("espacio")) or self.initial.get("espacio")
        if espacio_id and "estado" in self.fields:
            from .condiciones import _choices_condicion_para_espacio
            try:
                esp = EspacioCurricular.objects.get(pk=espacio_id)
                self.fields["estado"].choices = _choices_condicion_para_espacio(esp)
            except EspacioCurricular.DoesNotExist:
                pass
