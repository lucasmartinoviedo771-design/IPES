# ui/forms.py
from django import forms
from django.apps import apps
from django.forms.widgets import ClearableFileInput, DateInput, TextInput, EmailInput, NumberInput, Select, Textarea

def existing_fields(model, candidates):
    model_fields = {f.name for f in model._meta.get_fields() if getattr(f, "editable", False)}
    return [f for f in candidates if f in model_fields]

# ---- base para dar estilo a todos los campos ----
class BaseStyledModelForm(forms.ModelForm):
    BASE = (
        "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm "
        "placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 "
        "focus:border-brand-500"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, f in self.fields.items():
            w = f.widget
            # agrega clases si el widget no las trae
            w.attrs.setdefault("class", self.BASE)
            # place­holder con el label
            if isinstance(w, (TextInput, EmailInput, NumberInput, Textarea)):
                w.attrs.setdefault("placeholder", f.label)
            # inputs de fecha con type=date
            if isinstance(w, DateInput):
                w.input_type = "date"

        # si existe un campo de foto, usar ClearableFileInput bonito
        for pic in ["foto", "imagen", "foto_perfil", "avatar", "photo"]:
            if pic in self.fields:
                self.fields[pic].widget = ClearableFileInput(
                    attrs={
                        "accept": "image/*",
                        "class": self.BASE
                        + " file:mr-4 file:py-2 file:px-3 file:rounded-lg file:border-0 "
                          "file:bg-brand-500 file:text-white hover:file:bg-brand-600 cursor-pointer",
                    }
                )

# ui/forms.py
from django import forms
from django.forms import TextInput, EmailInput, DateInput, CheckboxInput, FileInput
from django.apps import apps

_INPUT = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-300"
_LABEL = "block text-sm font-medium text-slate-700 mb-1"

class EstudianteNuevoForm(forms.ModelForm):
    class Meta:
        model = apps.get_model("academia_core", "Estudiante")
        fields = [
            "apellido", "nombre", "dni",
            "fecha_nacimiento", "lugar_nacimiento",
            "email", "telefono",
            "contacto_emergencia_tel", "contacto_emergencia_parentesco",
            "localidad", "activo", "foto",
        ]
        widgets = {
            "apellido": TextInput(attrs={"class": _INPUT, "placeholder": "Apellido"}),
            "nombre": TextInput(attrs={"class": _INPUT, "placeholder": "Nombre"}),
            "dni": TextInput(attrs={"class": _INPUT, "placeholder": "DNI"}),
            "lugar_nacimiento": TextInput(attrs={"class": _INPUT, "placeholder": "Lugar de nacimiento"}),
            "fecha_nacimiento": DateInput(attrs={"class": _INPUT, "placeholder": "dd/mm/aaaa", "type": "date"}),
            "email": EmailInput(attrs={"class": _INPUT, "placeholder": "Email"}),
            "telefono": TextInput(attrs={"class": _INPUT, "placeholder": "Teléfono"}),
            "contacto_emergencia_tel": TextInput(attrs={"class": _INPUT, "placeholder": "Tel. de emergencia"}),
            "contacto_emergencia_parentesco": TextInput(attrs={"class": _INPUT, "placeholder": "Parentesco (emergencia)"}),
            "localidad": TextInput(attrs={"class": _INPUT, "placeholder": "Localidad"}),
            "activo": CheckboxInput(attrs={"class": "h-5 w-5 align-middle accent-blue-600"}),
            "foto": FileInput(attrs={"class": "block text-sm", "accept": "image/*"}),
        }

    # opcional: etiquetas más legibles
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "contacto_emergencia_tel": "Tel. de emergencia",
            "contacto_emergencia_parentesco": "Parentesco (emergencia)",
        }
        for name, field in self.fields.items():
            field.label = labels.get(name, field.label)

# -------- Docente --------
Docente = apps.get_model("academia_core", "Docente")

DOCENTE_CANDIDATES = [
    "apellido", "apellidos",
    "nombre", "nombres",
    "dni", "documento",
    "legajo",
    "email", "mail",
    "telefono", "celular",
    "foto", "imagen", "foto_perfil", "avatar", "photo",
]

class NuevoDocenteForm(BaseStyledModelForm):
    class Meta:
        model = Docente
        fields = existing_fields(Docente, DOCENTE_CANDIDATES) or "__all__"


# -----------------------
#   INSCRIPCIÓN CARRERA
# -----------------------
InscripcionCarrera = apps.get_model("academia_core", "EstudianteProfesorado")

