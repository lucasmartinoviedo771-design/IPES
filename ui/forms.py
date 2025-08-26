# ui/forms.py
from django import forms
from django.apps import apps

def existing_fields(model, candidates):
    model_fields = {f.name for f in model._meta.get_fields() if getattr(f, "editable", False)}
    return [f for f in candidates if f in model_fields]

# -------- Estudiante --------
Estudiante = apps.get_model("academia_core", "Estudiante")

# Campos habituales; si alguno no existe en tu modelo se ignora automáticamente
ESTUDIANTE_CANDIDATES = [
    "apellido", "apellidos",
    "nombre", "nombres",
    "dni", "documento",
    "legajo",
    "fecha_nacimiento",
    "email", "mail",
    "telefono", "celular",
    "domicilio", "direccion", "localidad",
]

class NuevoEstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = existing_fields(Estudiante, ESTUDIANTE_CANDIDATES) or "__all__"
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }

# -------- Docente --------
Docente = apps.get_model("academia_core", "Docente")

DOCENTE_CANDIDATES = [
    "apellido", "apellidos",
    "nombre", "nombres",
    "dni", "documento",
    "legajo",
    "email", "mail",
    "telefono", "celular",
]

class NuevoDocenteForm(forms.ModelForm):
    class Meta:
        model = Docente
        fields = existing_fields(Docente, DOCENTE_CANDIDATES) or "__all__"