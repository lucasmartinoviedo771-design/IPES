# academia_core/forms_carga.py
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import EstudianteProfesorado

# Estos imports pueden no existir aún; los “try” evitan que truene la importación.
try:  # pragma: no cover
    from .models import Estudiante
except Exception:  # noqa: BLE001
    Estudiante = None  # type: ignore

try:  # pragma: no cover
    from .models import (
        InscripcionEspacio,
        Movimiento,               # modelos del resto del flujo
        EspacioCurricular,
        EstadoInscripcion,        # choices del estado de cursada
    )
except Exception:  # noqa: BLE001
    InscripcionEspacio = None  # type: ignore
    Movimiento = None  # type: ignore
    EspacioCurricular = None  # type: ignore

    class _EstadoDummy:  # fallback para no romper imports
        EN_CURSO = "EN_CURSO"
        BAJA = "BAJA"

    EstadoInscripcion = _EstadoDummy  # type: ignore


# Helper opcional para filtrar espacios; si no existe, hacemos fallback
try:  # pragma: no cover
    from academia_core.utils_inscripciones import espacios_habilitados_para
except Exception:  # noqa: BLE001
    espacios_habilitados_para = None  # type: ignore


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
# Inscripción a Profesorado (calcula legajo_estado y condicion_admin)
# -----------------------------------------------------------------------------
class InscripcionProfesoradoForm(forms.ModelForm):
    """
    Calcula y guarda:
      - legajo_estado (COMPLETO/INCOMPLETO)
      - condicion_admin (REGULAR/CONDICIONAL)
    Reglas especiales para Certificación Docente vs. carreras comunes.
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
            # Bloque extra (si adeuda)
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

    def _es_cd(self) -> bool:
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
            # En CD no aplica secundario ni adeuda
            if not cleaned.get("doc_titulo_terciario_legalizado"):
                self.add_error(
                    "doc_titulo_terciario_legalizado",
                    "Requerido para Certificación Docente.",
                )
            if not cleaned.get("doc_incumbencias"):
                self.add_error(
                    "doc_incumbencias", "Requerido para Certificación Docente."
                )
            cleaned["doc_titulo_sec_legalizado"] = False
            cleaned["adeuda_materias"] = False
            cleaned["materias_adeudadas"] = ""
            cleaned["institucion_origen"] = ""
        else:
            # Si tiene título secundario, NO puede estar en trámite ni adeudar
            if cleaned.get("doc_titulo_sec_legalizado"):
                cleaned["titulo_en_tramite"] = False
                if cleaned.get("adeuda_materias"):
                    cleaned["adeuda_materias"] = False
                    cleaned["materias_adeudadas"] = ""
                    cleaned["institucion_origen"] = ""
            else:
                # Sin título: puede adeudar -> debe completar campos
                if cleaned.get("adeuda_materias"):
                    if not cleaned.get("materias_adeudadas"):
                        self.add_error(
                            "materias_adeudadas", "Requerido cuando adeuda materias."
                        )
                    if not cleaned.get("institucion_origen"):
                        self.add_error(
                            "institucion_origen", "Requerido cuando adeuda materias."
                        )

        # Cálculo de estado/condición
        base_ok = all(cleaned.get(f) for f in base_fields)
        titulo_ok = (
            es_cd
            and cleaned.get("doc_titulo_terciario_legalizado")
            and cleaned.get("doc_incumbencias")
        ) or ((not es_cd) and cleaned.get("doc_titulo_sec_legalizado"))
        completo = base_ok and titulo_ok and (not cleaned.get("titulo_en_tramite"))
        condicional = (not completo) or (
            (not es_cd) and bool(cleaned.get("adeuda_materias"))
        )

        # Nota de compromiso si es condicional
        if condicional and not cleaned.get("nota_compromiso"):
            self.add_error(
                "nota_compromiso", "Obligatoria cuando la condición es CONDICIONAL."
            )

        # Guardar para save()
        self._calc_legajo_estado = (
            EstudianteProfesorado.LegajoEstado.COMPLETO
            if completo
            else EstudianteProfesorado.LegajoEstado.INCOMPLETO
        )
        self._calc_condicion_admin = (
            EstudianteProfesorado.CondicionAdmin.CONDICIONAL
            if condicional
            else EstudianteProfesorado.CondicionAdmin.REGULAR
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


# -----------------------------------------------------------------------------
# Inscripción a Espacio (cursada por año): ModelForm con filtro de Espacio + Estado
# -----------------------------------------------------------------------------
if InscripcionEspacio and EspacioCurricular:

    class InscripcionEspacioForm(forms.ModelForm):
        class Meta:
            model = InscripcionEspacio
            fields = (
                "inscripcion",
                "anio_academico",
                "espacio",
                "estado",
                "fecha_baja",
                "motivo_baja",
            )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Hasta que elijan "inscripcion", el queryset queda vacío
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()

            # Choices e initial para estado (si el enum lo provee)
            estado_field = self.fields.get("estado")
            choices = getattr(EstadoInscripcion, "choices", None)
            if estado_field and choices is not None:
                estado_field.choices = choices
            # Valor por defecto EN_CURSO si existe
            en_curso = getattr(EstadoInscripcion, "EN_CURSO", None)
            if estado_field and en_curso is not None and not estado_field.initial:
                estado_field.initial = en_curso

            insc_id = None
            if self.is_bound:
                # admite name="inscripcion" o "inscripcion_id"
                insc_id = self.data.get("inscripcion") or self.data.get("inscripcion_id")
            elif self.instance and getattr(self.instance, "pk", None):
                insc_id = self.instance.inscripcion_id

            if insc_id:
                try:
                    est_prof = (
                        EstudianteProfesorado.objects
                        .select_related("profesorado")
                        .get(pk=insc_id)
                    )
                    if espacios_habilitados_para:
                        qs = espacios_habilitados_para(est_prof)
                    else:
                        # fallback: todos los espacios del mismo profesorado
                        qs = EspacioCurricular.objects.filter(
                            profesorado=est_prof.profesorado
                        )
                    self.fields["espacio"].queryset = qs
                except EstudianteProfesorado.DoesNotExist:
                    pass

        def save(self, commit: bool = True):
            obj = super().save(commit=False)

            # Si marcan BAJA y no hay fecha_baja → hoy
            if obj.estado == getattr(EstadoInscripcion, "BAJA", "BAJA") and getattr(obj, "fecha_baja", None) is None:
                obj.fecha_baja = timezone.now().date()

            # Si vuelve a EN_CURSO y tenía fecha_baja → limpiar
            if obj.estado == getattr(EstadoInscripcion, "EN_CURSO", "EN_CURSO") and getattr(obj, "fecha_baja", None):
                obj.fecha_baja = None
                # opcional: limpiar motivo_baja al volver a EN_CURSO
                if hasattr(obj, "motivo_baja"):
                    try:
                        obj.motivo_baja = ""
                    except Exception:
                        pass

            if commit:
                obj.save()
            return obj


# -----------------------------------------------------------------------------
# Placeholders (para que las importaciones de las vistas no rompan)
# Se reemplazarán por ModelForms reales cuando abordemos cada flujo.
# -----------------------------------------------------------------------------
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
    mesa_fecha = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    observaciones = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def save(self, commit: bool = True):
        # No hace nada aún; se implementará cuando armemos el flujo real.
        return None


# -----------------------------------------------------------------------------
# Fallback “blindado” para InscripcionEspacioForm:
# solo define el placeholder si NO existe la ModelForm anterior.
# -----------------------------------------------------------------------------
if "InscripcionEspacioForm" not in globals():
    class InscripcionEspacioForm(forms.Form):  # type: ignore[misc]
        inscripcion = forms.IntegerField(required=False)
        anio_academico = forms.CharField(required=False)
        espacio = forms.CharField(required=False)
        estado = forms.CharField(required=False)
        fecha_baja = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
        motivo_baja = forms.CharField(required=False)

        def save(self, commit: bool = True):
            return None
