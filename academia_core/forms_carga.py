# academia_core/forms_carga.py
from datetime import date, timedelta
import re

from django import forms
from django.core.exceptions import ValidationError, FieldError
from django.db.models import Q

from .models import (
    EstudianteProfesorado,
    EspacioCurricular,
    Profesorado,
    InscripcionEspacio,
    Estudiante,
    Correlatividad,  # detectar si un espacio tiene reglas CURSAR/RENDIR
    InscripcionFinal,
    Movimiento,
    _tiene_regularidad_vigente,  # importada para el nuevo form
)

# Si hay helper de correlatividades:
try:
    from .models import _cumple_correlativas  # opcional
except Exception:
    _cumple_correlativas = None


# ===================== Choices / helpers =====================

REG_CONDICIONES = [
    ("Promoción", "Promoción"),
    ("Aprobado", "Aprobado"),
    ("Regular", "Regular"),
    ("Desaprobado", "Desaprobado"),
    ("Libre", "Libre"),
    ("Libre-I", "Libre-I"),
    ("Libre-AT", "Libre-AT"),
]

FIN_CONDICIONES = [
    ("Regular", "Regular"),
    ("Libre", "Libre"),
    ("Equivalencia", "Equivalencia"),
]


def _nota_choices():
    # permite vacío (None) cuando la nota no corresponde
    return [("", "—")] + [(i, str(i)) for i in range(0, 11)]


def _coerce_nota(v):
    return int(v) if v not in (None, "",) else None


def _profes_qs_for_user(user):
    perfil = getattr(user, "perfil", None)
    if perfil and perfil.rol in ("BEDEL", "TUTOR"):
        return perfil.profesorados_permitidos.all()
    return Profesorado.objects.all()


def _plan_vigente_id(profesorado):
    """
    Devuelve el ID del plan vigente si existe.
    Soporta que plan_vigente sea FK (objeto con .id), un id plano o None.
    """
    pv = getattr(profesorado, "plan_vigente", None)
    if pv is None:
        return None
    if hasattr(pv, "id"):
        return getattr(pv, "id")
    try:
        return int(pv)
    except Exception:
        return None


# ---------- compat helpers (legacy/new nombres) ----------
def _ie_get_estado(rec) -> str:
    """Devuelve estado en mayúsculas, soportando
    'estado_cursada' (nuevo) o 'estado' (legacy)."""
    val = getattr(rec, "estado_cursada", None)
    if not val:
        val = getattr(rec, "estado", "")  # legacy
    return (val or "").upper()


def _ie_get_fecha_regularidad(rec):
    """Devuelve fecha de regularidad, soportando
    'fecha_regularidad' (nuevo) o 'fecha' (legacy)."""
    val = getattr(rec, "fecha_regularidad", None)
    if val is None:
        val = getattr(rec, "fecha", None)  # legacy
    return val


# ===================== Inscripción a Profesorado =====================

