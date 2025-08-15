# academia_core/forms_carga.py
from datetime import date
import re

import logging
DBG = False
def _dbg(*args, **kwargs):
    # no-op para silenciar logs del form
    return

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Movimiento,
    EstudianteProfesorado,
    EspacioCurricular,
    Profesorado,
    InscripcionEspacio,
    Estudiante,
    Correlatividad,   # <- lo usamos para detectar si un espacio tiene reglas CURSAR
)

# Si tenés helpers de correlatividades en modelos:
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
    # permite vacío (None) para casos donde la nota es opcional
    return [("", "—")] + [(i, str(i)) for i in range(0, 11)]


def _coerce_nota(v):
    return int(v) if v not in (None, "",) else None


def _profes_qs_for_user(user):
    perfil = getattr(user, "perfil", None)
    if perfil and perfil.rol in ("BEDEL", "TUTOR"):
        return perfil.profesorados_permitidos.all()
    return Profesorado.objects.all()


# ===================== Cargar Movimiento =====================

class CargarMovimientoForm(forms.ModelForm):
    tipo = forms.ChoiceField(
        choices=(("REG", "Regularidad"), ("FIN", "Final")),
        label="Tipo",
        widget=forms.Select(attrs={"class": "inp"})
    )
    fecha = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "inp"}),
        label="Fecha",
    )
    condicion = forms.ChoiceField(
        choices=REG_CONDICIONES,
        label="Condición",
        widget=forms.Select(attrs={"class": "inp"})
    )
    nota_num = forms.TypedChoiceField(
        choices=_nota_choices(),
        coerce=_coerce_nota,
        empty_value=None,
        required=False,
        label="Nota num.",
        widget=forms.Select(attrs={"class": "inp"}),
    )

    class Meta:
        model = Movimiento
        fields = (
            "inscripcion", "espacio",
            "tipo", "fecha", "condicion",
            "nota_num",
            "folio", "libro", "disposicion_interna",
        )
        widgets = {
            "inscripcion": forms.Select(attrs={"class": "inp"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
            "folio": forms.TextInput(attrs={"class": "inp"}),
            "libro": forms.TextInput(attrs={"class": "inp"}),
            "disposicion_interna": forms.TextInput(attrs={"class": "inp"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        profes_permitidos = _profes_qs_for_user(user)
        perfil = getattr(user, "perfil", None)
        if perfil and perfil.rol in ("BEDEL", "TUTOR"):
            self.fields["inscripcion"].queryset = (
                EstudianteProfesorado.objects
                .filter(profesorado__in=profes_permitidos)
                .select_related("estudiante", "profesorado")
                .order_by("estudiante__apellido", "estudiante__nombre")
            )
            self.fields["espacio"].queryset = (
                EspacioCurricular.objects
                .filter(profesorado__in=profes_permitidos)
                .order_by("profesorado__nombre", "anio", "cuatrimestre", "nombre")
            )
        else:
            self.fields["inscripcion"].queryset = (
                EstudianteProfesorado.objects.select_related("estudiante", "profesorado")
            )
            self.fields["espacio"].queryset = EspacioCurricular.objects.all()

        tipo_inicial = (self.data.get("tipo")
                        or self.initial.get("tipo")
                        or "REG")
        self._set_condiciones(tipo_inicial)

    def _set_condiciones(self, tipo):
        self.fields["condicion"].choices = FIN_CONDICIONES if tipo == "FIN" else REG_CONDICIONES

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        condicion = cleaned.get("condicion")
        nota = cleaned.get("nota_num")
        dispo = (cleaned.get("disposicion_interna") or "").strip()

        ins = cleaned.get("inscripcion")
        esp = cleaned.get("espacio")
        if ins and esp and ins.profesorado_id != esp.profesorado_id:
            raise ValidationError("El espacio debe pertenecer al mismo profesorado de la inscripción.")

        if tipo == "REG":
            validas = {c for c, _ in REG_CONDICIONES}
            if condicion not in validas:
                raise ValidationError("Condición inválida para Regularidad.")
            if condicion in ("Promoción", "Aprobado"):
                if nota is None or int(nota) < 6:
                    raise ValidationError("Para Promoción/Aprobado la nota debe ser 6..10.")
            elif condicion == "Desaprobado":
                if nota is not None and int(nota) > 5:
                    raise ValidationError("Para Desaprobado la nota debe ser 0..5.")
        elif tipo == "FIN":
            validas = {c for c, _ in FIN_CONDICIONES}
            if condicion not in validas:
                raise ValidationError("Condición inválida para Final.")
            if condicion == "Equivalencia":
                if not dispo:
                    raise ValidationError("Para Equivalencia, la Disposición Interna es obligatoria.")
            elif condicion == "Regular":
                if nota is not None and int(nota) < 6:
                    raise ValidationError("Final por Regularidad: si cargás nota debe ser 6..10.")
        return cleaned

    def save(self, commit=True):
        obj: Movimiento = super().save(commit=False)
        if self.cleaned_data.get("tipo") == "FIN" and self.cleaned_data.get("condicion") == "Equivalencia":
            obj.nota_texto = "Equivalencia"
            obj.nota_num = None
        else:
            obj.nota_texto = (obj.nota_texto or "").strip() or ""
        if commit:
            obj.save()
        return obj


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
            # autosubmit para repoblar 'espacio' al cambiar inscripción
            "inscripcion": forms.Select(attrs={"class": "inp", "onchange": "this.form.submit()"}),
            "espacio": forms.Select(attrs={"class": "inp"}),
        }
        labels = {"anio_academico": "Año académico"}

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

        # Año seleccionado (para excluir ya inscriptos en ese año)
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

        # 4) Espacios: del profesorado de la inscripción + filtros
        insc_id = self.data.get("inscripcion") or getattr(self.initial.get("inscripcion"), "pk", None)

        if insc_id:
            try:
                insc = EstudianteProfesorado.objects.select_related("profesorado").get(pk=insc_id)
            except EstudianteProfesorado.DoesNotExist:
                self.fields["espacio"].queryset = EspacioCurricular.objects.none()
                return

            base = (
                EspacioCurricular.objects
                .filter(profesorado=insc.profesorado)
                .order_by("anio", "cuatrimestre", "nombre")
            )

            # 4.a) Correlatividades CURSAR:
            #     - si el espacio TIENE reglas CURSAR, se exige cumplirlas
            #     - si NO tiene reglas, se permite
            allowed_ids = []
            for e in base:
                ok = True
                if _cumple_correlativas:
                    tiene_reglas = Correlatividad.objects.filter(
                        plan=e.plan, espacio=e, tipo="CURSAR"
                    ).exists()
                    if tiene_reglas:
                        try:
                            ok, _faltan = _cumple_correlativas(insc, e, "CURSAR")
                        except Exception:
                            ok = True  # no bloquear por error de configuración
                if ok:
                    allowed_ids.append(e.id)

            base = base.filter(id__in=allowed_ids)

            # 4.b) Excluir espacios ya aprobados
            aprobados_ids = set(
                insc.movimientos.filter(
                    Q(espacio__in=base) & (
                        Q(tipo="REG", condicion__in=["Promoción", "Aprobado"], nota_num__gte=6) |
                        Q(tipo="FIN", condicion="Regular",                   nota_num__gte=6) |
                        Q(tipo="FIN", condicion="Equivalencia",              nota_texto__iexact="Equivalencia")
                    )
                ).values_list("espacio_id", flat=True)
            )
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

            self.fields["espacio"].queryset = base
        else:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()
            self.fields["espacio"].help_text = "Elegí una inscripción primero."

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

        # No duplicar
        ya = InscripcionEspacio.objects.filter(inscripcion=insc, espacio=esp, anio_academico=anio)
        if self.instance.pk:
            ya = ya.exclude(pk=self.instance.pk)
        if ya.exists():
            raise ValidationError("Ya existe una cursada de este espacio para ese año académico.")

        # No reinscribir si ya está aprobado
        aprobada = insc.movimientos.filter(
            Q(espacio=esp) & (
                Q(tipo="REG", condicion__in=["Promoción", "Aprobado"], nota_num__gte=6) |
                Q(tipo="FIN", condicion="Regular",                   nota_num__gte=6) |
                Q(tipo="FIN", condicion="Equivalencia",              nota_texto__iexact="Equivalencia")
            )
        ).exists()
        if aprobada:
            raise ValidationError("El espacio ya está aprobado: no corresponde reinscribir.")

        # Defensa adicional por correlatividades (si hay helper y el espacio tiene reglas)
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
