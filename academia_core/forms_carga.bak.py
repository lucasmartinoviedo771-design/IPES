from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from .models import EstudianteProfesorado

# Estos imports pueden no existir aún; los “try” evitan que truene la importación.
try:  # pragma: no cover
    from .models import Estudiante
except Exception:  # noqa: BLE001
    Estudiante = None  # type: ignore

try:  # pragma: no cover
    from .models import InscripcionEspacio, Movimiento  # modelos del resto del flujo
except Exception:  # noqa: BLE001
    InscripcionEspacio = None  # type: ignore
    Movimiento = None          # type: ignore


# -----------------------------------------------------------------------------
# Alta de estudiante (usado por action=add_est en el panel)
# -----------------------------------------------------------------------------
if Estudiante:
    class EstudianteForm(forms.ModelForm):
        class Meta:
            model = Estudiante
            # Si tu modelo tiene todos estos campos, dejalos así; si faltara alguno,
            # podés quitarlo de la lista. (Los nombres coinciden con el template.)
            fields = [
                "dni",
                "apellido",
                "nombre",
                "fecha_nacimiento",
                "lugar_nacimiento",
                "email",
                "telefono",
                "localidad",
                "contacto_emergencia_tel",
                "contacto_emergencia_parentesco",
                "activo",
                "foto",
            ]

            widgets = {
                "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
                "contacto_emergencia_parentesco": forms.TextInput(
                    attrs={"placeholder": "Opcional"}
                ),
            }
else:
    # Fallback ultra-minimal por si el modelo no está disponible
    class EstudianteForm(forms.Form):  # type: ignore[misc]
        dni = forms.CharField()
        apellido = forms.CharField()
        nombre = forms.CharField()


