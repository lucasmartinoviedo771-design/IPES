# academia_core/forms_carga.py
from datetime import date
import re

from django import forms
from django.core.exceptions import ValidationError, FieldError
from django.db.models import Q

from .models import (
    Movimiento,
    EstudianteProfesorado,
    EspacioCurricular,
    Profesorado,
    InscripcionEspacio,
    Estudiante,
    Correlatividad,  # detectar si un espacio tiene reglas CURSAR/RENDIR
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
            "cohorte", "libreta",
            "curso_introductorio",

            # Documentación entregada
            "doc_dni_legalizado",
            "doc_titulo_sec_legalizado",
            "doc_cert_medico",
            "doc_fotos_carnet",
            "doc_folios_oficio",
            "nota_compromiso",

            # Libreta entregada
            "legajo_entregado",

            # Adeuda materia
            "adeuda_materias",
            "adeuda_detalle",
            "colegio",

            # Sólo Certificación Docente
            "doc_titulo_superior_legalizado",
            "doc_incumbencias_titulo",
        ]
        widgets = {
            "estudiante": forms.Select(attrs={"class": "inp"}),
            "profesorado": forms.Select(attrs={"class": "inp"}),
            "cohorte": forms.TextInput(attrs={"placeholder": "2025", "class": "inp"}),
            "libreta": forms.TextInput(attrs={"class": "inp", "placeholder": "Nº físico (si aplica)"}),
            "curso_introductorio": forms.Select(attrs={"class": "inp"}),

            "doc_fotos_carnet": forms.NumberInput(attrs={"class": "inp", "min": 0, "max": 2}),
            "doc_folios_oficio": forms.NumberInput(attrs={"class": "inp", "min": 0, "max": 2}),
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
            "libreta": "Libreta",
            "curso_introductorio": "Curso introductorio",

            "doc_dni_legalizado": "DNI legalizado",
            "doc_titulo_sec_legalizado": "Título Secundario legalizado",
            "doc_cert_medico": "Certificado médico",
            "doc_fotos_carnet": "Fotos carnet (0–2)",
            "doc_folios_oficio": "Folios oficio (0–2)",
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
        profes_qs = _profes_qs_for_user(user)
        self.fields["profesorado"].queryset = profes_qs.order_by("nombre")


# ===================== Inscripción a Espacio (Cursada) =====================

class InscripcionEspacioForm(forms.ModelForm):
    class Meta:
        model = InscripcionEspacio
        fields = ["inscripcion", "espacio", "anio_academico"]
        widgets = {
            "anio_academico": forms.NumberInput(attrs={"class": "inp", "min": 2000, "max": 2100}),
            "inscripcion": forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),  # autosubmit
            "espacio": forms.Select(attrs={"class": "inp"}),
        }
        labels = {"anio_academico": "Año académico"}

    # ---------- Política (configurable por settings) ----------
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
            # mismo día/mes si existe; si no, último día del mes
            from calendar import monthrange
            y, m, d = fr.year + vig, fr.month, fr.day
            last = monthrange(y, m)[1]
            return date(y, m, min(d, last))

    @classmethod
    def _tiene_regularidad_vigente(cls, insc, espacio) -> bool:
        """
        Usa InscripcionEspacio.(estado|estado_cursada) y (fecha|fecha_regularidad).
        Considera REGULAR / PROMOCIONADO como con-regularidad.
        """
        qs = (InscripcionEspacio.objects
              .filter(inscripcion=insc, espacio=espacio)
              .only("estado", "estado_cursada", "fecha", "fecha_regularidad"))
        hoy = date.today()
        for cur in qs:
            estado = _ie_get_estado(cur)
            if estado in {"REGULAR", "PROMOCIONADO"}:
                fr = _ie_get_fecha_regularidad(cur)
                if fr is None:
                    return True  # defensivo
                # vigencia
                frlim = cls._fecha_expiracion_regularidad(fr)
                if hoy <= frlim:
                    return True
        return False

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # 1) Año por defecto
        if not self.initial.get("anio_academico") and not self.data.get("anio_academico"):
            self.initial["anio_academico"] = date.today().year

        # 2) Inscripciones visibles según profesorados permitidos al usuario
        profes = _profes_qs_for_user(user)
        insc_qs = (
            EstudianteProfesorado.objects
            .filter(profesorado__in=profes)
            .select_related("estudiante", "profesorado")
            .order_by("estudiante__apellido", "estudiante__nombre")
        )
        self.fields["inscripcion"].queryset = insc_qs

        # Año seleccionado
        anio_sel = self.data.get("anio_academico") or self.initial.get("anio_academico") or date.today().year
        try:
            anio_int = int(anio_sel)
        except Exception:
            anio_int = date.today().year

        # 3) Si ya hay espacio elegido, limitar inscripciones al profesorado de ese espacio
        esp_id = self.data.get("espacio") or getattr(self.initial.get("espacio"), "pk", None)
        if esp_id:
            try:
                esp = EspacioCurricular.objects.select_related("profesorado").get(pk=esp_id)
                self.fields["inscripcion"].queryset = insc_qs.filter(profesorado=esp.profesorado)
            except EspacioCurricular.DoesNotExist:
                pass

        # 4) Espacios del profesorado de la inscripción + filtros
        insc_id = self.data.get("inscripcion") or getattr(self.initial.get("inscripcion"), "pk", None)
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

        base = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            base = base.filter(plan_id=plan_vigente_id)
        base = base.order_by("anio", "cuatrimestre", "nombre")

        # 4.a) Correlatividades CURSAR (solo exigimos si el espacio tiene reglas; si no, se permite)
        allowed_ids = []
        for e in base:
            ok = True
            if _cumple_correlativas:
                tiene_reglas = Correlatividad.objects.filter(plan=e.plan, espacio=e, tipo="CURSAR").exists()
                if tiene_reglas:
                    try:
                        ok, _faltan = _cumple_correlativas(insc, e, "CURSAR")
                    except Exception:
                        ok = True  # no bloquear por error de configuración
            if ok:
                allowed_ids.append(e.id)
        base = base.filter(id__in=allowed_ids)

        # 4.b) Excluir espacios ya aprobados (dos fuentes: movimientos históricos y estado actual)
        aprobados_ids = set(
            insc.movimientos.filter(
                Q(espacio__in=base) & (
                    Q(tipo="REG", condicion__in=["Promoción", "Aprobado"], nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Regular",                   nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Equivalencia",              nota_texto__iexact="Equivalencia")
                )
            ).values_list("espacio_id", flat=True)
        )
        # Estados del ciclo de cursada (compat)
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

        # 4.c) Excluir ya inscriptos en el mismo año académico
        ya_cursadas = set(
            InscripcionEspacio.objects.filter(
                inscripcion=insc, anio_academico=anio_int
            ).values_list("espacio_id", flat=True)
        )
        if ya_cursadas:
            base = base.exclude(id__in=ya_cursadas)

        # 4.d) Excluir espacios con regularidad vigente
        reg_vigentes_ids = []
        for e in list(base):
            try:
                if self._tiene_regularidad_vigente(insc, e):
                    reg_vigentes_ids.append(e.id)
            except Exception:
                pass  # defensivo
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

        # Misma carrera
        if insc.profesorado_id != esp.profesorado_id:
            raise ValidationError("La inscripción y el espacio pertenecen a profesorados distintos.")

        # No duplicar (mismo año)
        ya = InscripcionEspacio.objects.filter(inscripcion=insc, espacio=esp, anio_academico=anio)
        if self.instance and self.instance.pk:
            ya = ya.exclude(pk=self.instance.pk)
        if ya.exists():
            raise ValidationError("Ya existe una cursada de este espacio para ese año académico.")

        # No reinscribir si ya está aprobado (histórico o estado actual)
        aprobada = insc.movimientos.filter(
            Q(espacio=esp) & (
                Q(tipo="REG", condicion__in=["Promoción", "Aprobado"], nota_num__gte=6) |
                Q(tipo="FIN", condicion="Regular",                   nota_num__gte=6) |
                Q(tipo="FIN", condicion="Equivalencia",              nota_texto__iexact="Equivalencia")
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

        # Defensa final: regularidad vigente
        try:
            if self._tiene_regularidad_vigente(insc, esp):
                raise ValidationError("El estudiante ya posee regularidad vigente en este espacio: no corresponde reinscribir.")
        except Exception:
            pass

        # Defensa por correlatividades (si hay helper y el espacio tiene reglas)
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

class CargarRegularidadForm(forms.ModelForm):
    """
    REG: muestra SOLO espacios inscriptos este año y no aprobados,
    dentro del mismo profesorado y plan vigente.
    """
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "inp"}))
    condicion = forms.ChoiceField(choices=REG_CONDICIONES, widget=forms.Select(attrs={"class":"inp"}))
    nota_num = forms.TypedChoiceField(
        choices=_nota_choices(), coerce=_coerce_nota, empty_value=None, required=False,
        label="Nota num.", widget=forms.Select(attrs={"class": "inp"})
    )

    class Meta:
        model = Movimiento
        fields = ("inscripcion", "espacio", "fecha", "condicion", "nota_num")
        widgets = {
            "inscripcion": forms.Select(attrs={"class":"inp","onchange":"this.form.submit()"}),
            "espacio": forms.Select(attrs={"class":"inp"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        profes_permitidos = _profes_qs_for_user(user)
        self.fields["inscripcion"].queryset = (
            EstudianteProfesorado.objects
            .filter(profesorado__in=profes_permitidos)
            .select_related("estudiante","profesorado")
            .order_by("estudiante__apellido","estudiante__nombre")
        )
        self.fields["espacio"].queryset = EspacioCurricular.objects.none()

        insc_id = self.data.get("inscripcion") or getattr(self.initial.get("inscripcion"), "pk", None)
        if not insc_id:
            return

        try:
            insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
        except EstudianteProfesorado.DoesNotExist:
            return

        q = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            q = q.filter(plan_id=plan_vigente_id)

        # excluir aprobadas/promocionadas (histórico + ciclo)
        def _aprobado(e):
            mov_ok = insc.movimientos.filter(
                Q(espacio=e) & (
                    Q(tipo="REG", condicion__in=["Promoción","Aprobado"], nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Regular", nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Equivalencia", nota_texto__iexact="Equivalencia")
                )
            ).exists()
            try:
                ciclo_ok = InscripcionEspacio.objects.filter(
                    inscripcion=insc, espacio=e,
                    estado_cursada__in=["APROBADA","PROMOCIONADO","PROMOCIONADA"]
                ).exists()
            except Exception:
                ciclo_ok = InscripcionEspacio.objects.filter(
                    inscripcion=insc, espacio=e,
                    estado__in=["APROBADA","PROMOCIONADO","PROMOCIONADA"]
                ).exists()
            return mov_ok or ciclo_ok

        base_ids = [e.id for e in q if not _aprobado(e)]

        # sólo materias inscriptas este año
        anio = date.today().year
        insc_ids = set(
            InscripcionEspacio.objects.filter(
                inscripcion=insc, anio_academico=anio
            ).values_list("espacio_id", flat=True)
        )
        permitidos = set(base_ids) & insc_ids
        self.fields["espacio"].queryset = EspacioCurricular.objects.filter(id__in=permitidos).order_by("anio","cuatrimestre","nombre")

    def clean(self):
        c = super().clean()
        if c.get("condicion") in ("Promoción","Aprobado"):
            if c.get("nota_num") is None or int(c["nota_num"]) < 6:
                raise ValidationError("Para Promoción/Aprobado la nota debe ser 6..10.")
        if c.get("condicion") == "Desaprobado" and c.get("nota_num") is not None and int(c["nota_num"]) > 5:
            raise ValidationError("Para Desaprobado la nota debe ser 0..5.")
        return c

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.tipo = "REG"
        if commit: obj.save()
        return obj


class CargarFinalForm(forms.ModelForm):
    """
    FIN: muestra SOLO espacios con regularidad vigente + correlativas RENDIR (si hay),
    y no aprobados (histórico/ciclo).
    """
    fecha = forms.DateField(widget=forms.DateInput(attrs={"type":"date","class":"inp"}))
    condicion = forms.ChoiceField(choices=FIN_CONDICIONES, widget=forms.Select(attrs={"class":"inp"}))
    nota_num = forms.TypedChoiceField(
        choices=_nota_choices(), coerce=_coerce_nota, empty_value=None, required=False,
        label="Nota num.", widget=forms.Select(attrs={"class":"inp"})
    )
    ausente = forms.BooleanField(required=False)
    ausencia_justificada = forms.BooleanField(required=False)
    folio = forms.CharField(required=False)
    libro = forms.CharField(required=False)
    disposicion_interna = forms.CharField(required=False)

    class Meta:
        model = Movimiento
        fields = ("inscripcion","espacio","fecha","condicion","nota_num","ausente","ausencia_justificada","folio","libro","disposicion_interna")
        widgets = {
            "inscripcion": forms.Select(attrs={"class":"inp","onchange":"this.form.submit()"}),
            "espacio": forms.Select(attrs={"class":"inp"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        profes_permitidos = _profes_qs_for_user(user)
        self.fields["inscripcion"].queryset = (
            EstudianteProfesorado.objects
            .filter(profesorado__in=profes_permitidos)
            .select_related("estudiante","profesorado")
            .order_by("estudiante__apellido","estudiante__nombre")
        )
        self.fields["espacio"].queryset = EspacioCurricular.objects.none()

        insc_id = self.data.get("inscripcion") or getattr(self.initial.get("inscripcion"), "pk", None)
        if not insc_id:
            return

        try:
            insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
        except EstudianteProfesorado.DoesNotExist:
            return

        q = EspacioCurricular.objects.filter(profesorado=insc.profesorado)
        plan_vigente_id = _plan_vigente_id(insc.profesorado)
        if plan_vigente_id:
            q = q.filter(plan_id=plan_vigente_id)

        # excluir ya aprobadas/promocionadas
        def _aprobado(e):
            mov_ok = insc.movimientos.filter(
                Q(espacio=e) & (
                    Q(tipo="REG", condicion__in=["Promoción","Aprobado"], nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Regular", nota_num__gte=6) |
                    Q(tipo="FIN", condicion="Equivalencia", nota_texto__iexact="Equivalencia")
                )
            ).exists()
            try:
                ciclo_ok = InscripcionEspacio.objects.filter(
                    inscripcion=insc, espacio=e,
                    estado_cursada__in=["APROBADA","PROMOCIONADO","PROMOCIONADA"]
                ).exists()
            except Exception:
                ciclo_ok = InscripcionEspacio.objects.filter(
                    inscripcion=insc, espacio=e,
                    estado__in=["APROBADA","PROMOCIONADO","PROMOCIONADA"]
                ).exists()
            return mov_ok or ciclo_ok

        base_ids = []
        for e in q:
            if _aprobado(e):
                continue
            # regularidad vigente
            try:
                if not _regularidad_vigente_para_rendir(insc, e):
                    continue
            except Exception:
                pass
            # correlativas RENDIR (si hay reglas)
            if _cumple_correlativas:
                tiene_rendir = Correlatividad.objects.filter(plan=e.plan, espacio=e, tipo="RENDIR").exists()
                if tiene_rendir:
                    try:
                        ok, _ = _cumple_correlativas(insc, e, "RENDIR")
                    except Exception:
                        ok = True
                    if not ok:
                        continue
            base_ids.append(e.id)

        self.fields["espacio"].queryset = EspacioCurricular.objects.filter(id__in=base_ids).order_by("anio","cuatrimestre","nombre")

    def clean(self):
        c = super().clean()
        cond = c.get("condicion")
        nota = c.get("nota_num")
        aus = c.get("ausente")
        just = c.get("ausencia_justificada")
        dispo = (c.get("disposicion_interna") or "").strip()

        if cond == "Equivalencia":
            if aus: raise ValidationError("Equivalencia no puede marcarse como ausente.")
            if not dispo: raise ValidationError("Para Equivalencia, la Disposición Interna es obligatoria.")
            return c

        if aus and nota is not None:
            raise ValidationError("Si marcás ‘Ausente’, no podés cargar nota.")
        if not aus and nota is not None and int(nota) < 6:
            raise ValidationError("En Final, si cargás nota debe ser 6..10.")
        if just and not aus:
            raise ValidationError("‘Ausencia justificada’ sólo corresponde con ‘Ausente’.")
        return c

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.tipo = "FIN"
        if self.cleaned_data.get("condicion") == "Equivalencia":
            obj.nota_texto = "Equivalencia"
            obj.nota_num = None
        else:
            obj.nota_texto = (obj.nota_texto or "").strip() or ""
        if commit: obj.save()
        return obj