class InscripcionProfesoradoForm(forms.ModelForm):
    """Crea EstudianteProfesorado (vínculo Estudiante ↔ Profesorado + datos de legajo)."""

    class Meta:
        model = EstudianteProfesorado
        fields = [
            "estudiante", "profesorado",
            "cohorte",
            "curso_introductorio",
            # Documentación
            "doc_dni_legalizado", "doc_titulo_sec_legalizado", "doc_cert_medico",
            "doc_fotos_carnet", "doc_folios_oficio", "nota_compromiso",
            # Libreta (solo check)
            "legajo_entregado",
            # Adeuda
            "adeuda_materias", "adeuda_detalle", "colegio",
            # Certificación Docente
            "doc_titulo_superior_legalizado", "doc_incumbencias_titulo",
        ]
        widgets = {
            "estudiante": forms.Select(attrs={"class": "inp"}),
            "profesorado": forms.Select(attrs={"class": "inp"}),
            "cohorte": forms.TextInput(attrs={"placeholder": "2025", "class": "inp"}),
            "curso_introductorio": forms.Select(attrs={"class": "inp"}),

            # ✅ Cambiados a checkbox
            "doc_fotos_carnet": forms.CheckboxInput(),
            "doc_folios_oficio": forms.CheckboxInput(),

            "doc_dni_legalizado": forms.CheckboxInput(),
            "doc_titulo_sec_legalizado": forms.CheckboxInput(),
            "doc_cert_medico": forms.CheckboxInput(),
            "nota_compromiso": forms.CheckboxInput(),

            "legajo_entregado": forms.CheckboxInput(),

            "adeuda_materias": forms.CheckboxInput(),
            "adeuda_detalle": forms.Textarea(attrs={"class": "inp", "rows": 2, "placeholder": "Listado (si corresponde)"}),
            "colegio": forms.TextInput(attrs={"class": "inp", "placeholder": "Colegio"}),

            "doc_titulo_superior_legalizado": forms.CheckboxInput(),
            "doc_incumbencias_titulo": forms.CheckboxInput(),
        }
        labels = {
            "cohorte": "Cohorte",
            "curso_introductorio": "Curso introductorio",

            "doc_dni_legalizado": "DNI legalizado",
            "doc_titulo_sec_legalizado": "Título Secundario legalizado",
            "doc_cert_medico": "Certificado médico",
            # ✅ Etiquetas sin (0–2)
            "doc_fotos_carnet": "Fotos carnet",
            "doc_folios_oficio": "Folios oficio",
            "nota_compromiso": "DDJJ / Nota compromiso",

            "legajo_entregado": "Libreta entregada",

            "adeuda_materias": "Adeuda materia (sí/no)",
            "adeuda_detalle": "¿Cuáles?",
            "colegio": "Colegio",

            "doc_titulo_superior_legalizado": "Título Superior legalizado",
            "doc_incumbencias_titulo": "Incumbencias del título",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtro de profesorados por usuario (como ya tenías)
        profes_qs = _profes_qs_for_user(user)
        self.fields["profesorado"].queryset = profes_qs.order_by("nombre")

    def clean(self):
        cleaned = super().clean()
        # Si NO adeuda, vaciamos los campos dependientes para evitar datos “fantasma”
        if not cleaned.get("adeuda_materias"):
            for k in ("adeuda_detalle", "colegio"):
                if k in self.fields:
                    cleaned[k] = None
        return cleaned


# ===================== Inscripción a Espacio (Cursada) =====================

class InscripcionEspacioForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = ["inscripcion", "espacio", "anio_academico"]
        widgets = {
            "anio_academico": forms.NumberInput(attrs={"class": "inp", "min": 2000, "max": 2100}),
            "inscripcion": forms.Select(attrs={"class": "inp"}),  # autosubmit removido
            "espacio": forms.Select(attrs={"class": "inp", "id": "espacio-select"}),
        }
        labels = {"anio_academico": "Año académico"}

    @staticmethod
    def _vigencia_regularidad_anios():
        from django.conf import settings
        try:
            return int(getattr(settings, "REGULARIDAD_VIGENCIA_ANIOS", 2))
        except Exception:
            return 2

    @staticmethod
    def _vence_fin_de_anio():
        from django.conf import settings
        return bool(getattr(settings, "REGULARIDAD_VENCE_FIN_DE_ANIO", True))

    @classmethod
    def _fecha_expiracion_regularidad(cls, fr: date) -> date:
        vig = cls._vigencia_regularidad_anios()
        if cls._vence_fin_de_anio():
            return date(fr.year + vig - 1, 12, 31)
        else:
            from calendar import monthrange
            y, m, d = fr.year + vig, fr.month, fr.day
            last = monthrange(y, m)[1]
            return date(y, m, min(d, last))

    @classmethod
    def _tiene_regularidad_vigente(cls, insc, espacio) -> bool:
        qs = (InscripcionEspacio.objects
              .filter(inscripcion=insc, espacio=espacio)
              .only("estado", "estado_cursada", "fecha", "fecha_regularidad"))
        hoy = date.today()
        for cur in qs:
            estado = _ie_get_estado(cur)
            if estado in {"REGULAR", "PROMOCIONADO"}:
                fr = _ie_get_fecha_regularidad(cur)
                if fr is None:
                    return True
                frlim = cls._fecha_expiracion_regularidad(fr)
                if hoy <= frlim:
                    return True
        return False

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Año por defecto
        if not self.initial.get("anio_academico") and not self.data.get("anio_academico"):
            self.initial["anio_academico"] = date.today().year

        profes = _profes_qs_for_user(user)
        insc_qs = (
            EstudianteProfesorado.objects
            .filter(profesorado__in=profes)
            .select_related("estudiante", "profesorado")
            .order_by("estudiante__apellido", "estudiante__nombre")
        )
        self.fields["inscripcion"].queryset = insc_qs

        anio_sel = self.data.get("anio_academico") or self.initial.get("anio_academico") or date.today().year
        try:
            anio_int = int(anio_sel)
        except Exception:
            anio_int = date.today().year

        # ✅ si viene como dato, como initial o como instance → lo tomamos
        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )
        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        # <- aseguro que quede seleccionado visiblemente
        self.initial["inscripcion"] = insc_id

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            base = base.filter(plan_id=plan_vigente_id)
        base = base.order_by("anio", "cuatrimestre", "nombre")

        # Correlatividades CURSAR
        allowed_ids = []
        for e in base:
            ok = True
            if _cumple_correlativas:
                tiene_reglas = Correlatividad.objects.filter(plan=e.plan, espacio=e, tipo="CURSAR").exists()
                if tiene_reglas:
                    try:
                        ok, _faltan = _cumple_correlativas(insc, e, "CURSAR")
                    except Exception:
                        ok = True
            if ok:
                allowed_ids.append(e.id)
        base = base.filter(id__in=allowed_ids)

        # excluir aprobados
        aprobados_ids = set(
            insc.movimientos.filter(
                Q(espacio__in=base) & (
                    Q(tipo="REG", condicion__in=["Promoción", "Aprobado"], nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Regular",              nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Equivalencia",           nota_texto__iexact="Equivalencia")
                )
            ).values_list("espacio_id", flat=True)
        )
        estados_ok = ["APROBADA", "PROMOCIONADO", "PROMOCIONADA"]
        try:
            ids_estado = InscripcionEspacio.objects.filter(
                inscripcion=insc, espacio__in=base,
                estado_cursada__in=estados_ok
            ).values_list("espacio_id", flat=True)
        except FieldError:
            ids_estado = InscripcionEspacio.objects.filter(
                inscripcion=insc, espacio__in=base,
                estado__in=estados_ok
            ).values_list("espacio_id", flat=True)
        aprobados_ids |= set(ids_estado)
        if aprobados_ids:
            base = base.exclude(id__in=aprobados_ids)

        # excluir ya inscriptos en ese año
        ya_cursadas = set(
            InscripcionEspacio.objects.filter(
                inscripcion=insc, anio_academico=anio_int
            ).values_list("espacio_id", flat=True)
        )
        if ya_cursadas:
            base = base.exclude(id__in=ya_cursadas)

        # excluir regulares vigentes
        reg_vigentes_ids = []
        for e in list(base):
            try:
                if self._tiene_regularidad_vigente(insc, e):
                    reg_vigentes_ids.append(e.id)
            except Exception:
                pass
        if reg_vigentes_ids:
            base = base.exclude(id__in=reg_vigentes_ids)

        self.fields["espacio"].queryset = base

    def clean(self):
        cleaned = super().clean()
        insc = cleaned.get("inscripcion")
        esp = cleaned.get("espacio")
        anio = cleaned.get("anio_academico")
        if not insc or not esp or not anio:
            return cleaned

        if insc.profesorado_id != esp.profesorado_id:
            raise ValidationError("La inscripción y el espacio pertenecen a profesorados distintos.")

        ya = InscripcionEspacio.objects.filter(inscripcion=insc, espacio=esp, anio_academico=anio)
        if self.instance and self.instance.pk:
            ya = ya.exclude(pk=self.instance.pk)
        if ya.exists():
            raise ValidationError("Ya existe una cursada de este espacio para ese año académico.")

        aprobada = insc.movimientos.filter(
            Q(espacio=esp) & (
                Q(tipo="REG", condicion__in=["Promoción", "Aprobado"], nota_num__gte=6) |
                Q(tipo="FIN", condicion="Regular",              nota_num__gte=6) |
                Q(tipo="FIN", condicion="Equivalencia",           nota_texto__iexact="Equivalencia")
            )
        ).exists()
        if not aprobada:
            try:
                aprobada = InscripcionEspacio.objects.filter(
                    inscripcion=insc, espacio=esp, estado_cursada__in=["APROBADA", "PROMOCIONADO", "PROMOCIONADA"]
                ).exists()
            except FieldError:
                aprobada = InscripcionEspacio.objects.filter(
                    inscripcion=insc, espacio=esp, estado__in=["APROBADA", "PROMOCIONADO", "PROMOCIONADA"]
                ).exists()
        if aprobada:
            raise ValidationError("El espacio ya está aprobado: no corresponde reinscribir.")

        try:
            if self._tiene_regularidad_vigente(insc, esp):
                raise ValidationError("El estudiante ya posee regularidad vigente en este espacio: no corresponde reinscribir.")
        except Exception:
            pass

        if _cumple_correlativas:
            tiene_reglas = Correlatividad.objects.filter(plan=esp.plan, espacio=esp, tipo="CURSAR").exists()
            if tiene_reglas:
                ok, faltan = _cumple_correlativas(insc, esp, "CURSAR")
                if not ok:
                    partes = []
                    for regla, req in faltan:
                        partes.append(
                            f"{regla.requisito.lower()} de '{req.nombre}'"
                            if getattr(regla, 'requiere_espacio_id', None)
                            else f"{regla.requisito.lower()} de TODOS los espacios hasta {regla.requiere_todos_hasta_anio}°"
                        )
                    raise ValidationError("No cumple correlatividades para CURSAR: faltan " + ", ".join(partes) + ".")
        return cleaned


