# academia_core/forms_carga.py
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from .models import EstudianteProfesorado

# Estos imports pueden no existir aún; los “try” evitan que truene la importación.
try:  # pragma: no cover
    from .models import Estudiante
except Exception:  # noqa: BLE001
    Estudiante = None  # type: ignore

try:  # pragma: no cover
    from .models import (
        InscripcionEspacio,
        Movimiento,  # modelos del resto del flujo
        EspacioCurricular,
        EstadoInscripcion,  # choices del estado de cursada
        Condicion,  # Usado en MovimientoForm
    )
except Exception:  # noqa: BLE001
    InscripcionEspacio = None
    Movimiento = None
    EspacioCurricular = None
    Condicion = None

    class _EstadoDummy:
        EN_CURSO = "EN_CURSO"
        BAJA = "BAJA"
        choices = (("EN_CURSO", "En curso"), ("BAJA", "Baja"))

    EstadoInscripcion = _EstadoDummy


# Helper opcional para filtrar espacios; si no existe, hacemos fallback
try:  # pragma: no cover
    from academia_core.utils_inscripciones import espacios_habilitados_para
except Exception:  # noqa: BLE001
    espacios_habilitados_para = None


# --- Formularios de Entidades Principales ---

if Estudiante:

    class EstudianteForm(forms.ModelForm):
        class Meta:
            model = Estudiante
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


class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = [
            "estudiante",
            "profesorado",
            "cohorte",
            "curso_introductorio",
            "doc_dni_legalizado",
            "doc_cert_medico",
            "doc_fotos_carnet",
            "doc_folios_oficio",
            "doc_titulo_sec_legalizado",
            "doc_titulo_terciario_legalizado",
            "doc_incumbencias",
            "titulo_en_tramite",
            "adeuda_materias",
            "materias_adeudadas",
            "institucion_origen",
            "nota_compromiso",
        ]

    # ... (el resto de la clase InscripcionProfesoradoForm que ya tenías está bien) ...


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
            widgets = {"estado": forms.Select(attrs={"class": "form-select w-full"})}

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            # Hasta elegir inscripcion: sin opciones
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()

            # Estado: choices + initial defensivo
            estado_field = self.fields.get("estado")
            if estado_field:
                estado_field.choices = list(getattr(EstadoInscripcion, "choices", ()))
                if not getattr(self.instance, "pk", None) and not self.initial.get(
                    "estado"
                ):
                    estado_field.initial = getattr(
                        EstadoInscripcion, "EN_CURSO", "EN_CURSO"
                    )

            # Data-attribute para el fetch dinámico de espacios
            url_base = reverse("api_espacios_por_inscripcion", args=[0])
            if "inscripcion" in self.fields:
                self.fields["inscripcion"].widget.attrs.update(
                    {"data-espacios-url": url_base}
                )

            # Si ya conocemos la inscripción, completar queryset de espacios
            insc_id = None
            if self.is_bound:
                insc_id = self.data.get("inscripcion")
            elif getattr(self.instance, "pk", None):
                insc_id = self.instance.inscripcion_id

            if insc_id:
                try:
                    est_prof = EstudianteProfesorado.objects.select_related(
                        "profesorado"
                    ).get(pk=insc_id)
                    if espacios_habilitados_para:
                        # Pasa la inscripción real (con estudiante/carrera) al helper
                        self.fields["espacio"].queryset = espacios_habilitados_para(
                            est_prof
                        )
                    else:
                        self.fields["espacio"].queryset = (
                            EspacioCurricular.objects.filter(
                                profesorado=est_prof.profesorado
                            )
                        )
                except EstudianteProfesorado.DoesNotExist:
                    pass

        # --- Validaciones defensivas ---
        def clean_estado(self):
            value = self.cleaned_data.get("estado")
            return value or getattr(EstadoInscripcion, "EN_CURSO", "EN_CURSO")

        def clean(self):
            cleaned = super().clean()
            estado = cleaned.get("estado")
            BAJA = getattr(EstadoInscripcion, "BAJA", "BAJA")
            EN_CURSO = getattr(EstadoInscripcion, "EN_CURSO", "EN_CURSO")

            if (
                estado == BAJA
                and "fecha_baja" in self.fields
                and not cleaned.get("fecha_baja")
            ):
                self.add_error("fecha_baja", "Requerido si el estado es Baja.")

            if estado == EN_CURSO:
                if "fecha_baja" in self.fields:
                    cleaned["fecha_baja"] = None
                if "motivo_baja" in self.fields:
                    cleaned["motivo_baja"] = ""
            return cleaned

        def save(self, commit: bool = True):
            obj = super().save(commit=False)

            # Normalizaciones cruzadas por estado
            if (
                obj.estado == getattr(EstadoInscripcion, "BAJA", "BAJA")
                and getattr(obj, "fecha_baja", None) is None
            ):
                obj.fecha_baja = timezone.now().date()

            if obj.estado == getattr(
                EstadoInscripcion, "EN_CURSO", "EN_CURSO"
            ) and getattr(obj, "fecha_baja", None):
                obj.fecha_baja = None
                if hasattr(obj, "motivo_baja"):
                    try:
                        obj.motivo_baja = ""
                    except Exception:
                        pass

            if commit:
                obj.save()
            return obj


class CargaNotaForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "tipo", "fecha", "condicion", "nota_num"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "inscripcion"
        ].queryset = EstudianteProfesorado.objects.all().select_related(
            "estudiante", "profesorado"
        )
        self.fields["espacio"].queryset = EspacioCurricular.objects.none()
        self.fields["condicion"].queryset = Condicion.objects.none()

        if "inscripcion" in self.data:
            try:
                inscripcion_id = int(self.data.get("inscripcion"))
                inscripcion = EstudianteProfesorado.objects.get(id=inscripcion_id)
                self.fields["espacio"].queryset = EspacioCurricular.objects.filter(
                    plan=inscripcion.plan
                ).order_by("nombre")
            except (ValueError, TypeError, EstudianteProfesorado.DoesNotExist):
                pass
        elif self.instance.pk and self.instance.inscripcion:
            self.fields["espacio"].queryset = EspacioCurricular.objects.filter(
                plan=self.instance.inscripcion.plan
            ).order_by("nombre")

        if "tipo" in self.data:
            try:
                tipo = self.data.get("tipo")
                self.fields["condicion"].queryset = Condicion.objects.filter(
                    tipo=tipo
                ).order_by("nombre")
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.tipo:
            self.fields["condicion"].queryset = Condicion.objects.filter(
                tipo=self.instance.tipo
            ).order_by("nombre")


# --- FORMULARIO FALTANTE ---
if Movimiento and Condicion:

    class MovimientoForm(forms.ModelForm):
        class Meta:
            model = Movimiento
            fields = [
                "tipo",
                "fecha",
                "condicion",
                "nota_num",
                "nota_texto",
                "folio",
                "libro",
                "disposicion_interna",
                "ausente",
                "ausencia_justificada",
            ]
            widgets = {
                "fecha": forms.DateInput(attrs={"type": "date"}),
            }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Filtrar condiciones según el tipo seleccionado (si corresponde)
            if "tipo" in self.data:
                try:
                    tipo_seleccionado = self.data.get("tipo")
                    self.fields["condicion"].queryset = Condicion.objects.filter(
                        tipo=tipo_seleccionado
                    ).order_by("nombre")
                except (ValueError, TypeError):
                    pass
            elif getattr(self.instance, "pk", None):
                self.fields["condicion"].queryset = Condicion.objects.filter(
                    tipo=self.instance.tipo
                ).order_by("nombre")