class InscripcionCarreraForm(BaseStyledModelForm):
    class Meta:
        model = InscripcionCarrera
        # tomamos los que existan en el modelo
        fields = existing_fields(
            InscripcionCarrera,
            [
                "estudiante",       # FK
                "profesorado",      # o "carrera" si tu modelo lo llama así
                "fecha",            # si existe
                "observaciones",    # si existe
                "estado",           # si existe
            ],
        ) or "__all__"


# -------------------------
#   INSCRIPCIÓN A MATERIA
#   (suele llamarse InscripcionEspacio)
# -------------------------
InscripcionMateria = apps.get_model("academia_core", "InscripcionEspacio")

class InscripcionMateriaForm(BaseStyledModelForm):
    class Meta:
        model = InscripcionMateria
        fields = existing_fields(
            InscripcionMateria,
            [
                "estudiante",       # FK
                "espacio",          # o "espacio_curricular"/"materia"
                "comision",         # si existe
                "periodo",          # si existe
                "fecha",            # si existe
                "observaciones",    # si existe
                "estado",           # si existe
            ],
        ) or "__all__"


# -------------------------
#   INSCRIPCIÓN A MESA FINAL
# -------------------------
InscripcionFinal = apps.get_model("academia_core", "InscripcionFinal")

class InscripcionFinalForm(BaseStyledModelForm):
    class Meta:
        model = InscripcionFinal
        fields = existing_fields(
            InscripcionFinal,
            [
                "estudiante",       # FK
                "espacio",          # o "materia"
                "mesa",             # si existe
                "llamado",          # si existe
                "fecha",            # si existe
                "observaciones",    # si existe
                "estado",           # si existe
            ],
        ) or "__all__"

# -------------------------
#   CALIFICACIÓN (BORRADOR)
# -------------------------
Calificacion = apps.get_model("academia_core", "Movimiento")

class CalificacionBorradorForm(BaseStyledModelForm):
    class Meta:
        model = Calificacion
        fields = existing_fields(
            Calificacion,
            [
                "inscripcion",
                "espacio",
                "tipo",
                "fecha",
                "condicion",
                "nota_num",
                "nota_texto",
                "folio",
                "libro",
            ],
        ) or "__all__"


_SELECT = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"

class InscripcionProfesoradoForm(forms.ModelForm):
    """Formulario tolerante a diferencias de nombres en campos del modelo."""
    class Meta:
        model = apps.get_model("academia_core", "EstudianteProfesorado")
        fields = "__all__"  # luego ocultamos lo que no corresponda
        widgets = {}        # se completa en __init__

    def __init__(self, *args, **kwargs):
        initial_estudiante = kwargs.pop("initial_estudiante", None)
        super().__init__(*args, **kwargs)

        # Campos que típicamente no queremos editar a mano si existen
        ocultar = {
            "id", "created", "updated", "fecha_baja", "usuario_creacion",
            "usuario_actualizacion", "estado_interno",
        }
        for name in list(self.fields.keys()):
            if name in ocultar:
                self.fields.pop(name, None)

        # Tipados/estilos por tipo y por posibles nombres
        for name, field in self.fields.items():
            # Selects comunes (FKs): estudiante, profesorado, cohorte_fk si existiera
            if field.widget.__class__.__name__ in {"Select", "RelatedFieldWidgetWrapper"}:
                field.widget.attrs.setdefault("class", _SELECT)
            # Booleans
            elif field.__class__.__name__ == "BooleanField":
                field.widget = CheckboxInput(attrs={"class": "h-5 w-5 align-middle accent-blue-600"})
            # Textos por defecto
            else:
                field.widget.attrs.setdefault("class", _INPUT)

        # Tratar de detectar el campo de fecha de inscripción
        for probable in ("fecha_inscripcion", "cohorte", "fecha"):
            if probable in self.fields and not isinstance(self.fields[probable].widget, DateInput):
                self.fields[probable].widget = DateInput(attrs={"class": _INPUT, "type": "date"})
                break

        # Un textarea para observaciones si existiera
        for probable in ("observaciones", "nota", "comentario"):
            if probable in self.fields:
                self.fields[probable].widget = Textarea(attrs={"class": _INPUT, "rows": 3})
                break

        # Preseleccionar estudiante si viene por querystring (?est=ID)
        if initial_estudiante and "estudiante" in self.fields:
            self.fields["estudiante"].initial = initial_estudiante