# ===================== Alta rápida de Estudiantes =====================

class EstudianteForm(forms.ModelForm):
    """Alta rápida de estudiantes desde el panel."""
    fecha_nacimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "inp"})
    )

    class Meta:
        model = Estudiante
        fields = [
            "dni", "apellido", "nombre",
            "fecha_nacimiento", "lugar_nacimiento",
            "email", "telefono", "localidad",
            "activo", "foto",
        ]
        widgets = {
            "dni": forms.TextInput(attrs={"class": "inp", "placeholder": "DNI"}),
            "apellido": forms.TextInput(attrs={"class": "inp"}),
            "nombre": forms.TextInput(attrs={"class": "inp"}),
            "lugar_nacimiento": forms.TextInput(attrs={"class": "inp", "placeholder": "Ciudad / Provincia"}),
            "email": forms.EmailInput(attrs={"class": "inp"}),
            "telefono": forms.TextInput(attrs={"class": "inp"}),
            "localidad": forms.TextInput(attrs={"class": "inp"}),
            "activo": forms.CheckboxInput(),
            "foto": forms.ClearableFileInput(attrs={"class": "inp"}),
        }
        labels = {
            "dni": "DNI",
            "apellido": "Apellido",
            "nombre": "Nombre",
            "fecha_nacimiento": "Fecha de nacimiento",
            "lugar_nacimiento": "Lugar de nacimiento",
            "email": "Email",
            "telefono": "Teléfono",
            "localidad": "Localidad",
            "activo": "Activo",
            "foto": "Foto (opcional)",
        }
        help_texts = {"dni": "Ingresá sólo números (se validará que no esté repetido)."}

    # --- Normalizaciones / validaciones ---
    def clean_dni(self):
        raw = (self.cleaned_data.get("dni") or "").strip()
        dni = re.sub(r"\D+", "", raw)
        if not dni:
            raise ValidationError("Ingresá un DNI.")
        qs = Estudiante.objects.filter(dni=dni)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Ya existe un estudiante con ese DNI.")
        return dni

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_nombre(self):
        return (self.cleaned_data.get("nombre") or "").strip()

    def clean_apellido(self):
        return (self.cleaned_data.get("apellido") or "").strip()


