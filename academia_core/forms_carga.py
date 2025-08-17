from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

# ### NOTA: Se ajustaron los imports a los modelos realmente usados en los formularios ###
from .models import (
    Estudiante,
    Profesorado,
    EspacioCurricular,
    EstudianteProfesorado,
    InscripcionEspacio,
    InscripcionFinal,
    Movimiento,
)
from .label_utils import espacio_etiqueta
from .models import _tiene_regularidad_vigente, _tiene_aprobada
from .correlativas import evaluar_correlatividades, should_enforce


# ### Mantenemos los helpers que todavía se usan ###
def _pop_req(kwargs):
    kwargs.pop("request", None); kwargs.pop("user", None)
    return None


# ===================== Formularios de Entidades Básicas =====================

class EstudianteForm(forms.ModelForm):
    # ### INICIO DE LA ACTUALIZACIÓN SOLICITADA ###
    class Meta:
        model = Estudiante
        fields = [
            "dni", "apellido", "nombre",
            "fecha_nacimiento", "lugar_nacimiento",
            "email", "telefono", "localidad",
            # === NUEVOS CAMPOS ===
            "contacto_emergencia_tel", "contacto_emergencia_parentesco",
            "activo", "foto",
        ]
        widgets = {
            "contacto_emergencia_tel": forms.TextInput(attrs={
                "placeholder": "Ej: 2964-123456"
            }),
            "contacto_emergencia_parentesco": forms.TextInput(attrs={
                "placeholder": "Ej: madre, padre, tutor…"
            }),
        }
        labels = {
            "contacto_emergencia_tel": "Tel. de emergencia",
            "contacto_emergencia_parentesco": "Parentesco",
        }
    # ### FIN DE LA ACTUALIZACIÓN SOLICITADA ###


class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        _pop_req(kwargs); super().__init__(*args, **kwargs)


# ===================== Formularios de Carga y Movimientos =====================

