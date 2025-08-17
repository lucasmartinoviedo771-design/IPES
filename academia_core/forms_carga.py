# academia_core/forms_carga.py

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
    # === IMPORTS REQUERIDOS ===
    LegajoEstado,
    CondicionAdmin,
)
from .label_utils import espacio_etiqueta
from .models import _tiene_regularidad_vigente, _tiene_aprobada
from .correlativas import evaluar_correlatividades, should_enforce


# ### Mantenemos los helpers que todavía se usan ###
def _pop_req(kwargs):
    kwargs.pop("request", None); kwargs.pop("user", None)
    return None

# --- Utils internos ---
def _bool(v):  # tolerante a None/"on"/True/False
    if isinstance(v, bool):
        return v
    s = (str(v) if v is not None else "").strip().lower()
    return s in {"1", "true", "t", "si", "sí", "on", "ok", "aprobado", "aprobada"}

def _doc(insc, name):
    return _bool(getattr(insc, name, False))

def _insc_prof_de_form(form):
    # devuelve EstudianteProfesorado desde distintos formularios
    insc = None
    if hasattr(form, "cleaned_data"):
        insc = form.cleaned_data.get("inscripcion")
        insc_curs = form.cleaned_data.get("inscripcion_cursada")
        if not insc and insc_curs is not None:
            insc = getattr(insc_curs, "inscripcion", None)
    return insc

def _espacio_de_form(form):
    esp = None
    if hasattr(form, "cleaned_data"):
        esp = form.cleaned_data.get("espacio")
        insc_curs = form.cleaned_data.get("inscripcion_cursada")
        if insc_curs is not None:
            esp = getattr(insc_curs, "espacio", None)
    return esp


# ===================== Formularios de Entidades Básicas =====================

class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = [
            "dni", "apellido", "nombre",
            "fecha_nacimiento", "lugar_nacimiento",
            "email", "telefono", "localidad",
            "contacto_emergencia_tel", "contacto_emergencia_parentesco",
            "activo", "foto",
        ]
        widgets = {
            "contacto_emergencia_tel": forms.TextInput(attrs={"placeholder": "Ej: 2964-123456"}),
            "contacto_emergencia_parentesco": forms.TextInput(attrs={"placeholder": "Ej: madre, padre, tutor…"}),
        }
        labels = {
            "contacto_emergencia_tel": "Tel. de emergencia",
            "contacto_emergencia_parentesco": "Parentesco",
        }


# ===================== Inscribir a Carrera (EstudianteProfesorado) =====================