# ---------- Reglas compartidas para RENDIR (finales) ----------

def _regularidad_vigente_para_rendir(insc, espacio) -> bool:
    """
    Requiere alguna InscripcionEspacio con estado {REGULAR,PROMOCIONADO}
    y fecha de regularidad vigente. Soporta nombres legacy.
    """
    from calendar import monthrange
    from django.conf import settings

    vig = int(getattr(settings, "REGULARIDAD_VIGENCIA_ANIOS", 2))
    vence_fin_de_anio = bool(getattr(settings, "REGULARIDAD_VENCE_FIN_DE_ANIO", True))

    def _expira(fr: date) -> date:
        if vence_fin_de_anio:
            return date(fr.year + vig - 1, 12, 31)
        y, m, d = fr.year + vig, fr.month, fr.day
        last = monthrange(y, m)[1]
        return date(y, m, min(d, last))

    qs = InscripcionEspacio.objects.filter(
        inscripcion=insc, espacio=espacio
    ).only("estado", "estado_cursada", "fecha", "fecha_regularidad")

    hoy = date.today()
    for cur in qs:
        estado = _ie_get_estado(cur)
        if estado in {"REGULAR", "PROMOCIONADO"}:
            fr = _ie_get_fecha_regularidad(cur)
            if fr is None:
                return True
            if hoy <= _expira(fr):
                return True
    return False


def _max_intentos_final() -> int:
    """Cantidad de intentos de final fallidos permitidos (default: 3)."""
    from django.conf import settings
    try:
        return int(getattr(settings, "MAX_INTENTOS_FINAL", 3))
    except Exception:
        return 3


