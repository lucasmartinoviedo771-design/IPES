# ui/forms.py
from django import forms
from django.apps import apps

def get_model(app_label, model_name):
    return apps.get_model(app_label, model_name)

# ---------- Estudiante ----------
class EstudianteForm(forms.ModelForm):
    class Meta:
        model = get_model("academia_core", "Estudiante")
        fields = ["dni", "apellido", "nombre", "email", "telefono"]  # ajusta si difiere

# ---------- Inscripciones ----------
class InscripcionCarreraForm(forms.ModelForm):
    """Asume un modelo InscripcionCarrera(estudiante, profesorado/planestudios, fecha, estado...)"""
    class Meta:
        model = get_model("academia_core", "EstudianteProfesorado")
        fields = "__all__"

class InscripcionMateriaForm(forms.ModelForm):
    """Asume un modelo Inscripcionespacio(estudiante, espacio/plan, comision, periodo, estado...)"""
    class Meta:
        model = get_model("academia_core", "InscripcionEspacio")
        fields = "__all__"

class InscripcionFinalForm(forms.ModelForm):
    """Asume un modelo InscripcionFinal(estudiante, espacio, mesa, fecha...)"""
    class Meta:
        model = get_model("academia_core", "InscripcionFinal")
        fields = "__all__"

# ---------- Calificaciones (borrador) ----------
class CalificacionBorradorForm(forms.ModelForm):
    """Asume modelo Calificacion(inscripcion, instancia, nota, estado)"""
    class Meta:
        model = get_model("academia_core", "Movimiento")
        fields = ["inscripcion", "espacio", "tipo", "condicion", "nota_num"]