# -----------------------------------------------------------------------------
# Inscribir a carrera
# -----------------------------------------------------------------------------
class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = [
            "estudiante", "profesorado", "cohorte", "curso_introductorio",
            "doc_dni_legalizado", "doc_cert_medico", "doc_fotos_carnet", "doc_folios_oficio",
            "doc_titulo_sec_legalizado", "doc_titulo_terciario_legalizado", "doc_incumbencias",
            "titulo_en_tramite", "adeuda_materias", "materias_adeudadas", "institucion_origen",
            "nota_compromiso",
        ]

    def _es_cd(self):
        prof = self.cleaned_data.get("profesorado")
        nombre = (getattr(prof, "nombre", "") or "").lower()
        return "certificación docente" in nombre or "certificacion docente" in nombre

    def clean(self):
        cleaned = super().clean()
        es_cd = self._es_cd()

        # Requeridos base
        base_fields = (
            "doc_dni_legalizado",
            "doc_cert_medico",
            "doc_fotos_carnet",
            "doc_folios_oficio",
        )
        for f in base_fields:
            if not cleaned.get(f):
                self.add_error(f, "Requerido.")

        # Título según carrera
        if es_cd:
            # En CD no se usa título secundario ni adeuda materias
            if not cleaned.get("doc_titulo_terciario_legalizado"):
                self.add_error(
                    "doc_titulo_terciario_legalizado",
                    "Requerido para Certificación Docente.",
                )
            if not cleaned.get("doc_incumbencias"):
                self.add_error(
                    "doc_incumbencias",
                    "Requerido para Certificación Docente.",
                )
        else:
            # Carreras comunes: título secundario obligatorio
            if not cleaned.get("doc_titulo_sec_legalizado"):
                self.add_error(
                    "doc_titulo_sec_legalizado",
                    "Requerido (título secundario).",
                )
            # Si marcó título secundario, no debe haber 'en trámite' ni 'adeuda'
            if cleaned.get("doc_titulo_sec_legalizado"):
                cleaned["titulo_en_tramite"] = False
                if cleaned.get("adeuda_materias"):
                    cleaned["adeuda_materias"] = False
                    cleaned["materias_adeudadas"] = ""
                    cleaned["institucion_origen"] = ""

        # Cálculo estado y condición
        base_ok = all(cleaned.get(f) for f in base_fields)
        titulo_ok = (
            (es_cd and cleaned.get("doc_titulo_terciario_legalizado") and cleaned.get("doc_incumbencias"))
            or ((not es_cd) and cleaned.get("doc_titulo_sec_legalizado"))
        )
        completo = base_ok and titulo_ok and (not cleaned.get("titulo_en_tramite"))

        # En CD la “adeuda materias” no aplica para la condición
        if es_cd:
            condicional = (not completo)
        else:
            condicional = (not completo) or bool(cleaned.get("adeuda_materias"))

        # Nota de compromiso si es condicional
        if condicional and not cleaned.get("nota_compromiso"):
            self.add_error("nota_compromiso", "Obligatoria cuando la condición es CONDICIONAL.")

        # Guardar para usar en save()
        self._calc_legajo_estado = (
            EstudianteProfesorado.LegajoEstado.COMPLETO
            if completo else EstudianteProfesorado.LegajoEstado.INCOMPLETO
        )
        self._calc_condicion_admin = (
            EstudianteProfesorado.CondicionAdmin.CONDICIONAL
            if condicional else EstudianteProfesorado.CondicionAdmin.REGULAR
        )
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        if hasattr(self, "_calc_legajo_estado"):
            inst.legajo_estado = self._calc_legajo_estado
        if hasattr(self, "_calc_condicion_admin"):
            inst.condicion_admin = self._calc_condicion_admin
        if commit:
            inst.save()
        return inst
    """
    Calcula y guarda:
      - legajo_estado (COMPLETO/INCOMPLETO)
      - condicion_admin (REGULAR/CONDICIONAL)
    Aplica reglas especiales para Certificación Docente vs carreras comunes.
    """

    class Meta:
        model = EstudianteProfesorado
        fields = [
            "estudiante",
            "profesorado",
            "cohorte",
            "curso_introductorio",
            # Documentación base
            "doc_dni_legalizado",
            "doc_cert_medico",
            "doc_fotos_carnet",
            "doc_folios_oficio",
            # Títulos
            "doc_titulo_sec_legalizado",        # carreras comunes
            "doc_titulo_terciario_legalizado",  # Certificación Docente
            "doc_incumbencias",                 # Certificación Docente
            # Estados extra
            "titulo_en_tramite",
            "adeuda_materias",
            # Bloque extra
            "materias_adeudadas",
            "institucion_origen",
            # Condicionalidad
            "nota_compromiso",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Validamos en clean(); por defecto no requerimos en el form
        for f in self.fields.values():
            f.required = False

        self.fields["cohorte"].widget.attrs.setdefault("placeholder", "p.ej. 2025")
        self.fields["materias_adeudadas"].widget.attrs.setdefault(
            "placeholder", "Listado de materias"
        )
        self.fields["institucion_origen"].widget.attrs.setdefault(
            "placeholder", "Escuela / Institución"
        )

    # -------- utilidades internas ----------
    @staticmethod
     def _es_cd(self):
        prof = self.cleaned_data.get("profesorado")
        nombre = (getattr(prof, "nombre", "") or "").lower()
        return "certificación docente" in nombre or "certificacion docente" in nombre

    # --------------- validación ---------------
def clean(self):
        cleaned = super().clean()
        es_cd = self._es_cd()

        # Requeridos base
        base = ("doc_dni_legalizado", "doc_cert_medico", "doc_fotos_carnet", "doc_folios_oficio")
        for f in base:
            if not cleaned.get(f):
                self.add_error(f, "Requerido.")

        # Título según carrera
        if es_cd:
            if not cleaned.get("doc_titulo_terciario_legalizado"):
                self.add_error("doc_titulo_terciario_legalizado", "Requerido para Certificación Docente.")
            if not cleaned.get("doc_incumbencias"):
                self.add_error("doc_incumbencias", "Requerido para Certificación Docente.")
        else:
            if not cleaned.get("doc_titulo_sec_legalizado"):
                self.add_error("doc_titulo_sec_legalizado", "Requerido (título secundario).")

        # Cálculo de estado/condición
        base_ok = all(cleaned.get(f) for f in base)
        titulo_ok = (
            (es_cd and cleaned.get("doc_titulo_terciario_legalizado") and cleaned.get("doc_incumbencias")) or
            (not es_cd and cleaned.get("doc_titulo_sec_legalizado"))
        )
        completo = base_ok and titulo_ok and (not cleaned.get("titulo_en_tramite"))
        condicional = (not completo) or bool(cleaned.get("adeuda_materias"))

        # Nota de compromiso si es condicional
        if condicional and not cleaned.get("nota_compromiso"):
            self.add_error("nota_compromiso", "Obligatoria cuando la condición es CONDICIONAL.")

        # Guardamos para usar en save()
        self._calc_legajo_estado = (
            EstudianteProfesorado.LegajoEstado.COMPLETO
            if completo else EstudianteProfesorado.LegajoEstado.INCOMPLETO
        )
        self._calc_condicion_admin = (
            EstudianteProfesorado.CondicionAdmin.CONDICIONAL
            if condicional else EstudianteProfesorado.CondicionAdmin.REGULAR
        )
        return cleaned

    def save(self, commit=True):
        inst = super().save(commit=False)
        # Aplicar lo calculado en clean()
        if hasattr(self, "_calc_legajo_estado"):
            inst.legajo_estado = self._calc_legajo_estado
        if hasattr(self, "_calc_condicion_admin"):
            inst.condicion_admin = self._calc_condicion_admin
        if commit:
            inst.save()
        return inst
        inst = super().save(commit=False)

        # Valores calculados
        inst.legajo_estado = self.cleaned_data.get("legajo_estado", inst.legajo_estado)
        inst.condicion_admin = self.cleaned_data.get(
            "condicion_admin", inst.condicion_admin
        )

        # Refuerza coherencias (igual que clean)
        es_cd = self._es_cd(self.cleaned_data.get("profesorado"))
        if es_cd:
            inst.doc_titulo_sec_legalizado = False
            inst.adeuda_materias = False
            inst.materias_adeudadas = ""
            inst.institucion_origen = ""
        else:
            if inst.doc_titulo_sec_legalizado:
                inst.adeuda_materias = False
                inst.materias_adeudadas = ""
                inst.institucion_origen = ""
                inst.titulo_en_tramite = False
            if inst.adeuda_materias or inst.titulo_en_tramite:
                inst.doc_titulo_sec_legalizado = False

        if commit:
            inst.save()
        return inst


# -----------------------------------------------------------------------------
# Placeholders (para que las importaciones de las vistas no rompan)
# Se reemplazarán por ModelForms reales cuando abordemos cada flujo.
# -----------------------------------------------------------------------------
class InscripcionEspacioForm(forms.Form):
    inscripcion = forms.IntegerField(required=False)
    anio_academico = forms.CharField(required=False)
    espacio = forms.CharField(required=False)

    def save(self, commit: bool = True):
        return None


class CargarCursadaForm(forms.Form):
    inscripcion = forms.IntegerField(required=False)
    espacio = forms.CharField(required=False)
    condicion = forms.CharField(required=False)
    nota_cursada = forms.CharField(required=False)

    def save(self, commit: bool = True):
        return None


class CargarNotaFinalForm(forms.Form):
    inscripcion = forms.IntegerField(required=False)
    espacio = forms.CharField(required=False)
    anio_academico = forms.CharField(required=False)
    condicion = forms.CharField(required=False)
    nota_final = forms.IntegerField(required=False, min_value=0, max_value=10)
    ausente = forms.BooleanField(required=False)
    ausencia_justificada = forms.BooleanField(required=False)
    nota_texto = forms.CharField(required=False)
    disposicion_interna = forms.CharField(required=False)

    def clean(self):
        data = super().clean()
        if data.get("ausente"):
            data["nota_final"] = None
        return data

    def save(self, commit: bool = True):
        return None


class CargarResultadoFinalForm(forms.Form):
    inscripcion = forms.IntegerField(required=False)
    espacio = forms.CharField(required=False)
    anio_academico = forms.CharField(required=False)
    condicion = forms.CharField(required=False)
    nota_final = forms.IntegerField(required=False, min_value=0, max_value=10)
    ausente = forms.BooleanField(required=False)
    ausencia_justificada = forms.BooleanField(required=False)
    nota_texto = forms.CharField(required=False)
    disposicion_interna = forms.CharField(required=False)

    def clean(self):
        data = super().clean()
        if data.get("ausente"):
            data["nota_final"] = None
        return data

    def save(self, commit: bool = True):
        return None

class InscripcionFinalForm(forms.Form):
    """
    Placeholder para 'insc_final'. Mantiene el import vivo y permite
    que el servidor arranque aunque aún no implementemos este flujo.
    Ajustaremos campos cuando integremos la UI de mesas de final.
    """
    inscripcion = forms.IntegerField(required=False)
    espacio = forms.CharField(required=False)
    anio_academico = forms.CharField(required=False)
    mesa_fecha = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def save(self, commit: bool = True):
        # No hace nada aún; se implementará cuando armemos el flujo real.
        return None