def _intentos_finales_fallidos(insc, espacio) -> int:
    """
    Cuenta intentos fallidos previos de final:
    - condicion == 'Libre' (no aprobado)
    - o Ausente sin justificación
    """
    return Movimiento.objects.filter(
        inscripcion=insc, espacio=espacio, tipo="FIN"
    ).filter(
        Q(condicion="Libre") | Q(ausente=True, ausencia_justificada=False)
    ).count()


# ===================== NUEVOS FORMULARIOS ESPECIALIZADOS =====================

NOTA_0_10 = [(i, str(i)) for i in range(11)]  # 0..10

# --- Registrar resultado de mesa de final (InscripcionFinal) ---
class CargarResultadoFinalForm(forms.ModelForm):
    nota_final = forms.TypedChoiceField(
        choices=NOTA_0_10, coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = InscripcionFinal
        fields = ["inscripcion_cursada", "nota_final", "ausente", "ausencia_justificada"]
        widgets = {
            "inscripcion_cursada": forms.Select(attrs={"class": "inp"}),
        }
        labels = {
            "inscripcion_cursada": "Inscripción Final (mesa)",
            "ausente": "Marcar Ausente",
            "ausencia_justificada": "Ausencia justificada",
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("ausente"):
            cleaned["nota_final"] = None
            return cleaned
        nota = cleaned.get("nota_final")
        if nota is None:
            raise ValidationError("Debe seleccionar una nota o marcar Ausente.")
        if not (0 <= nota <= 10):
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        if obj.ausente:
            obj.estado = "AUSENTE"
        elif (obj.nota_final or 0) >= 6:
            obj.estado = "APROBADO"
        else:
            obj.estado = "DESAPROBADO"
        if commit:
            obj.save()
        return obj


# --- Ejemplo para formularios que cargan Movimiento (REG o FIN) ---
class CargarRegularidadForm(forms.ModelForm):
    # Nota entera 0..10
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],
        coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"}),
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num"]
        widgets = {
            # ✅ autosubmit para recalcular "espacio"
            "inscripcion": forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # tomada de data (autosubmit), de initial o de una instancia ya cargada
        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        # que quede seleccionada visible
        self.initial["inscripcion"] = insc_id

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        # 1) si hay cursadas para esa inscripción, muestro esas
        cursadas_ids = list(
            InscripcionEspacio.objects
            .filter(inscripcion=insc)
            .values_list("espacio_id", flat=True)
        )
        if cursadas_ids:
            base = (EspacioCurricular.objects
                    .filter(id__in=cursadas_ids)
                    .order_by("anio", "cuatrimestre", "nombre"))
        else:
            # 2) fallback: todos los espacios del profesorado (plan vigente si existe)
            base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
            plan_vigente_id = _plan_vigente_id(insc.profesorado)
            if plan_vigente_id:
                base = base.filter(plan_id=plan_vigente_id)
            base = base.order_by("anio", "cuatrimestre", "nombre")

        self.fields["espacio"].queryset = base

    def clean(self):
        cleaned = super().clean()
        cond = cleaned.get("condicion")
        nota = cleaned.get("nota_num")

        # para Regular/Promoción/Aprobado la nota es obligatoria y 0..10
        if cond in {"Promoción", "Aprobado", "Regular"}:
            if nota is None:
                raise ValidationError("Debe seleccionar una nota (0–10).")
            if not (0 <= nota <= 10):
                raise ValidationError("La nota debe estar entre 0 y 10.")
        else:
            cleaned["nota_num"] = None
        return cleaned

    # si tu modelo usa 'nota_num' para REG, lo forzamos a entero con select:
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],  # 0..10
        coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num"]
        widgets = {
            # ✅ autosubmit SOLO para filtrar
            "inscripcion": forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        # mantener visible la inscripción seleccionada
        self.initial["inscripcion"] = insc_id

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        # Si ya hay cursadas para esa inscripción, mostramos esas
        cursadas_ids = list(
            InscripcionEspacio.objects
            .filter(inscripcion=insc)
            .values_list("espacio_id", flat=True)
        )

        if cursadas_ids:
            base = (EspacioCurricular.objects
                    .filter(id__in=cursadas_ids)
                    .order_by("anio", "cuatrimestre", "nombre"))
        else:
            # Fallback: todos los espacios del profesorado (plan vigente si hay)
            base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
            plan_vigente_id = _plan_vigente_id(insc.profesorado)
            if plan_vigente_id:
                base = base.filter(plan_id=plan_vigente_id)
            base = base.order_by("anio", "cuatrimestre", "nombre")

        self.fields["espacio"].queryset = base

    def clean(self):
        cleaned = super().clean()
        cond = cleaned.get("condicion")
        nota = cleaned.get("nota_num")
        if cond in {"Promoción", "Aprobado", "Regular"}:
            if nota is None:
                raise ValidationError("Debe seleccionar una nota (0–10).")
            if not (0 <= nota <= 10):
                raise ValidationError("La nota debe estar entre 0 y 10.")
        else:
            cleaned["nota_num"] = None
        return cleaned

    # si tu modelo usa 'nota_num' para REG, lo forzamos a entero con select:
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],  # 0..10
        coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num"]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filtrar ESPACIO según la inscripción elegida
        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            # hasta que elijan inscripción, no mostrar nada
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        # Si ya hay cursadas creadas para esa inscripción, priorizamos esas
        cursadas_ids = list(
            InscripcionEspacio.objects
            .filter(inscripcion=insc)
            .values_list("espacio_id", flat=True)
        )

        if cursadas_ids:
            base = (EspacioCurricular.objects
                    .filter(id__in=cursadas_ids)
                    .order_by("anio", "cuatrimestre", "nombre"))
        else:
            # Fallback: todos los espacios del profesorado (y plan vigente si hay)
            base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
            plan_vigente_id = _plan_vigente_id(insc.profesorado)
            if plan_vigente_id:
                base = base.filter(plan_id=plan_vigente_id)
            base = base.order_by("anio", "cuatrimestre", "nombre")

        self.fields["espacio"].queryset = base

    def clean(self):
        cleaned = super().clean()
        # Validación simple de nota para condiciones que la requieren
        cond = cleaned.get("condicion")
        nota = cleaned.get("nota_num")
        if cond in {"Promoción", "Aprobado", "Regular"}:
            if nota is None:
                raise ValidationError("Debe seleccionar una nota (0–10).")
            if not (0 <= nota <= 10):
                raise ValidationError("La nota debe estar entre 0 y 10.")
        else:
            cleaned["nota_num"] = None
        return cleaned

    # si tu modelo usa 'nota_num' para REG, lo forzamos a entero con select:
    nota_num = forms.TypedChoiceField(
        choices=NOTA_0_10, coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion", "nota_num"]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
        }

    def clean(self):
        cleaned = super().clean()
        # si corresponde nota, que esté 0..10 (entera)
        cond = cleaned.get("condicion")
        nota = cleaned.get("nota_num")
        if cond in {"Promoción", "Aprobado", "Regular"}:
            if nota is None:
                raise ValidationError("Debe seleccionar una nota (0–10).")
            if not (0 <= nota <= 10):
                raise ValidationError("La nota debe estar entre 0 y 10.")
        else:
            cleaned["nota_num"] = None
        return cleaned


class CargarFinalForm(forms.ModelForm):
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],
        coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"}),
    )

    class Meta:
        model = Movimiento
        fields = [
            "inscripcion", "espacio", "fecha", "condicion",
            "nota_num", "ausente", "ausencia_justificada",
            "nota_texto", "disposicion_interna",
        ]
        widgets = {
            # ✅ autosubmit para recalcular "espacio"
            "inscripcion": forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
            "nota_texto": forms.TextInput(attrs={"class": "inp"}),
            "disposicion_interna": forms.TextInput(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )
        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        self.initial["inscripcion"] = insc_id

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        # para finales: espacios del profesorado (plan vigente si existe)
        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            base = base.filter(plan_id=plan_vigente_id)
        self.fields["espacio"].queryset = base.order_by("anio", "cuatrimestre", "nombre")

    def clean(self):
        cleaned = super().clean()
        cond = cleaned.get("condicion")
        aus = cleaned.get("ausente")
        nota = cleaned.get("nota_num")

        if cond == "Equivalencia":
            cleaned["nota_num"] = None
            return cleaned

        if aus:
            cleaned["nota_num"] = None
            return cleaned

        if nota is None:
            raise ValidationError("Debe seleccionar una nota o marcar Ausente.")
        if not (0 <= nota <= 10):
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned

    # para FIN Regular/Libre (no equivalencia), entero 0..10
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],  # 0..10
        coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion",
                  "nota_num", "ausente", "ausencia_justificada",
                  "nota_texto", "disposicion_interna"]
        widgets = {
            # ✅ autosubmit para filtrar el combo de espacio
            "inscripcion": forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
            "nota_texto": forms.TextInput(attrs={"class": "inp"}),
            "disposicion_interna": forms.TextInput(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        # mantener visible la inscripción seleccionada
        self.initial["inscripcion"] = insc_id

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        # Para finales mostramos los espacios del profesorado (plan vigente si hay)
        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            base = base.filter(plan_id=plan_vigente_id)
        base = base.order_by("anio", "cuatrimestre", "nombre")
        self.fields["espacio"].queryset = base

    def clean(self):
        cleaned = super().clean()
        cond   = cleaned.get("condicion")
        aus    = cleaned.get("ausente")
        nota   = cleaned.get("nota_num")

        if cond == "Equivalencia":
            cleaned["nota_num"] = None
            return cleaned

        if aus:
            cleaned["nota_num"] = None
            return cleaned

        if nota is None:
            raise ValidationError("Debe seleccionar una nota o marcar Ausente.")
        if not (0 <= nota <= 10):
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned

    # para FIN Regular/Libre (no equivalencia), entero 0..10
    nota_num = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(11)],  # 0..10
        coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion",
                  "nota_num", "ausente", "ausencia_justificada",
                  "nota_texto", "disposicion_interna"]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
            "nota_texto": forms.TextInput(attrs={"class": "inp"}),
            "disposicion_interna": forms.TextInput(attrs={"class": "inp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        insc_id = (
            self.data.get("inscripcion")
            or getattr(self.initial.get("inscripcion"), "pk", None)
            or getattr(self.instance, "inscripcion_id", None)
        )

        if not insc_id:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."
            return

        try:
            insc = (
                EstudianteProfesorado.objects
                .select_related("profesorado")
                .get(pk=insc_id)
            )
        except EstudianteProfesorado.DoesNotExist:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            return

        # Para finales, mostramos los espacios del profesorado (y plan vigente)
        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            base = base.filter(plan_id=plan_vigente_id)
        base = base.order_by("anio", "cuatrimestre", "nombre")
        self.fields["espacio"].queryset = base

    def clean(self):
        cleaned = super().clean()
        cond   = cleaned.get("condicion")
        aus    = cleaned.get("ausente")
        nota   = cleaned.get("nota_num")

        if cond == "Equivalencia":
            cleaned["nota_num"] = None
            return cleaned

        if aus:
            cleaned["nota_num"] = None
            return cleaned

        if nota is None:
            raise ValidationError("Debe seleccionar una nota o marcar Ausente.")
        if not (0 <= nota <= 10):
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned

    # para FIN Regular/Libre (no equivalencia), entero 0..10
    nota_num = forms.TypedChoiceField(
        choices=NOTA_0_10, coerce=int, required=False,
        label="Nota (0–10)",
        widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ["inscripcion", "espacio", "fecha", "condicion",
                  "nota_num", "ausente", "ausencia_justificada",
                  "nota_texto", "disposicion_interna"]
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "inp"}),
            "condicion": forms.Select(attrs={"class": "inp"}),
            "nota_texto": forms.TextInput(attrs={"class": "inp"}),
            "disposicion_interna": forms.TextInput(attrs={"class": "inp"}),
        }

    def clean(self):
        cleaned = super().clean()
        cond   = cleaned.get("condicion")
        aus    = cleaned.get("ausente")
        nota   = cleaned.get("nota_num")

        if cond == "Equivalencia":
            cleaned["nota_num"] = None  # no hay nota numérica
            # (dejá tus validaciones de 'nota_texto' y 'disposicion_interna')
            return cleaned

        if aus:
            cleaned["nota_num"] = None
            return cleaned

        if nota is None:
            raise ValidationError("Debe seleccionar una nota o marcar Ausente.")
        if not (0 <= nota <= 10):
            raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned


# ===================== Inscripción a Mesa de Examen Final =====================

class InscripcionFinalForm(forms.ModelForm):
    # Filtro previo
    estudiante = forms.ModelChoiceField(
        label="Estudiante",
        queryset=Estudiante.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),  # autosubmit
    )

    class Meta:
        model = InscripcionFinal
        fields = ["estudiante", "inscripcion_cursada", "fecha_examen"]
        widgets = {
            "inscripcion_cursada": forms.Select(attrs={"class": "inp"}),
            "fecha_examen": forms.DateInput(attrs={"type": "date", "class": "inp"}),
        }
        labels = {
            "inscripcion_cursada": "Estudiante y Materia a Rendir:",
            "fecha_examen": "Fecha de la Mesa:",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)  # <- importante
        super().__init__(*args, **kwargs)

        # --- 1) Poblá el combo de estudiantes según el rol/alcance del usuario ---
        try:
            profes = _profes_qs_for_user(user)  # si tenés este helper
            est_qs = (Estudiante.objects
                      .filter(inscripciones__profesorado__in=profes)
                      .distinct()
                      .order_by("apellido", "nombre"))
        except Exception:
            # fallback: todos (si no tenés helper)
            est_qs = Estudiante.objects.order_by("apellido", "nombre")

        self.fields["estudiante"].queryset = est_qs

        # estudiante seleccionado (GET o initial)
        est_id = self.data.get("estudiante")
        est = None
        if est_id:
            try:
                est = Estudiante.objects.get(pk=est_id)
            except Estudiante.DoesNotExist:
                est = None

        # --- 2) Filtrá las cursadas (inscripcion_cursada) del estudiante seleccionado
        base = InscripcionEspacio.objects.none()
        if est:
            base = (InscripcionEspacio.objects
                    .filter(inscripcion__estudiante=est)
                    .select_related("inscripcion__estudiante", "inscripcion__profesorado", "espacio"))

            # dejar solo las que tienen regularidad vigente
            hoy = date.today()
            elegibles = []
            for c in base:
                try:
                    if _tiene_regularidad_vigente(c.inscripcion, c.espacio, hoy):
                        elegibles.append(c.pk)
                except Exception:
                    pass
            base = base.filter(pk__in=elegibles)

        self.fields["inscripcion_cursada"].queryset = base.order_by(
            "espacio__anio", "espacio__cuatrimestre", "espacio__nombre"
        )
        self.fields["inscripcion_cursada"].label_from_instance = (
            lambda obj: f"{obj.inscripcion.estudiante.apellido}, "
                        f"{obj.inscripcion.estudiante.nombre} — {obj.espacio.nombre}"
        )

    def clean(self):
        cleaned = super().clean()
        est = cleaned.get("estudiante")
        ic = cleaned.get("inscripcion_cursada")
        if est and ic and ic.inscripcion.estudiante_id != est.id:
            raise ValidationError("La cursada seleccionada no corresponde al estudiante elegido.")
        return cleaned


