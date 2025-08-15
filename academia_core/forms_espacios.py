# academia_core/forms_espacios.py
from django import forms
from .models import EspacioCurricular, Profesorado, PlanEstudios

class EspacioForm(forms.ModelForm):
    class Meta:
        model = EspacioCurricular
        fields = [
            "profesorado",
            "plan",
            "anio",
            "cuatrimestre",
            "formato",
            "nombre",
            "horas",
        ]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Nombre del espacio"}),
            "anio": forms.TextInput(attrs={"placeholder": "1° / 2° / 3° / 4°"}),
        }

# --- NUEVO FORMULARIO AGREGADO ---
class FiltroEspaciosForm(forms.Form):
    profesorado = forms.ModelChoiceField(
        queryset=Profesorado.objects.all().order_by("nombre"),
        required=True, label="Profesorado",
    )
    plan = forms.ModelChoiceField(
        queryset=PlanEstudios.objects.none(),
        required=True, label="Plan",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        p_val = self.data.get("profesorado") or self.initial.get("profesorado")
        try:
            p_id = int(p_val) if p_val else None
        except ValueError:
            p_id = None

        if p_id:
            plans = PlanEstudios.objects.filter(profesorado_id=p_id).order_by("-vigente", "resolucion")
            self.fields["plan"].queryset = plans
            if not (self.data.get("plan") or self.initial.get("plan")) and plans.count() == 1:
                self.initial["plan"] = plans.first().pk
        else:
            self.fields["plan"].queryset = PlanEstudios.objects.none()