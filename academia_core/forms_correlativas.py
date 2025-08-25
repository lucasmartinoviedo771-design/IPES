from django import forms
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from academia_core.models import Profesorado, PlanEstudios, EspacioCurricular, Correlatividad


class CorrelatividadForm(forms.Form):
    profesorado = ModelChoiceField(
        queryset=Profesorado.objects.all().order_by('nombre'),
        label="Profesorado",
        empty_label="-- Seleccione un Profesorado --"
    )
    plan = ModelChoiceField(
        queryset=PlanEstudios.objects.none(), # Initially empty
        label="Plan de Estudios",
        empty_label="-- Seleccione un Plan --"
    )
    materia_principal = ModelChoiceField(
        queryset=EspacioCurricular.objects.none(), # Initially empty
        label="Materia Principal",
        empty_label="-- Seleccione una Materia --"
    )
    correlativas_regulares = ModelMultipleChoiceField(
        queryset=EspacioCurricular.objects.none(), # Initially empty
        label="Correlativas (condición regular)",
        required=False, # Not mandatory to select any
        widget=forms.CheckboxSelectMultiple # Or forms.SelectMultiple
    )
    correlativas_aprobadas = ModelMultipleChoiceField(
        queryset=EspacioCurricular.objects.none(), # Initially empty
        label="Correlativas (aprobadas)",
        required=False, # Not mandatory to select any
        widget=forms.CheckboxSelectMultiple # Or forms.SelectMultiple
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get data from either self.data (POST) or initial (GET)
        data_source = self.data if self.data else self.initial

        # If a profesorado is selected, filter plans
        if 'profesorado' in data_source:
            try:
                profesorado_id = int(data_source.get('profesorado'))
                self.fields['plan'].queryset = PlanEstudios.objects.filter(profesorado_id=profesorado_id).order_by('resolucion')
            except (ValueError, TypeError):
                pass # Invalid input, leave queryset empty

        # If a plan is selected, filter materias and correlativas
        if 'plan' in data_source:
            try:
                plan_id = int(data_source.get('plan'))
                # Filter materias for the main selection
                self.fields['materia_principal'].queryset = EspacioCurricular.objects.filter(plan_id=plan_id).order_by('nombre')

                # Filter correlativas (all other spaces in the same plan)
                all_other_spaces_in_plan = EspacioCurricular.objects.filter(plan_id=plan_id).order_by('nombre')
                self.fields['correlativas_regulares'].queryset = all_other_spaces_in_plan
                self.fields['correlativas_aprobadas'].queryset = all_other_spaces_in_plan

            except (ValueError, TypeError):
                pass # Invalid input, leave querysets empty

    def save(self, commit=True):
        # This is a custom form, not a ModelForm, so we need to handle saving manually
        profesorado = self.cleaned_data['profesorado']
        plan = self.cleaned_data['plan']
        materia_principal = self.cleaned_data['materia_principal']
        correlativas_regulares = self.cleaned_data['correlativas_regulares']
        correlativas_aprobadas = self.cleaned_data['correlativas_aprobadas']

        # Clear existing correlativities for this materia_principal and plan
        Correlatividad.objects.filter(
            plan=plan,
            espacio=materia_principal,
            tipo="CURSAR" # Assuming this form is only for CURSAR correlativities
        ).delete()

        # Save new regular correlativities
        for req_espacio in correlativas_regulares:
            Correlatividad.objects.create(
                plan=plan,
                espacio=materia_principal,
                tipo="CURSAR",
                requisito="REGULARIZADA",
                requiere_espacio=req_espacio
            )

        # Save new aprobadas correlativities
        for req_espacio in correlativas_aprobadas:
            Correlatividad.objects.create(
                plan=plan,
                espacio=materia_principal,
                tipo="CURSAR",
                requisito="APROBADA",
                requiere_espacio=req_espacio
            )

        # No return value as it's not a ModelForm instance