# ===================== Cargar Nota de Mesa Final =====================

class CargarNotaFinalForm(forms.ModelForm):

    class Meta:
        model = InscripcionFinal
        fields = ['inscripcion_cursada', 'fecha_examen', 'nota_final', 'ausente', 'ausencia_justificada']
        widgets  = {
            'inscripcion_cursada': forms.Select(attrs={'class': 'inp'}),
            'fecha_examen': forms.DateInput(attrs={'type': 'date', 'class': 'inp'}),
            'nota_final': forms.NumberInput(attrs={'class': 'inp', 'min':0, 'max':10}),
            'ausente': forms.CheckboxInput(),
            'ausencia_justificada': forms.CheckboxInput(),
        }
        labels = {
            'inscripcion_cursada': 'Mesa (inscripción del estudiante)',
            'fecha_examen': 'Fecha',
            'nota_final': 'Nota numérica',
            'ausente': 'Ausente',
            'ausencia_justificada': 'Ausencia justificada',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # solo mostrar mesas INSCRIPTAS que todavía no tengan cargado resultado
        qs = InscripcionFinal.objects.filter(estado='INSCRIPTO')
        self.fields['inscripcion_cursada'].queryset = qs.order_by('inscripcion_cursada__inscripcion__estudiante__apellido')

        self.fields['inscripcion_cursada'].label_from_instance = (
            lambda obj: f"{obj.inscripcion_cursada.inscripcion.estudiante.apellido}, {obj.inscripcion_cursada.inscripcion.estudiante.nombre} - {obj.inscripcion_cursada.espacio}"
        )

    def clean(self):
        cleaned = super().clean()
        nota    = cleaned.get('nota_final')
        ausente = cleaned.get('ausente')
        justif  = cleaned.get('ausencia_justificada')

        if ausente and nota is not None:
            raise ValidationError("Si está AUSENTE no se puede cargar una nota.")
        if justif and not ausente:
            raise ValidationError("Solo se puede marcar 'justificada' si está marcado AUSENTE.")
        if not ausente and nota is None:
            raise ValidationError("Debe cargar una nota o marcarlo como Ausente.")
        if not ausente and nota is not None and (nota < 0 or nota > 10):
                 raise ValidationError("La nota debe estar entre 0 y 10.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Seteamos estado final según lo que cargue el operador
        if obj.ausente:
            obj.estado = 'AUSENTE'
        elif obj.nota_final is not None and obj.nota_final >= 6:
            obj.estado = 'APROBADO'
        else:
            obj.estado = 'DESAPROBADO'
        if commit:
            obj.save()
        return obj
