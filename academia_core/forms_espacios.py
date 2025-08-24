# academia_core/forms_espacios.py
from django import forms
from .models import EspacioCurricular, Profesorado, PlanEstudios


class EspacioForm(forms.ModelForm):
    class Meta:
        model = EspacioCurricular
        fields = [
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
