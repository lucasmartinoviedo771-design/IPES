# ui/forms.py
from django import forms
from django.apps import apps
from django.forms.widgets import ClearableFileInput, DateInput, TextInput, EmailInput, NumberInput, Select, Textarea
from django.forms import CheckboxInput, FileInput
from datetime import date

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

_INPUT = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-300"
_LABEL = "block text-sm font-medium text-slate-700 mb-1"
_SELECT = "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"

class EstudianteNuevoForm(forms.ModelForm):
    field_order = [
        "apellido", "nombre",
        "dni", "fecha_nacimiento",
        "lugar_nacimiento", "email",
        "telefono", "localidad",
        "contacto_emergencia_parentesco", "contacto_emergencia_tel",
        "activo", "foto",
    ]
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


# -------------------------
#   INSCRIPCIÓN A PROFESORADO (CARRERA)
# -------------------------
EstudianteProfesorado = apps.get_model("academia_core", "EstudianteProfesorado")
CERT_DOCENTE_LABEL = "Certificación Docente para la Educación Secundaria"

def year_choices(start=2010):
    current = date.today().year
    return [(y, y) for y in range(current, start - 1, -1)]

base_input = {"class": "w-full border rounded px-3 py-2"}
base_select = {"class": "w-full border rounded px-3 py-2"}
base_textarea = {"class": "w-full border rounded px-3 py-2", "rows": 3}

class InscripcionProfesoradoForm(forms.ModelForm):
    # cohorte en <select> de años
    cohorte = forms.ChoiceField(choices=year_choices(), required=True)

    # Requisitos (generales)
    req_dni = forms.BooleanField(required=False, label="Fotocopia legalizada del DNI")
    req_cert_med = forms.BooleanField(required=False, label="Certificado Médico de Buena Salud")
    req_fotos = forms.BooleanField(required=False, label="Dos (2) fotos carnet")
    req_folios = forms.BooleanField(required=False, label="Dos (2) folios oficio")

    # Título (mutuamente excluyentes para carreras generales)
    req_titulo_sec = forms.BooleanField(required=False, label="Fotocopia legalizada del Título Secundario")
    req_titulo_tramite = forms.BooleanField(required=False, label="Título en trámite")
    req_adeuda = forms.BooleanField(required=False, label="Adeuda materias")
    req_adeuda_mats = forms.CharField(required=False, label="Materias adeudadas")
    req_adeuda_inst = forms.CharField(required=False, label="Escuela o Institución de origen")

    # Específico Certificación Docente
    req_titulo_sup = forms.BooleanField(required=False, label="Fotocopia legalizada del Título de Nivel Superior")
    req_incumbencias = forms.BooleanField(required=False, label="Incumbencias del Título Base")

    # Nuevo: “Condición” (tiene que estar marcado para regularidad)
    req_condicion = forms.BooleanField(required=False, label="Formulario de preinscripción")

    # DDJJ aparece solo si queda condicional
    ddjj_compromiso = forms.BooleanField(required=False, label="DDJJ de Compromiso")

    class Meta:
        model = EstudianteProfesorado
        fields = ["estudiante", "profesorado", "plan", "cohorte"]  # solo campos del modelo
        widgets = {
            "estudiante": forms.Select(attrs=base_select),
            "profesorado": forms.Select(attrs=base_select),
            "plan": forms.Select(attrs=base_select),
            "cohorte": forms.Select(attrs=base_select),
        }

    field_order = [
        "estudiante", "profesorado", "plan", "cohorte",
        "req_dni", "req_cert_med", "req_fotos", "req_folios",
        "req_titulo_sec", "req_titulo_tramite", "req_adeuda",
        "req_adeuda_mats", "req_adeuda_inst",
        "req_titulo_sup", "req_incumbencias",
        "req_condicion", "ddjj_compromiso",
    ]

    def __init__(self, *args, **kwargs):
        initial_estudiante = kwargs.pop("initial_estudiante", None)
        super().__init__(*args, **kwargs)

        # año actual por defecto
        current = date.today().year
        self.fields["cohorte"].choices = year_choices()
        self.fields["cohorte"].initial = current

        if initial_estudiante is not None and "estudiante" in self.fields:
            self.fields["estudiante"].initial = initial_estudiante

        # estilo a los inputs de texto extra
        for name in ("req_adeuda_mats", "req_adeuda_inst"):
            self.fields[name].widget.attrs.update(base_input)

        try:
            from django.apps import apps
            Plan = apps.get_model("academia_core", "PlanEstudios")
            if "plan" in self.fields:
                self.fields["plan"].queryset = Plan.objects.none()
        except Exception:
            pass

    # ---------- Validación ----------
    def clean(self):
        cleaned = super().clean()
        prof = cleaned.get("profesorado")
        label = (str(prof).strip() if prof else "")
        is_cert_docente = (label == CERT_DOCENTE_LABEL)

        # exclusión mutua (solo aplica a generales)
        if not is_cert_docente:
            a = cleaned.get("req_titulo_sec")
            b = cleaned.get("req_titulo_tramite")
            c = cleaned.get("req_adeuda")
            if sum(bool(x) for x in (a, b, c)) > 1:
                raise forms.ValidationError(
                    "‘Título Secundario’, ‘Título en trámite’ y ‘Adeuda materias’ son mutuamente excluyentes."
                )

            if cleaned.get("req_adeuda"):
                if not cleaned.get("req_adeuda_mats"):
                    self.add_error("req_adeuda_mats", "Obligatorio si se marca ‘Adeuda materias’.")
                if not cleaned.get("req_adeuda_inst"):
                    self.add_error("req_adeuda_inst", "Obligatorio si se marca ‘Adeuda materias’.")

        else:
            # si es Certificación, ignoro título sec / trámite / adeuda
            cleaned["req_titulo_sec"] = False
            cleaned["req_titulo_tramite"] = False
            cleaned["req_adeuda"] = False
            cleaned["req_adeuda_mats"] = ""
            cleaned["req_adeuda_inst"] = ""

        return cleaned

    # ---------- Estado administrativo ----------
    def compute_estado_admin(self):
        cd = getattr(self, "cleaned_data", {})
        prof = cd.get("profesorado")
        label = (str(prof).strip() if prof else "")
        is_cert_docente = (label == CERT_DOCENTE_LABEL)

        # requisito común: “condición” marcado
        cond_ok = bool(cd.get("req_condicion"))

        if is_cert_docente:
            # generales + específicos de certificación
            base_ok = all([
                cd.get("req_dni"),
                cd.get("req_cert_med"),
                cd.get("req_fotos"),
                cd.get("req_folios"),
                cd.get("req_titulo_sup"),
                cd.get("req_incumbencias"),
            ])
            cond_flags = False  # no hay “trámite/adeuda” aquí
        else:
            # generales + título secundario (o condicional si trámite/adeuda)
            base_ok = all([
                cd.get("req_dni"),
                cd.get("req_cert_med"),
                cd.get("req_fotos"),
                cd.get("req_folios"),
                cd.get("req_titulo_sec"),
            ])
            cond_flags = any([cd.get("req_titulo_tramite"), cd.get("req_adeuda")])

        is_regular = base_ok and not cond_flags and cond_ok
        return ("REGULAR" if is_regular else "CONDICIONAL"), is_cert_docente


