# academia_core/forms_carga.py
from __future__ import annotations

from typing import Any, Optional, Iterable, Dict

from django import forms
from django.core.exceptions import ValidationError, FieldDoesNotExist


# Importá tus modelos reales.
# Estos nombres vienen de lo que mostraste en el proyecto y en los errores previos.
from .models import (
    Estudiante,
    Profesorado,
    EstudianteProfesorado,
    EspacioCurricular,
    InscripcionEspacio,
    InscripcionFinal,
    Movimiento,
)


# =========================
# Helpers de introspección
# =========================

def _model_has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _get_field(model, name: str):
    try:
        return model._meta.get_field(name)
    except Exception:
        return None


def _safe_bool(cd: Dict[str, Any], key: str) -> bool:
    """Toma un booleano de cleaned_data sin explotar si no existe."""
    v = cd.get(key, False)
    return bool(v)


def _set_estado_char_or_fk(instance, field_name: str, code_value: str) -> None:
    """
    Setea un estado que podría ser CharField o FK.
    - Si es CharField: asigna string directamente.
    - Si es FK: intenta buscar por 'codigo' / 'code' / 'slug' / 'nombre'.
    Si no encuentra, no rompe (deja lo que hubiera).
    """
    fld = _get_field(type(instance), field_name)
    if not fld:
        return

    if getattr(fld, "is_relation", False):
        # Es FK: buscar registro por algún campo razonable
        rel_model = fld.remote_field.model  # type: ignore
        candidates = ("codigo", "code", "slug", "nombre", "label")
        found_obj = None
        for cand in candidates:
            if _model_has_field(rel_model, cand):
                try:
                    found_obj = rel_model.objects.filter(**{cand: code_value}).first()
                    if found_obj:
                        break
                except Exception:
                    # Si hay algún fallo, seguimos con el siguiente campo candidato
                    pass
        if found_obj:
            setattr(instance, field_name, found_obj)
    else:
        # Asumimos CharField/TextField: poner string
        try:
            setattr(instance, field_name, code_value)
        except Exception:
            # No romper si por algún motivo el set falla
            pass


# ======================================
# Formulario: Inscripción a Profesorado
# (acción "insc_prof")
# ======================================