# -------------------------
# Inscribir a materia (cursada)
# -------------------------
class InscripcionEspacioForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = ["inscripcion", "anio_academico", "espacio", "fecha", "estado"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "estado": forms.Select(),  # Las opciones vienen del modelo
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Asegura que el campo 'estado' siempre tenga choices válidos como fallback.
        if "estado" in self.fields:
            base = [("", "---------"), ("EN_CURSO", "En curso"), ("BAJA", "Baja")]
            try:
                if not list(self.fields["estado"].choices):
                    self.fields["estado"].choices = base
            except Exception:
                self.fields["estado"].choices = base

        # Lógica para filtrar espacios según la inscripción seleccionada
        if "espacio" in self.fields:
            self.fields["espacio"].label_from_instance = espacio_etiqueta
            
            insc_id = self.data.get(self.add_prefix("inscripcion")) or self.initial.get("inscripcion")
            if insc_id:
                try:
                    insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
                    qs = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
                    self.fields["espacio"].queryset = qs.order_by("anio","cuatrimestre","nombre")
                except EstudianteProfesorado.DoesNotExist:
                    self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            else:
                self.fields["espacio"].queryset = EspacioCurricular.objects.none()

    # 17.1.A — Validación de correlativas (server-side, bloqueante si corresponde)
    def clean(self):
        cleaned = super().clean()
        insc = cleaned.get("inscripcion")
        espacio = cleaned.get("espacio")
        estado = cleaned.get("estado")

        # Si es una inscripción "activa" (no BAJA), evaluar correlativas
        if insc and espacio and (estado or "") != "BAJA":
            ok, detalles = evaluar_correlatividades(insc, espacio)
            if not ok:
                # Armar mensaje legible con los faltantes
                faltantes = [d.get("motivo") for d in detalles if not d.get("cumplido")]
                msg = "No cumple correlatividades para cursar: " + "; ".join(f for f in faltantes if f)
                if should_enforce():
                    raise ValidationError(msg)
                # Si no se enforcea, al menos mostrar como error del form (bloquea igual por consistencia)
                raise ValidationError(msg)

        return cleaned

# -------------------------
# Cargar/editar resultado de cursada (regularidad/promoción, etc.)
# -------------------------
class CargarCursadaForm(forms.ModelForm):
    """
    Este formulario es para cargar el RESULTADO de una cursada (un Movimiento).
    """
    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num", "nota_texto"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "condicion": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aquí puedes agregar lógica para filtrar las condiciones de tipo "Cursada"
        # si es necesario.
        pass


# -------------------------
# Inscribir a mesa de final
# -------------------------
class InscripcionFinalForm(forms.ModelForm):
    class Meta:
        model = InscripcionFinal
        fields = ["inscripcion_cursada", "fecha_examen", "estado", "nota_final"]
        widgets = {
            "fecha_examen": forms.DateInput(attrs={"type": "date"}),
        }

    # 17.1.B — Reglas para inscripción a final
    def clean(self):
        cleaned = super().clean()
        insc_cursada = cleaned.get("inscripcion_cursada")
        fecha = cleaned.get("fecha_examen")
        estado = cleaned.get("estado")
        nota_final = cleaned.get("nota_final")

        if not insc_cursada or not fecha:
            return cleaned  # ya lo validará el required de los campos

        insc = insc_cursada.inscripcion
        espacio = insc_cursada.espacio

        # (1) Regularidad vigente (regla 2 años)
        if not _tiene_regularidad_vigente(insc, espacio, fecha):
            raise ValidationError("No posee regularidad vigente (2 años) para rendir este final en la fecha indicada.")

        # (2) Ya aprobado previamente (no inscribir de nuevo)
        if _tiene_aprobada(insc, espacio, hasta_fecha=fecha):
            raise ValidationError("El espacio ya figura aprobado; no corresponde nueva inscripción a final.")

        # (3) Límite de intentos (opcional por settings)
        max_intentos = getattr(settings, "ACADEMIA_MAX_INTENTOS_FINALES", None)
        if max_intentos:
            prev = (InscripcionFinal.objects
                    .filter(inscripcion_cursada=insc_cursada, fecha_examen__lt=fecha)
                    .order_by("-fecha_examen"))
            # Contamos intentos “realizados” (ausente o desaprobado). INSCRIPTO futuro no cuenta.
            usados = prev.filter(estado__in=["DESAPROBADO", "AUSENTE"]).count()
            if usados >= int(max_intentos):
                ult = prev.first()
                ult_txt = f" Último intento: {ult.fecha_examen} ({ult.estado})." if ult else ""
                raise ValidationError(f"Se alcanzó el máximo de intentos permitidos para este final ({max_intentos}).{ult_txt}")

        # (4) Coherencia estado/nota (sanidad mínima)
        if estado == "AUSENTE" and nota_final:
            raise ValidationError("Si marcás AUSENTE, no debe cargarse nota.")
        if estado == "APROBADO" and (nota_final is None or nota_final < 6):
            raise ValidationError("Estado APROBADO requiere nota final ≥ 6.")
        if estado == "DESAPROBADO" and (nota_final is not None and nota_final >= 6):
            raise ValidationError("Estado DESAPROBADO requiere nota final < 6 o vacía.")

        return cleaned

# ===================== Formularios Livianos para Carga de Notas (Actualizados) =====================

class CargarNotaFinalForm(forms.Form):
    """
    Form liviano para anotar nota/condición de un final.
    """
    condicion = forms.ChoiceField(
        required=False,
        choices=[
            ("", "---------"),
            ("REGULAR", "Regular"),
            ("LIBRE", "Libre"),
            ("EQUIVALENCIA", "Equivalencia"),
        ],
        label="Condición"
    )
    nota_final = forms.IntegerField(
        required=False,
        min_value=0, max_value=10,
        label="Nota final"
    )
    folio = forms.CharField(required=False, label="Folio")
    libro = forms.CharField(required=False, label="Libro")


class CargarResultadoFinalForm(forms.Form):
    """
    Placeholder para el flujo de 'resultado final'.
    """
    resultado = forms.ChoiceField(
        required=False,
        choices=[
            ("", "---------"),
            ("APROBADO", "Aprobado"),
            ("DESAPROBADO", "Desaprobado"),
        ],
        label="Resultado"
    )
    nota_final = forms.IntegerField(
        required=False,
        min_value=0, max_value=10,
        label="Nota final"
    )