class InscripcionProfesoradoForm(forms.ModelForm):
    class Meta:
        model = EstudianteProfesorado
        fields = "__all__"

    def _es_cd(self, prof) -> bool:
        if not prof:
            return False
        try:
            if not hasattr(prof, "nombre"):
                prof = Profesorado.objects.get(pk=prof)
            nombre = (getattr(prof, "nombre", "") or "").lower()
            return ("certificación docente" in nombre) or ("certificacion docente" in nombre)
        except Exception:
            return False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Campos extra: no requeridos por defecto
        for name in ("materias_adeudadas", "institucion_origen", "nota_compromiso"):
            if name in self.fields:
                self.fields[name].required = False
        if "materias_adeudadas" in self.fields:
            self.fields["materias_adeudadas"].widget.attrs.setdefault("rows", 2)

        # Nunca mostrar en UI estos campos administrativos crudos
        for name in ("promedio_general", "legajo", "libreta", "libreta_entregada"):
            self.fields.pop(name, None)

        # Los checks de títulos (sec/terciario/incumbencias) SIEMPRE quedan en el form.
        # El template/JS decide cuál mostrar según el profesorado (CD vs normal).

    def clean(self):
        cleaned = super().clean()

        # Documentación base
        dni_ok    = _bool(cleaned.get("doc_dni_legalizado"))
        cert_ok   = _bool(cleaned.get("doc_cert_medico"))
        fotos_ok  = _bool(cleaned.get("doc_fotos_carnet"))
        folios_ok = _bool(cleaned.get("doc_folios_oficio"))

        # Títulos / incumbencias
        sec_ok = _bool(cleaned.get("doc_titulo_sec_legalizado"))
        ter_ok = _bool(cleaned.get("doc_titulo_terciario_legalizado"))
        inc_ok = _bool(cleaned.get("doc_incumbencias"))

        prof  = cleaned.get("profesorado") or getattr(self.instance, "profesorado", None)
        es_cd = self._es_cd(prof)

        titulo_en_tramite = _bool(cleaned.get("titulo_en_tramite"))
        adeuda            = _bool(cleaned.get("adeuda_materias"))

        # Reglas de título según trayecto
        if es_cd:
            # Certificación Docente: exige terciario + incumbencias
            tiene_titulo = ter_ok and inc_ok
        else:
            # Profesorados normales: exige secundario
            tiene_titulo = sec_ok

        # ¿Legajo completo?
        docs_ok = dni_ok and cert_ok and fotos_ok and folios_ok and tiene_titulo and not titulo_en_tramite

        # Adeuda materias => exige detalles
        if adeuda:
            if not (cleaned.get("materias_adeudadas") or "").strip():
                self.add_error("materias_adeudadas", "Detalle las materias adeudadas.")
            if not (cleaned.get("institucion_origen") or "").strip():
                self.add_error("institucion_origen", "Indique la escuela / institución.")

        # Estados administrativos calculados
        try:
            legajo_estado = LegajoEstado.COMPLETO if docs_ok else LegajoEstado.INCOMPLETO
        except Exception:
            legajo_estado = cleaned.get("legajo_estado")

        try:
            cond_admin = CondicionAdmin.REGULAR if (docs_ok and not adeuda) else CondicionAdmin.CONDICIONAL
        except Exception:
            cond_admin = cleaned.get("condicion_admin") or "CONDICIONAL"

        cleaned["legajo_estado"] = legajo_estado
        cleaned["condicion_admin"] = cond_admin

        # Si queda Condicional, DDJJ/Nota compromiso obligatoria
        if (str(cond_admin) == getattr(CondicionAdmin, "CONDICIONAL", "CONDICIONAL")) and not _bool(cleaned.get("nota_compromiso")):
            self.add_error("nota_compromiso", "Obligatoria para condición administrativa Condicional.")

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Propagar valores calculados (por si esos campos no se renderizan)
        if "condicion_admin" in self.cleaned_data and hasattr(obj, "condicion_admin"):
            setattr(obj, "condicion_admin", self.cleaned_data["condicion_admin"])
        if "legajo_estado" in self.cleaned_data and hasattr(obj, "legajo_estado"):
            setattr(obj, "legajo_estado", self.cleaned_data["legajo_estado"])
        if commit:
            obj.save()
        return obj


# ===================== Inscripción a Materia (cursada) =====================

class InscripcionEspacioForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = ["inscripcion", "anio_academico", "espacio", "estado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Estado limitado a EN_CURSO / BAJA (consistencia)
        if "estado" in self.fields:
            self.fields["estado"].widget = forms.Select(choices=[
                ("EN_CURSO", "En curso"),
                ("BAJA", "Baja"),
            ])

    def clean(self):
        cleaned = super().clean()
        insc = cleaned.get("inscripcion")
        esp  = cleaned.get("espacio")
        if not insc or not esp:
            return cleaned

        # Validación de correlatividades (bloqueante)
        if should_enforce():
            ok, faltantes = evaluar_correlatividades(insc, esp)
            if not ok:
                msg = "No cumple correlatividades para cursar: " + "; ".join(f for f in faltantes if f)
                raise ValidationError(msg)
        return cleaned


# ===================== Cargar Cursada (REGULAR/PROMOCIÓN/...) =====================

class CargarCursadaForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num", "nota_texto"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}), "condicion": forms.Select()}

    def clean(self):
        cleaned = super().clean()
        condicion_obj = cleaned.get("condicion")
        condicion_str = str(getattr(condicion_obj, 'codigo', "") or "").upper()
        insc = cleaned.get("inscripcion")
        esp  = cleaned.get("espacio")

        # Condicional: puede cursar, pero no aprobar la cursada
        if insc and getattr(insc, "condicion_admin", "") == CondicionAdmin.CONDICIONAL:
            if condicion_str in {"REGULAR", "PROMOCION", "APROBADO"}:
                raise ValidationError("Estudiante condicional: puede cursar, pero no aprobar la cursada (REGULAR/PROMOCIÓN).")

        # EDI requiere Curso Introductorio aprobado para poder APROBAR (no para cursar)
        if insc and esp and condicion_str in {"PROMOCION", "APROBADO"}:
            if getattr(esp, "es_edi", False) and not insc.curso_intro_aprobado():
                raise ValidationError("Curso Introductorio no aprobado: puede cursar EDI, pero no aprobarlo.")

        return cleaned


# ===================== Inscripción a Final =====================

class InscripcionFinalForm(forms.ModelForm):
    class Meta:
        model = InscripcionFinal
        fields = ["inscripcion", "espacio", "fecha", "estado", "nota_final", "folio", "libro"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()
        insc   = cleaned.get("inscripcion")
        esp    = cleaned.get("espacio")
        estado = str(cleaned.get("estado") or "").upper()
        nota_final = cleaned.get("nota_final")

        if not insc or not esp:
            return cleaned

        # Condicional: no puede inscribirse a finales
        if getattr(insc, "condicion_admin", "") == CondicionAdmin.CONDICIONAL:
            raise ValidationError("Estudiante condicional: no puede inscribirse a finales.")

        # Requiere regularidad vigente
        if not _tiene_regularidad_vigente(insc, esp):
            raise ValidationError("No posee regularidad vigente para este espacio.")

        # Intentos máximos (si aplica por configuración)
        max_intentos = getattr(settings, "MAX_INTENTOS_FINAL", None)
        if max_intentos:
            usados = InscripcionFinal.objects.filter(
                inscripcion=insc, espacio=esp,
                estado__in=["DESAPROBADO", "AUSENTE"]
            ).count()
            if usados >= int(max_intentos):
                raise ValidationError(f"Se alcanzó el máximo de intentos permitidos para este final ({max_intentos}).")

        # Consistencias de nota/estado
        if estado == "AUSENTE" and nota_final is not None:
            raise ValidationError("Si marcás AUSENTE, no debe cargarse nota.")
        if estado == "APROBADO" and (nota_final is None or nota_final < 6):
            raise ValidationError("Estado APROBADO requiere nota final ≥ 6.")
        if estado == "DESAPROBADO" and (nota_final is not None and nota_final >= 6):
            raise ValidationError("Estado DESAPROBADO requiere nota final < 6 o vacía.")

        # EDI: para APROBAR requiere Curso Introductorio aprobado
        if estado == "APROBADO":
            if getattr(esp, "es_edi", False) and not insc.curso_intro_aprobado():
                raise ValidationError("Curso Introductorio no aprobado: puede rendir, pero no aprobar el EDI.")

        return cleaned


# ===================== Formularios Livianos para Carga de Notas =====================

class CargarNotaFinalForm(forms.Form):
    condicion   = forms.ChoiceField(required=False, choices=[("", "—"), ("LIBRE", "Libre"), ("EQUIVALENCIA", "Equivalencia")], label="Condición")
    nota_final  = forms.IntegerField(required=False, min_value=0, max_value=10, label="Nota final")
    folio       = forms.CharField(required=False, label="Folio")
    libro       = forms.CharField(required=False, label="Libro")


class CargarResultadoFinalForm(forms.ModelForm):
    class Meta:
        model = InscripcionFinal
        fields = ["inscripcion_cursada", "fecha", "estado", "nota_final", "folio", "libro"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()

        insc_cursada = cleaned.get("inscripcion_cursada")
        if not insc_cursada:
            return cleaned

        insc   = getattr(insc_cursada, "inscripcion", None)
        esp    = getattr(insc_cursada, "espacio", None)
        estado = str(cleaned.get("estado") or "").upper()

        # Condicional: no puede rendir/registrar final
        if insc and getattr(insc, "condicion_admin", "") == CondicionAdmin.CONDICIONAL:
            raise ValidationError("Estudiante condicional: no puede rendir ni registrar resultados de final.")

        # EDI: para APROBAR requiere Curso Introductorio aprobado
        if insc and esp and estado == "APROBADO":
            if getattr(esp, "es_edi", False) and not insc.curso_intro_aprobado():
                raise ValidationError("Curso Introductorio no aprobado: puede cursar EDI, pero no aprobarlo.")

        return cleaned