class InscripcionProfesoradoForm(forms.ModelForm):
    """
    Lógica de negocio según tu especificación:

    Base (para cualquier trayecto):
      - doc_dni_legalizado
      - doc_cert_medico
      - doc_fotos_carnet
      - doc_folios_oficio

    Profesorados "normales":
      - doc_titulo_sec_legalizado  (requerido para legajo completo)

    Certificación Docente:
      - doc_titulo_terciario_legalizado  (requerido)
      - doc_incumbencias                 (requerido)
      - (NO se usa título secundario aquí)

    Condición administrativa:
      - "REGULAR" si legajo completo y NO adeuda materias
      - "CONDICIONAL" en caso contrario
      - Si "CONDICIONAL" => se exige nota_compromiso = True

    Adeuda materias:
      - Si adeuda_materias = True => pedir materias_adeudadas + institucion_origen

    Título en trámite:
      - Impide legajo completo (aunque tenga el resto).
    """

    class Meta:
        model = EstudianteProfesorado
        # Muy importante: usamos __all__ para no romper si hay diferencias de campos.
        fields = "__all__"

    # --- Si tu modelo NO tuviera alguno de estos campos, el formulario igual no rompe ---
    # (limpiamos en __init__, y en clean usamos .get() con default False)
    # Estos son solo "alias" para etiquetar más lindo en el form si existen.
    LABELS_READABLE = {
        "doc_dni_legalizado": "Doc. DNI legalizado",
        "doc_cert_medico": "Certificado médico",
        "doc_fotos_carnet": "Foto carnet",
        "doc_folios_oficio": "Folio oficio",
        "doc_titulo_sec_legalizado": "Título secundario legalizado",
        "doc_titulo_terciario_legalizado": "Título terciario/universitario legalizado",
        "doc_incumbencias": "Incumbencias presentadas",
        "titulo_en_tramite": "Título en trámite",
        "adeuda_materias": "Adeuda materias",
        "nota_compromiso": "DDJJ / Nota compromiso",
        "materias_adeudadas": "Materias adeudadas",
        "institucion_origen": "Escuela / Institución",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Etiquetas amigables si los campos existen
        for fname, label in self.LABELS_READABLE.items():
            if fname in self.fields:
                self.fields[fname].label = label

        # Widgets y obligatoriedad de los campos "extra"
        for name in ("materias_adeudadas", "institucion_origen"):
            if name in self.fields:
                self.fields[name].required = False
                if getattr(self.fields[name].widget, "attrs", None) is not None:
                    self.fields[name].widget.attrs.setdefault("rows", 2)

        for name in ("nota_compromiso", "doc_incumbencias"):
            if name in self.fields:
                self.fields[name].required = False

        # Por si el template necesita un ordenamiento "visual" (no obligatorio)
        preferred_order = [
            "estudiante", "profesorado", "cohorte",
            # Documentación base
            "doc_dni_legalizado", "doc_cert_medico", "doc_fotos_carnet", "doc_folios_oficio",
            # Títulos
            "doc_titulo_sec_legalizado", "doc_titulo_terciario_legalizado", "doc_incumbencias",
            "titulo_en_tramite",
            # Condicionalidad
            "adeuda_materias", "materias_adeudadas", "institucion_origen", "nota_compromiso",
        ]
        # Mantenemos el orden de los que existan y agregamos el resto al final
        existing = [k for k in preferred_order if k in self.fields]
        rest = [k for k in self.fields.keys() if k not in existing]
        self.order_fields(existing + rest)

    # ---------------------
    # Helpers internos
    # ---------------------
    def _es_certificacion_docente(self, prof: Optional[Profesorado]) -> bool:
        """
        Devuelve True si el profesorado es “certificación docente”.
        Idealmente, si tu modelo tiene un booleano `es_certificacion`, úsalo.
        Fallback por texto en el nombre: contiene “certificación docente”.
        """
        if not prof:
            return False
        if hasattr(prof, "es_certificacion"):
            try:
                return bool(prof.es_certificacion)
            except Exception:
                pass
        try:
            name = (prof.nombre or "").lower()
            return "certificación docente" in name or "certificacion docente" in name
        except Exception:
            return False

    # ---------------------
    # Validación de negocio
    # ---------------------
    def clean(self):
        cleaned = super().clean()

        # Extracciones seguras (booleanos)
        base_ok = (
            _safe_bool(cleaned, "doc_dni_legalizado")
            and _safe_bool(cleaned, "doc_cert_medico")
            and _safe_bool(cleaned, "doc_fotos_carnet")
            and _safe_bool(cleaned, "doc_folios_oficio")
        )

        profesorado = cleaned.get("profesorado")
        es_cd = self._es_certificacion_docente(profesorado)

        titulo_ok = False
        if es_cd:
            # Certificación docente: terciario + incumbencias
            titulo_ok = (
                _safe_bool(cleaned, "doc_titulo_terciario_legalizado")
                and _safe_bool(cleaned, "doc_incumbencias")
            )
            # (Si existiera el campo de secundario, no lo consideramos)
        else:
            # Profesorados normales: secundario
            titulo_ok = _safe_bool(cleaned, "doc_titulo_sec_legalizado")

        # Título en trámite impide legajo completo
        if _safe_bool(cleaned, "titulo_en_tramite"):
            legajo_completo = False
        else:
            legajo_completo = base_ok and titulo_ok

        adeuda = _safe_bool(cleaned, "adeuda_materias")

        # Condición administrativa
        condicion_admin = "REGULAR" if (legajo_completo and not adeuda) else "CONDICIONAL"

        # Si adeuda materias => obligar campos de detalle
        if adeuda:
            if "materias_adeudadas" in self.fields and not cleaned.get("materias_adeudadas"):
                self.add_error("materias_adeudadas", "Obligatorio si adeuda materias.")
            if "institucion_origen" in self.fields and not cleaned.get("institucion_origen"):
                self.add_error("institucion_origen", "Obligatorio si adeuda materias.")

        # Si queda condicional => obligar nota_compromiso
        if condicion_admin == "CONDICIONAL" and "nota_compromiso" in self.fields:
            if not _safe_bool(cleaned, "nota_compromiso"):
                self.add_error("nota_compromiso", "Obligatorio para condición condicional.")

        # Guardamos “flags” en cleaned_data para usarlos en save()
        cleaned["_legajo_estado_code"] = "COMPLETO" if legajo_completo else "INCOMPLETO"
        cleaned["_condicion_admin_code"] = condicion_admin

        return cleaned

    # ---------------------
    # Persistencia
    # ---------------------
    def save(self, commit: bool = True) -> EstudianteProfesorado:
        obj: EstudianteProfesorado = super().save(commit=False)

        # Setear legajo_estado / condicion_admin si existieran
        legajo_code = self.cleaned_data.get("_legajo_estado_code")
        cond_code = self.cleaned_data.get("_condicion_admin_code")

        if legajo_code and _model_has_field(type(obj), "legajo_estado"):
            _set_estado_char_or_fk(obj, "legajo_estado", legajo_code)

        if cond_code and _model_has_field(type(obj), "condicion_admin"):
            _set_estado_char_or_fk(obj, "condicion_admin", cond_code)

        if commit:
            obj.save()
        return obj


# ======================================
# Formulario: Estudiante (alta/edición)
# (acción "add_est")
# ======================================

class EstudianteForm(forms.ModelForm):
    """
    ModelForm genérico para Estudiante.
    Usamos fields="__all__" para evitar FieldError si el modelo difiere.
    Tu template ya coloca etiquetas y orden.
    """
    class Meta:
        model = Estudiante
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Etiquetas útiles si existen estos campos
        labels = {
            "dni": "DNI",
            "apellido": "Apellido",
            "nombre": "Nombre",
            "fecha_nacimiento": "Fecha de nacimiento",
            "lugar_nacimiento": "Lugar de nacimiento",
            "email": "Email",
            "telefono": "Teléfono",
            "localidad": "Localidad",
            "contacto_emergencia_tel": "Tel. emergencia",
            "contacto_emergencia_parentesco": "Parentesco (opcional)",
            "activo": "Activo",
            "foto": "Foto",
        }
        for k, v in labels.items():
            if k in self.fields:
                self.fields[k].label = v


# ======================================
# Formulario: Inscripción a Materia
# (acción "insc_esp")
# ======================================

class InscripcionEspacioForm(forms.ModelForm):
    """
    Inscribir a cursada: tu JS acota 'estado' a EN_CURSO/BAJA.
    Aquí reforzamos esa restricción si el campo existe.
    """
    class Meta:
        model = InscripcionEspacio
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si el modelo tiene el campo 'estado', limitamos choices visualmente
        if "estado" in self.fields:
            try:
                self.fields["estado"].choices = [
                    ("EN_CURSO", "En curso"),
                    ("BAJA", "Baja"),
                ]
            except Exception:
                # Si por algún motivo no acepta reasignar choices, ignoramos silenciosamente
                pass

    def clean(self):
        cleaned = super().clean()
        # En server, reforzar que estado sea EN_CURSO/BAJA si existe
        if "estado" in self.fields:
            val = cleaned.get("estado")
            if val not in (None, "", "EN_CURSO", "BAJA"):
                raise ValidationError("Estado inválido. Solo EN_CURSO o BAJA.")
        return cleaned


# ======================================
# Formulario: Inscripción a Final
# (acción "insc_final")
# ======================================

class InscripcionFinalForm(forms.ModelForm):
    """
    ModelForm genérico para inscribir a mesa de final.
    Si luego agregás validaciones de negocio (regularidad vigente, intentos, etc.),
    podés extender clean() acá.
    """
    class Meta:
        model = InscripcionFinal
        fields = "__all__"


# ======================================
# Formularios de carga de cursada / final
# (acciones "cargar_cursada", "cargar_nota_final", "cargar_final_resultado")
# ======================================

class MovimientoForm(forms.ModelForm):
    """
    En varios proyectos se usa 'Movimiento' para registrar regularidad/finales.
    Dejamos un ModelForm flexible para que no rompa por diferencias de campos.
    """
    class Meta:
        model = Movimiento
        fields = "__all__"


# Aliases para que las vistas puedan importar sin romper
# Si tus vistas esperan nombres específicos, esto los resuelve.
CargarCursadaForm = MovimientoForm           # acción "cargar_cursada"
CargarNotaFinalForm = InscripcionFinalForm   # acción "cargar_nota_final"
RegistrarResultadoFinalForm = InscripcionFinalForm  # acción "cargar_final_resultado"


# === SHIM: CargarResultadoFinalForm (para destrabar el import en views_panel) ===
from django import forms

try:
    from .models import (
        EstudianteProfesorado,
        EspacioCurricular,
        InscripcionEspacio,
        InscripcionFinal,
        Movimiento,
    )
except Exception:
    # Si por alguna razón el import de modelos falla,
    # dejamos las referencias en None para que la importación del módulo no se rompa.
    EstudianteProfesorado = None
    EspacioCurricular = None
    InscripcionEspacio = None
    InscripcionFinal = None
    Movimiento = None


class CargarResultadoFinalForm(forms.Form):
    """
    Formulario 'dummy' para que el import desde views_panel no falle.
    Incluye los nombres de campos que el template/JS esperan:
      - inscripcion, espacio, anio_academico
      - condicion, nota_final, ausente, ausencia_justificada
      - nota_texto, disposicion_interna

    Todos los campos son optional (required=False) para no bloquear validaciones
    mientras terminamos la lógica de guardado.
    """

    # Selecciones base (los querysets se setean en __init__)
    inscripcion = forms.ModelChoiceField(
        queryset=None, required=False, label="Inscripción"
    )
    espacio = forms.ModelChoiceField(
        queryset=None, required=False, label="Espacio"
    )
    anio_academico = forms.IntegerField(required=False, label="Año académico")

    # Datos del resultado final
    condicion = forms.CharField(required=False, label="Condición")
    nota_final = forms.DecimalField(required=False, min_value=0, max_value=10, decimal_places=2, label="Nota final")
    ausente = forms.BooleanField(required=False, label="Ausente")
    ausencia_justificada = forms.BooleanField(required=False, label="Ausencia justificada")
    nota_texto = forms.CharField(required=False, label="Nota (texto)")
    disposicion_interna = forms.CharField(required=False, label="Disposición interna")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Si los modelos existen, poblamos querysets; si no, evitamos romper.
        if InscripcionEspacio is not None:
            self.fields["inscripcion"].queryset = InscripcionEspacio.objects.all()
        else:
            self.fields["inscripcion"].queryset = []

        if EspacioCurricular is not None:
            self.fields["espacio"].queryset = EspacioCurricular.objects.all()
        else:
            self.fields["espacio"].queryset = []

    def clean(self):
        """
        Validaciones mínimas no bloqueantes.
        La lógica real de negocio (equivalencias, ausente/nota, etc.) puede
        ir después cuando conectemos con el modelo Movimiento.
        """
        data = super().clean()

        # Coherencias suaves: si marca "ausente", ignoramos nota_final
        if data.get("ausente"):
            data["nota_final"] = None

        # Si la condición es 'Equivalencia', permitimos nota_texto/disposicion_interna
        # (no forzamos nada todavía)
        return data

    def save(self, commit=True):
        """
        Placeholder para que views_panel pueda llamar form.save() sin romper.
        Cuando quieras persistir, acá se crea el Movimiento correspondiente.
        """
        # Ejemplo (comentado) de cómo podrías guardar un Movimiento:
        # if Movimiento is None:
        #     return None
        # mov = Movimiento(
        #     inscripcion=self.cleaned_data.get("inscripcion"),
        #     espacio=self.cleaned_data.get("espacio"),
        #     anio_academico=self.cleaned_data.get("anio_academico"),
        #     condicion=self.cleaned_data.get("condicion"),
        #     nota_final=self.cleaned_data.get("nota_final"),
        #     ausente=self.cleaned_data.get("ausente") or False,
        #     ausencia_justificada=self.cleaned_data.get("ausencia_justificada") or False,
        #     nota_texto=self.cleaned_data.get("nota_texto") or "",
        #     disposicion_interna=self.cleaned_data.get("disposicion_interna") or "",
        # )
        # if commit:
        #     mov.save()
        # return mov
        return None