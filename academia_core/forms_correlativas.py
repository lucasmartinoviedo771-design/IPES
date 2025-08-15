# academia_core/forms_correlativas.py
from django import forms
from .models import (
    Profesorado,
    PlanEstudios,
    EspacioCurricular,
    Correlatividad,
)

TIPO_CURSAR = "CURSAR"
TIPO_RENDIR = "RENDIR"


class SeleccionEspacioForm(forms.Form):
    profesorado = forms.ModelChoiceField(
        queryset=Profesorado.objects.all(), required=True, label="Profesorado"
    )
    plan = forms.ModelChoiceField(
        queryset=PlanEstudios.objects.none(), required=True, label="Plan"
    )
    espacio = forms.ModelChoiceField(
        queryset=EspacioCurricular.objects.none(), required=True, label="Espacio curricular"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pueden venir como id/str/instancia → normalizo a id
        p_val = self.data.get("profesorado") or self.initial.get("profesorado")
        plan_val = self.data.get("plan") or self.initial.get("plan")

        def to_id(v):
            if hasattr(v, "pk"):
                return v.pk
            if isinstance(v, str):
                v = v.strip()
                return int(v) if v.isdigit() else None
            return v or None

        p_id = to_id(p_val)
        plan_id = to_id(plan_val)

        # Si no vino profesorado, tomar el primero disponible
        if not p_id:
            first_prof = Profesorado.objects.order_by("id").first()
            if first_prof:
                p_id = first_prof.pk
                self.initial["profesorado"] = p_id

        # Poblar planes del profesorado (y autoseleccionar si hay uno solo)
        if p_id:
            plans = PlanEstudios.objects.filter(profesorado_id=p_id).order_by("-vigente", "resolucion")
            self.fields["plan"].queryset = plans
            if not plan_id and plans.count() == 1:
                plan_id = plans.first().pk
                self.initial["plan"] = plan_id
        else:
            self.fields["plan"].queryset = PlanEstudios.objects.none()

        # Poblar espacios solo si hay profesorado + plan
        if p_id and plan_id:
            qs = (EspacioCurricular.objects
                  .filter(profesorado_id=p_id, plan_id=plan_id)
                  .order_by("anio", "cuatrimestre", "nombre"))
            self.fields["espacio"].queryset = qs
        else:
            self.fields["espacio"].queryset = EspacioCurricular.objects.none()


class EditaCorrelativasForm(forms.Form):
    # === CURSAR ===
    cursar_regularizadas = forms.ModelMultipleChoiceField(
        queryset=EspacioCurricular.objects.none(),
        required=False,
        label="Para CURSAR: tener REGULARIZADA",
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "checkboxselectmultiple"}
        ),
    )
    cursar_aprobadas = forms.ModelMultipleChoiceField(
        queryset=EspacioCurricular.objects.none(),
        required=False,
        label="Para CURSAR: tener APROBADA",
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "checkboxselectmultiple"}
        ),
    )

    # === RENDIR ===
    rendir_aprobadas = forms.ModelMultipleChoiceField(
        queryset=EspacioCurricular.objects.none(),
        required=False,
        label="Para RENDIR: tener APROBADA",
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "checkboxselectmultiple"}
        ),
    )

    def __init__(self, espacio: EspacioCurricular, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.espacio = espacio

        # mismas materias del plan, excepto la actual
        mismos = (
            EspacioCurricular.objects
            .filter(profesorado=espacio.profesorado, plan=espacio.plan)
            .exclude(id=espacio.id)
            .order_by("anio", "cuatrimestre", "nombre")
        )
        for f in ("cursar_regularizadas", "cursar_aprobadas", "rendir_aprobadas"):
            self.fields[f].queryset = mismos

        plan = espacio.plan
        existentes = Correlatividad.objects.filter(plan=plan, espacio=espacio)

        # iniciales (SOLO las que refieren a un espacio puntual)
        self.fields["cursar_regularizadas"].initial = list(
            existentes.filter(tipo=TIPO_CURSAR, requisito="REGULARIZADA", requiere_espacio__isnull=False)
            .values_list("requiere_espacio_id", flat=True)
        )
        self.fields["cursar_aprobadas"].initial = list(
            existentes.filter(tipo=TIPO_CURSAR, requisito="APROBADA", requiere_espacio__isnull=False)
            .values_list("requiere_espacio_id", flat=True)
        )
        self.fields["rendir_aprobadas"].initial = list(
            existentes.filter(tipo=TIPO_RENDIR, requisito="APROBADA", requiere_espacio__isnull=False)
            .values_list("requiere_espacio_id", flat=True)
        )
        
        # (cinturón y tiradores) fuerza que el <ul> tenga la clase para tu CSS
        for f in ("cursar_regularizadas", "cursar_aprobadas", "rendir_aprobadas"):
            w = self.fields[f].widget
            cls = (w.attrs.get("class") or "").strip()
            if "checkboxselectmultiple" not in cls:
                w.attrs["class"] = (cls + " checkboxselectmultiple").strip()
        

    def sync_to_db(self):
        """
        Sin 'todos hasta año': eliminamos cualquier regla de ese tipo
        y sincronizamos SOLO las de requiere_espacio seleccionado.
        """
        esp = self.espacio
        plan = esp.plan

        # 1) borrar cualquier 'todos hasta año' preexistente
        Correlatividad.objects.filter(
            plan=plan, espacio=esp, requiere_todos_hasta_anio__isnull=False
        ).delete()

        # 2) construir set deseado (solo requiere_espacio)
        want = set()
        for req, qs in (
            ("REGULARIZADA", self.cleaned_data.get("cursar_regularizadas", [])),
            ("APROBADA",    self.cleaned_data.get("cursar_aprobadas",    [])),
        ):
            for e in qs:
                want.add((TIPO_CURSAR, req, e.id))

        for e in self.cleaned_data.get("rendir_aprobadas", []):
            want.add((TIPO_RENDIR, "APROBADA", e.id))

        # 3) estado actual (solo reglas con requiere_espacio)
        have = set(
            Correlatividad.objects
            .filter(plan=plan, espacio=esp, requiere_todos_hasta_anio__isnull=True)
            .values_list("tipo", "requisito", "requiere_espacio_id")
        )

        # 4) crear faltantes
        for (tipo, req, req_esp_id) in (want - have):
            Correlatividad.objects.create(
                plan=plan,
                espacio=esp,
                tipo=tipo,
                requisito=req,
                requiere_espacio_id=req_esp_id,
            )

        # 5) borrar sobrantes
        for (tipo, req, req_esp_id) in (have - want):
            Correlatividad.objects.filter(
                plan=plan, espacio=esp, tipo=tipo, requisito=req, requiere_espacio_id=req_esp_id
            ).delete()
