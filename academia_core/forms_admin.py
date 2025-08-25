# academia_core/forms_admin.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Profesorado, PlanEstudios, EspacioCurricular, Estudiante

# === Helpers ===============================
# Ajustá este orden según tus modelos. Se usa para "renombrar"
# intentando el primer campo que exista.
_NAME_FIELDS = ("nombre", "resolucion", "titulo", "descripcion")


def _rename_instance(obj, new_name: str):
    for field in _NAME_FIELDS:
        if hasattr(obj, field):
            setattr(obj, field, new_name)
            obj.save(update_fields=[field])
            return obj
    raise ValidationError(
        f"No encontré un campo de texto para renombrar en {obj.__class__.__name__}. "
        f"Probé: {', '.join(_NAME_FIELDS)}"
    )


# === Crear (altas) =========================
class ProfesoradoCreateForm(forms.ModelForm):
    class Meta:
        model = Profesorado
        fields = "__all__"


class PlanCreateForm(forms.ModelForm):
    class Meta:
        model = PlanEstudios
        fields = "__all__"


class EstudianteCreateForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = "__all__"


# === Renombrar =============================
class RenameProfesoradoForm(forms.Form):
    profesorado = forms.ModelChoiceField(
        queryset=Profesorado.objects.all().order_by("nombre"), label="Profesorado"
    )
    nuevo_nombre = forms.CharField(label="Nuevo nombre", max_length=255)

    def save(self):
        prof = self.cleaned_data["profesorado"]
        _rename_instance(prof, self.cleaned_data["nuevo_nombre"])
        return prof


class RenamePlanForm(forms.Form):
    profesorado = forms.ModelChoiceField(
        queryset=Profesorado.objects.all().order_by("nombre"), label="Profesorado"
    )
    plan = forms.ModelChoiceField(queryset=PlanEstudios.objects.none(), label="Plan")
    nuevo_nombre = forms.CharField(
        label="Nuevo nombre (p.ej. alias/resolución)", max_length=255
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = args[0] if args else None

        prof = None
        if data and data.get("profesorado"):
            try:
                prof = Profesorado.objects.get(pk=data.get("profesorado"))
            except Profesorado.DoesNotExist:
                prof = None

        if prof:
            self.fields["plan"].queryset = PlanEstudios.objects.filter(
                profesorado=prof
            ).order_by("-vigente", "resolucion")
        else:
            self.fields["plan"].queryset = PlanEstudios.objects.all().order_by(
                "-vigente", "resolucion"
            )

    def save(self):
        plan = self.cleaned_data["plan"]
        _rename_instance(plan, self.cleaned_data["nuevo_nombre"])
        return plan


class RenameEspacioForm(forms.Form):
    profesorado = forms.ModelChoiceField(
        queryset=Profesorado.objects.all().order_by("nombre"), label="Profesorado"
    )
    plan = forms.ModelChoiceField(queryset=PlanEstudios.objects.none(), label="Plan")
    espacio = forms.ModelChoiceField(
        queryset=EspacioCurricular.objects.none(), label="Espacio"
    )
    nuevo_nombre = forms.CharField(label="Nuevo nombre", max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = args[0] if args else None

        prof = None
        if data and data.get("profesorado"):
            try:
                prof = Profesorado.objects.get(pk=data.get("profesorado"))
            except Profesorado.DoesNotExist:
                prof = None

        if prof:
            self.fields["plan"].queryset = PlanEstudios.objects.filter(
                profesorado=prof
            ).order_by("-vigente", "resolucion")
        else:
            self.fields["plan"].queryset = PlanEstudios.objects.all().order_by(
                "-vigente", "resolucion"
            )

        plan = None
        if data and data.get("plan"):
            try:
                plan = PlanEstudios.objects.get(pk=data.get("plan"))
            except PlanEstudios.DoesNotExist:
                plan = None

        if plan:
            self.fields["espacio"].queryset = EspacioCurricular.objects.filter(
                profesorado=plan.profesorado, plan=plan
            ).order_by("anio", "cuatrimestre", "nombre")
        else:
            self.fields["espacio"].queryset = EspacioCurricular.objects.all().order_by(
                "anio", "cuatrimestre", "nombre"
            )

    def save(self):
        espacio = self.cleaned_data["espacio"]
        _rename_instance(espacio, self.cleaned_data["nuevo_nombre"])
        return espacio