class CorrelatividadesForm(forms.Form):
    """
    Profesorado → Plan → Materia y definición de correlativas:
    - correlativas_regular: materias que requiere REGULARES
    - correlativas_aprobada: materias que requiere APROBADAS
    """
    APP_LABEL = "academia_core"
    PROF_MODEL = "Profesorado"
    PLAN_MODEL = "PlanEstudios"
    ESPACIO_MODEL = "EspacioCurricular"

    profesorado = forms.ModelChoiceField(
        queryset=apps.get_model(APP_LABEL, PROF_MODEL).objects.all().order_by("nombre"),
        required=True, label="Profesorado / Carrera",
        widget=forms.Select(attrs={"class": "block w-full rounded-xl border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-500"})
    )
    plan = forms.ModelChoiceField(
        queryset=apps.get_model(APP_LABEL, PLAN_MODEL).objects.none(),
        required=True, label="Plan",
        widget=forms.Select(attrs={"class": "block w-full rounded-xl border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-500", "data-endpoint": "/ui/api/materias-por-plan"})
    )
    espacio = forms.ModelChoiceField(
        queryset=apps.get_model(APP_LABEL, ESPACIO_MODEL).objects.none(),
        required=True, label="Materia / Espacio",
        widget=forms.Select(attrs={"class": "block w-full rounded-xl border border-slate-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-slate-500"})
    )

    correlativas_regular = forms.MultipleChoiceField(
        choices=[], required=False, label="Requiere REGULAR",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"})
    )
    correlativas_aprobada = forms.MultipleChoiceField(
        choices=[], required=False, label="Requiere APROBADA",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Plan = apps.get_model(self.APP_LABEL, self.PLAN_MODEL)
        Espacio = apps.get_model(self.APP_LABEL, self.ESPACIO_MODEL)

        # Si ya viene 'plan' en POST/initial, completamos dependientes
        plan = None
        if self.data.get("plan"):
            try:
                plan = Plan.objects.get(pk=self.data.get("plan"))
            except Plan.DoesNotExist:
                plan = None
        elif self.initial.get("plan"):
            plan = self.initial["plan"]

        if plan:
            self.fields["espacio"].queryset = Espacio.objects.filter(plan=plan).order_by("nombre")
            opciones = [(str(e.pk), str(e)) for e in self.fields["espacio"].queryset]
            self.fields["correlativas_regular"].choices = opciones
            self.fields["correlativas_aprobada"].choices = opciones

    def clean(self):
        cleaned = super().clean()
        espacio = cleaned.get("espacio")
        reg = cleaned.get("correlativas_regular") or []
        apr = cleaned.get("correlativas_aprobada") or []

        if espacio:
            if str(espacio.pk) in reg or str(espacio.pk) in apr:
                raise forms.ValidationError("La materia no puede ser correlativa de sí misma.")

        if set(reg) & set(apr):
            raise forms.ValidationError("Una correlativa no puede ser simultáneamente REGULAR y APROBADA.")
        return cleaned