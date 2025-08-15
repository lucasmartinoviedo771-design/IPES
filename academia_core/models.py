# academia_core/models.py
from datetime import date, timedelta
from decimal import Decimal
import os
import re

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.contrib.auth import get_user_model


# ---------- Helpers para archivos ----------
def estudiante_foto_path(instance, filename):
    """
    Guarda la foto en /media/estudiantes/<dni>/foto.<ext>
    """
    base, ext = os.path.splitext(filename or "")
    safe_dni = (instance.dni or "sin_dni").strip()
    return f"estudiantes/{safe_dni}/foto{ext.lower()}"


# ===================== Catálogos básicos =====================

class Profesorado(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    plan_vigente = models.CharField(max_length=20, blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)


class PlanEstudios(models.Model):
    profesorado = models.ForeignKey(Profesorado, on_delete=models.CASCADE, related_name="planes")
    resolucion = models.CharField(max_length=30)          # ej: 1935/14
    resolucion_slug = models.SlugField(max_length=100, blank=True, null=True)
    nombre = models.CharField(max_length=120, blank=True)   # ej: Plan 2014
    vigente = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        unique_together = [("profesorado", "resolucion")]

    def __str__(self):
        nom = f" ({self.nombre})" if self.nombre else ""
        return f"{self.profesorado} - Res. {self.resolucion}{nom}"

    def save(self, *args, **kwargs):
        if not self.resolucion_slug:
            self.resolucion_slug = slugify((self.resolucion or "").replace("/", "-"))
        super().save(*args, **kwargs)


# --- Estudiante -------------------------------------------------------------
class Estudiante(models.Model):
    dni = models.CharField(max_length=20, unique=True)
    apellido = models.CharField(max_length=120)
    nombre = models.CharField(max_length=120)
    fecha_nacimiento = models.DateField(null=True, blank=True)

    # Encabezado del cartón
    lugar_nacimiento = models.CharField(max_length=120, blank=True)

    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    localidad = models.CharField(max_length=120, blank=True)
    activo = models.BooleanField(default=True)

    # Foto del alumno
    foto = models.ImageField(upload_to=estudiante_foto_path, null=True, blank=True)

    class Meta:
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.dni})"

    @property
    def foto_url(self):
        try:
            return self.foto.url if self.foto else ""
        except Exception:
            return ""

    # --- Accesos convenientes a materias/inscripciones del alumno (NO cambian el esquema) ---
    @property
    def cursadas_qs(self):
        """
        QuerySet de InscripcionEspacio del alumno (con select_related).
        Útil para filtrar por año académico, espacio, estado, etc.
        """
        from .models import InscripcionEspacio  # import local para evitar ciclos
        return (
            InscripcionEspacio.objects
            .filter(inscripcion__estudiante=self)
            .select_related('espacio', 'inscripcion', 'inscripcion__profesorado')
        )

    @property
    def espacios_qs(self):
        """
        QuerySet de EspacioCurricular que cursó/inscribe (cualquier año). DISTINCT para evitar duplicados.
        """
        from .models import EspacioCurricular
        return (
            EspacioCurricular.objects
            .filter(cursadas__inscripcion__estudiante=self)
            .distinct()
        )

    def espacios_en_anio(self, anio_academico: int):
        """Materias del alumno en un año académico dado."""
        return self.espacios_qs.filter(cursadas__anio_academico=anio_academico)


# --- EstudianteProfesorado --------------------------------------------------
class EstudianteProfesorado(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="inscripciones")
    profesorado = models.ForeignKey(Profesorado, on_delete=models.CASCADE, related_name="inscripciones")

    # Datos del trayecto
    cohorte = models.CharField(max_length=20, blank=True)
    libreta = models.CharField(max_length=50, blank=True)

    # Curso introductorio
    CI_CHOICES = [
        ("Aprobado", "Aprobado"),
        ("Desaprobado", "Desaprobado"),
        ("En curso", "En curso"),
        ("No aplica", "No aplica"),
    ]
    curso_introductorio = models.CharField(max_length=20, choices=CI_CHOICES, blank=True)

    # Check simple para “Legajo: Sí/No” en el cartón
    legajo_entregado = models.BooleanField(default=False)

    # Documentación del legajo (para calcular Completo/Incompleto)
    doc_dni_legalizado = models.BooleanField(default=False)
    doc_titulo_sec_legalizado = models.BooleanField(default=False)
    doc_cert_medico = models.BooleanField(default=False)
    doc_fotos_carnet = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(2)]
    )
    doc_folios_oficio = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(2)]
    )

    # DDJJ / Nota de compromiso
    nota_compromiso = models.BooleanField(default=False)

    # Adicionales para Certificación Docente
    doc_titulo_superior_legalizado = models.BooleanField(default=False)
    doc_incumbencias_titulo = models.BooleanField(default=False)

    # Situación académica declarada
    adeuda_materias = models.BooleanField(default=False)
    adeuda_detalle = models.TextField(blank=True)
    colegio = models.CharField(max_length=120, blank=True)

    # Estado del legajo (cacheado)
    LEGAJO_ESTADOS = [("Completo", "Completo"), ("Incompleto", "Incompleto")]
    legajo_estado = models.CharField(max_length=12, choices=LEGAJO_ESTADOS, default="Incompleto")

    # Promedio general (cacheado, por signal al guardar Movimiento)
    promedio_general = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    # Observaciones opcionales
    legajo = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = [("estudiante", "profesorado")]

    def __str__(self):
        return f"{self.estudiante} → {self.profesorado}"

    # --------- Lógica de legajo y promedio ---------
    def requisitos_obligatorios(self):
        """
        Requisitos de legajo:
        - Profesorados comunes: DNI + Título secundario + Cert. médico + Fotos(2) + Folios(2)
        - Certificación Docente: DNI + Cert. médico + Fotos(2) + Folios(2)
          + Título superior legalizado + Incumbencias del título
          (NO se exige título secundario).
        """
        nombre = (self.profesorado.nombre or "").lower()
        es_cert = ("certificación" in nombre) or ("certificacion" in nombre)

        base = [
            ("doc_dni_legalizado", True),
            ("doc_cert_medico", True),
            ("doc_fotos_carnet", 2),
            ("doc_folios_oficio", 2),
        ]
        if es_cert:
            base += [
                ("doc_titulo_superior_legalizado", True),
                ("doc_incumbencias_titulo", True),
            ]
        else:
            base += [("doc_titulo_sec_legalizado", True)]
        return base

    def calcular_legajo_estado(self):
        ok = True
        for campo, requerido in self.requisitos_obligatorios():
            val = getattr(self, campo)
            if requerido is True:
                ok = ok and bool(val)
            else:
                ok = ok and (val >= requerido)
        return "Completo" if ok else "Incompleto"

    # === NUEVO: helpers de legajo/condición administrativa ===
    def legajo_completo(self) -> bool:
        """True si cumple todos los requisitos obligatorios (puede rendir mesa)."""
        return self.calcular_legajo_estado() == "Completo"

    @property
    def es_condicional(self) -> bool:
        """True si el legajo está incompleto (puede cursar, pero no aprobar/promocionar por cursada ni rendir final)."""
        return not self.legajo_completo()

    def _mov_aprueba(self, m) -> bool:
        # FIN Regular >=6
        if m.tipo == "FIN" and m.condicion == "Regular" and m.nota_num is not None and m.nota_num >= 6:
            return True
        # REG Promoción/Aprobado con nota >=6 (num o texto con número >=6)
        if m.tipo == "REG" and m.condicion in {"Promoción", "Aprobado"}:
            if m.nota_num is not None and m.nota_num >= 6:
                return True
            if m.nota_texto:
                try:
                    n = int("".join(ch for ch in m.nota_texto if ch.isdigit()) or "0")
                    return n >= 6
                except Exception:
                    return False
        return False

    def recalcular_promedio(self):
        movs = list(self.movimientos.all())
        notas = []
        for m in movs:
            if self._mov_aprueba(m):
                if m.nota_num is not None:
                    notas.append(Decimal(m.nota_num))
                elif m.nota_texto:
                    try:
                        n = Decimal(int("".join(ch for ch in m.nota_texto if ch.isdigit()) or "0"))
                        notas.append(n)
                    except Exception:
                        pass
        if notas:
            prom = sum(notas) / Decimal(len(notas))
            self.promedio_general = prom.quantize(Decimal("0.01"))
        else:
            self.promedio_general = None
        self.save(update_fields=["promedio_general"])


class EspacioCurricular(models.Model):
    CUATRIS = [
        ("1", "1º Cuatr."),
        ("2", "2º Cuatr."),
        ("A", "Anual"),
    ]
    profesorado  = models.ForeignKey(Profesorado, on_delete=models.CASCADE, related_name="espacios")
    plan         = models.ForeignKey(PlanEstudios, on_delete=models.CASCADE, related_name="espacios",
                                     null=True, blank=True)
    anio         = models.CharField(max_length=10)  # ej: "1°", "2°"
    cuatrimestre = models.CharField(max_length=1, choices=CUATRIS)
    nombre       = models.CharField(max_length=160)
    horas        = models.PositiveIntegerField(default=0)
    formato      = models.CharField(max_length=80, blank=True)
    libre_habilitado = models.BooleanField(default=False, help_text="Permite rendir en condición de Libre")

    class Meta:
        ordering = ["anio", "cuatrimestre", "nombre"]
        constraints = [
            # 🔒 ÚNICA por profesorado+plan+nombre
            models.UniqueConstraint(
                fields=["profesorado", "plan", "nombre"],
                name="uq_espacio_prof_plan_nombre",
            ),
            # ✅ anio permitido {"1°","2°","3°","4°"}
            models.CheckConstraint(
                name="anio_valido_1a4",
                check=Q(anio__in=["1°", "2°", "3°", "4°"]),
            ),
        ]
        # (Opcional, ayuda a performance de búsquedas frecuentes)
        indexes = [
            models.Index(fields=["profesorado", "plan", "nombre"]),
        ]

    def __str__(self):
        # Muestra el label del choice, no el código ('1','2','A')
        return f"{self.anio} {self.get_cuatrimestre_display()} - {self.nombre}"

    @property
    def anio_num(self) -> int:
        """Devuelve el año como número para ordenamientos robustos."""
        try:
            return int(''.join(ch for ch in self.anio if ch.isdigit()))
        except Exception:
            return 0


# ===================== Correlatividades =====================

class Correlatividad(models.Model):
    """
    Regla de correlatividad para un espacio (de un plan).
    - tipo = CURSAR -> requisitos para inscribirse/cursar (cargar REG)
    - tipo = RENDIR -> requisitos para rendir final (cargar FIN)
    - requisito = REGULARIZADA / APROBADA
    """
    TIPO = [("CURSAR", "Para cursar"), ("RENDIR", "Para rendir")]
    REQ  = [("REGULARIZADA", "Regularizada"), ("APROBADA", "Aprobada")]

    plan       = models.ForeignKey(PlanEstudios, on_delete=models.CASCADE, related_name="correlatividades")
    espacio    = models.ForeignKey(EspacioCurricular, on_delete=models.CASCADE, related_name="correlativas_de")
    tipo       = models.CharField(maxlength=10, choices=TIPO) if False else models.CharField(max_length=10, choices=TIPO)  # keep max_length
    requisito  = models.CharField(max_length=14, choices=REQ)

    requiere_espacio = models.ForeignKey(
        EspacioCurricular, null=True, blank=True,
        on_delete=models.CASCADE, related_name="correlativas_requeridas"
    )
    requiere_todos_hasta_anio = models.PositiveSmallIntegerField(null=True, blank=True)

    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(requiere_espacio__isnull=False) & Q(requiere_todos_hasta_anio__isnull=True)) |
                    (Q(requiere_espacio__isnull=True)  & Q(requiere_todos_hasta_anio__isnull=False))
                ),
                name="correlatividad_requiere_algo",
            ),
            models.UniqueConstraint(
                fields=["plan", "espacio", "tipo", "requisito", "requiere_espacio", "requiere_todos_hasta_anio"],
                name="uniq_correlatividad_regla",
            ),
        ]

    def __str__(self):
        if self.requiere_espacio:
            req = f"{self.requiere_espacio.anio} {self.requiere_espacio.get_cuatrimestre_display()} - {self.requiere_espacio.nombre}"
        else:
            req = f"todos hasta {self.requiere_todos_hasta_anio}°"
        return f"[{self.plan.resolucion}] {self.espacio.nombre} / {self.tipo} → {self.requisito}: {req}"


# ---------- Helpers de estado académico (correlatividades) ----------

REG_OK = {"Promoción", "Aprobado", "Regular"}

def _tiene_regularizada(insc: EstudianteProfesorado, esp: EspacioCurricular, hasta_fecha=None) -> bool:
    qs = insc.movimientos.filter(espacio=esp, tipo="REG", condicion__in=REG_OK)
    if hasta_fecha:
        qs = qs.filter(fecha__lte=hasta_fecha)
    return qs.exists()

def _tiene_aprobada(insc: EstudianteProfesorado, esp: EspacioCurricular, hasta_fecha=None) -> bool:
    qs1 = insc.movimientos.filter(espacio=esp, tipo="REG", condicion__in={"Promoción", "Aprobado"})
    qs2 = insc.movimientos.filter(espacio=esp, tipo="FIN", condicion="Regular", nota_num__gte=6)
    qs3 = insc.movimientos.filter(espacio=esp, tipo="FIN", condicion="Equivalencia", nota_texto__iexact="Equivalencia")
    if hasta_fecha:
        qs1 = qs1.filter(fecha__lte=hasta_fecha)
        qs2 = qs2.filter(fecha__lte=hasta_fecha)
        qs3 = qs3.filter(fecha__lte=hasta_fecha)
    return qs1.exists() or qs2.exists() or qs3.exists()

def _cumple_correlativas(insc: EstudianteProfesorado, esp: EspacioCurricular, tipo: str, fecha=None):
    """
    Devuelve (ok, faltantes[]) para correlatividades de 'esp' según 'tipo' (CURSAR/RENDIR).
    """
    reglas = Correlatividad.objects.filter(plan=esp.plan, espacio=esp, tipo=tipo)
    faltan = []
    for r in reglas:
        if r.requiere_espacio:
            reqs = [r.requiere_espacio]
        else:
            reqs = list(
                EspacioCurricular.objects
                .filter(plan=esp.plan, profesorado=esp.profesorado)
                .filter(anio__in=[f"{i}°" for i in range(1, (r.requiere_todos_hasta_anio or 0) + 1)])
            )
        for req in reqs:
            if r.requisito == "REGULARIZADA":
                ok = _tiene_regularizada(insc, req, hasta_fecha=fecha)
            else:
                ok = _tiene_aprobada(insc, req, hasta_fecha=fecha)
            if not ok:
                faltan.append((r, req))
    return (len(faltan) == 0), faltan

def _tiene_regularidad_vigente(insc: EstudianteProfesorado, esp: EspacioCurricular, a_fecha) -> bool:
    """Regularidad vigente por 2 años desde la REG."""
    limite = a_fecha - timedelta(days=730)
    return insc.movimientos.filter(
        espacio=esp, tipo="REG", condicion="Regular", fecha__gte=limite
    ).exists()


# ===================== Movimientos académicos =====================

TIPO_MOV = [("REG", "Regularidad"), ("FIN", "Final")]

COND_REG = [
    ("Promoción", "Promoción"),
    ("Aprobado", "Aprobado"),
    ("Regular", "Regular"),
    ("Libre", "Libre"),
    ("Libre-I", "Libre-I"),
    ("Libre-AT", "Libre-AT"),
    ("Desaprobado", "Desaprobado"),
    ("Desaprobado_TP", "Desaprobado_TP"),
    ("Desaprobado_PA", "Desaprobado_PA"),
]

COND_FIN = [
    ("Regular", "Regular"),
    ("Libre", "Libre"),
    ("Equivalencia", "Equivalencia"),
]

class Movimiento(models.Model):
    NOTA_MINIMA = 6

    inscripcion = models.ForeignKey(EstudianteProfesorado, on_delete=models.CASCADE, related_name="movimientos")
    espacio = models.ForeignKey(EspacioCurricular, on_delete=models.CASCADE, related_name="movimientos")
    tipo = models.CharField(max_length=3, choices=TIPO_MOV)
    fecha = models.DateField(null=True, blank=True)

    condicion = models.CharField(max_length=20)  # validamos en clean() según tipo
    nota_num = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    nota_texto = models.CharField(max_length=40, blank=True)

    # Solo para FIN (cuando rinde en mesa)
    folio = models.CharField(max_length=20, blank=True)
    libro = models.CharField(max_length=20, blank=True)
    disposicion_interna = models.CharField(max_length=120, blank=True)  # para equivalencias

    # === NUEVO: control de mesas e intentos ===
    ausente = models.BooleanField(default=False)
    ausencia_justificada = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado"]
        # --- constraints de base de datos (además de clean()) ---
        constraints = [
            # Rango válido 0..10 cuando hay nota_num (para REG o FIN)
            models.CheckConstraint(
                name="nota_num_rango_valido",
                check=Q(nota_num__isnull=True) | (Q(nota_num__gte=0) & Q(nota_num__lte=10)),
            ),
            # FIN-REGULAR no puede tener nota_num < 6
            models.CheckConstraint(
                name="fin_regular_nota_minima",
                check=~(Q(tipo="FIN") & Q(condicion="Regular") & Q(nota_num__lt=6)),
            ),
            # Equivalencia: dispo obligatoria y leyenda exacta "Equivalencia" (case-insensitive)
            models.CheckConstraint(
                name="equivalencia_campos_oblig",
                check=~Q(condicion="Equivalencia") | (Q(disposicion_interna__gt="") & Q(nota_texto__iexact="Equivalencia")),
            ),
        ]

    # === NUEVO: intentos previos de FINAL (excluye ausente justificado) ===
    def _intentos_final_previos(self):
        qs = self.__class__.objects.filter(
            tipo="FIN",
            inscripcion=self.inscripcion,
            espacio=self.espacio,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        # no contamos ausente justificado
        qs = qs.exclude(ausente=True, ausencia_justificada=True)
        return qs.order_by("fecha", "id")

    def clean(self):
        if self.tipo == "REG":
            if self.condicion not in dict(COND_REG):
                raise ValidationError("Condición inválida para Regularidad.")
            if self.nota_num is not None and not (0 <= self.nota_num <= 10):
                raise ValidationError("La nota de Regularidad debe estar entre 0 y 10.")
            if self.condicion in {"Libre", "Libre-I", "Libre-AT"} and \
               self.inscripcion.movimientos.filter(espacio=self.espacio, tipo="REG", condicion="Regular").exists():
                raise ValidationError("No corresponde 'Libre' si el estudiante ya obtuvo Regular en este espacio.")

            # --- NUEVO: condicional administrativo no puede quedar Aprobado/Promoción por cursada
            if hasattr(self.inscripcion, "es_condicional") and self.inscripcion.es_condicional:
                if self.condicion in {"Promoción", "Aprobado"}:
                    raise ValidationError(
                        "Estudiante condicional: no puede quedar Aprobado/Promoción por cursada."
                    )

        elif self.tipo == "FIN":
            if self.condicion not in dict(COND_FIN):
                raise ValidationError("Condición inválida para Final.")

            # --- NUEVO: legajo debe estar completo para mesa de examen
            if hasattr(self.inscripcion, "legajo_completo") and not self.inscripcion.legajo_completo():
                raise ValidationError(
                    "No puede inscribirse a mesa: documentación/legajo incompleto."
                )

            if self.condicion == "Regular":
                if self.ausente:
                    # Ausente en mesa por Regularidad: no exigimos nota_num (se ignora)
                    pass
                else:
                    if self.nota_num is None:
                        raise ValidationError("Debe cargar la nota o marcar Ausente.")
                    if self.nota_num < self.NOTA_MINIMA:
                        raise ValidationError("Nota de Final por regularidad debe ser >= 6.")
                    if self.fecha and not _tiene_regularidad_vigente(self.inscripcion, self.espacio, self.fecha):
                        raise ValidationError("La regularidad no está vigente (2 años).")

            if self.condicion == "Libre":
                if hasattr(self.espacio, "libre_habilitado") and not self.espacio.libre_habilitado:
                    raise ValidationError("Este espacio no habilita condición Libre.")
                if _tiene_aprobada(self.inscripcion, self.espacio):
                    raise ValidationError("El espacio ya está aprobado; no corresponde rendir Libre.")
                if _tiene_regularizada(self.inscripcion, self.espacio):
                    raise ValidationError("El estudiante está regular: no corresponde rendir Libre.")
                if not self.ausente:
                    if self.nota_num is None:
                        raise ValidationError("Debe cargar la nota o marcar Ausente.")
                    if not (0 <= self.nota_num <= 10):
                        raise ValidationError("La nota debe estar entre 0 y 10.")

            if self.condicion != "Equivalencia":
                # Correlatividades para RENDIR (Equivalencia se valida aparte)
                ok, faltan = _cumple_correlativas(self.inscripcion, self.espacio, "RENDIR", fecha=self.fecha)
                if not ok:
                    msgs = []
                    for regla, req in faltan:
                        if getattr(regla, "requiere_espacio_id", None):
                            msgs.append(f"{regla.requisito.lower()} de '{req.nombre}'")
                        else:
                            msgs.append(f"{regla.requisito.lower()} de TODOS los espacios hasta {regla.requiere_todos_hasta_anio}°")
                    raise ValidationError(f"No cumple correlatividades para RENDIR: faltan {', '.join(msgs)}.")

            # --- NUEVO: control de intentos de FINAL (no cuenta ausente justificado)
            prev = list(self._intentos_final_previos())
            # ¿ya está aprobado por final?
            if any((m.nota_num or 0) >= 6 and not m.ausente for m in prev):
                raise ValidationError("El espacio ya fue aprobado por final anteriormente.")

            if len(prev) >= 3:
                raise ValidationError("Alcanzó las tres posibilidades de final: debe recursar el espacio.")

            # Validación de nota/ausencia coherente
            if self.ausente:
                # si es ausente, ignoramos la nota (si viene cargada, no la validamos)
                pass
            else:
                # si no es ausente, la nota (si viene) debe estar en rango
                if self.nota_num is not None and not (0 <= self.nota_num <= 10):
                    raise ValidationError("La nota debe estar entre 0 y 10.")

        else:
            raise ValidationError("Tipo de movimiento inválido.")

        # Coherencia profesorado
        if self.inscripcion.profesorado_id != self.espacio.profesorado_id:
            raise ValidationError("El espacio no pertenece al mismo profesorado de la inscripción del estudiante.")

        # Correlatividades para CURSAR al cargar REG
        if self.tipo == "REG":
            ok, faltan = _cumple_correlativas(self.inscripcion, self.espacio, "CURSAR", fecha=self.fecha)
            if not ok:
                msgs = []
                for regla, req in faltan:
                    if getattr(regla, "requiere_espacio_id", None):
                        msgs.append(f"{regla.requisito.lower()} de '{req.nombre}'")
                    else:
                        msgs.append(f"{regla.requisito.lower()} de TODOS los espacios hasta {regla.requiere_todos_hasta_anio}°")
                raise ValidationError(f"No cumple correlatividades para CURSAR: faltan {', '.join(msgs)}.")

    def __str__(self):
        return f"[{self.tipo}] {self.inscripcion.estudiante} - {self.espacio.nombre} - {self.condicion}"


# ===================== Inscripción a espacios (cursada por año) =====================

class InscripcionEspacio(models.Model):
    ESTADOS = [("EN_CURSO", "EN_CURSO"), ("BAJA", "BAJA")]

    inscripcion = models.ForeignKey(
        EstudianteProfesorado, on_delete=models.CASCADE, related_name="cursadas"
    )
    espacio = models.ForeignKey(
        EspacioCurricular, on_delete=models.CASCADE, related_name="cursadas"
    )
    anio_academico = models.PositiveIntegerField()
    fecha = models.DateField(default=date.today)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="EN_CURSO")

    class Meta:
        ordering = ["-anio_academico", "espacio__anio", "espacio__cuatrimestre", "espacio__nombre"]
        unique_together = [("inscripcion", "espacio", "anio_academico")]
        # Índice útil para consultas por alumno + año académico
        indexes = [
            models.Index(fields=["inscripcion", "anio_academico"], name="idx_cursada_insc_anio"),
        ]

    def clean(self):
        if self.inscripcion and self.espacio and \
           self.inscripcion.profesorado_id != self.espacio.profesorado_id:
            raise ValidationError("El espacio pertenece a otro profesorado.")
        try:
            ok, faltan = _cumple_correlativas(self.inscripcion, self.espacio, "CURSAR", fecha=self.fecha)
        except Exception:
            ok, faltan = True, []
        if not ok:
            msgs = []
            for regla, req in faltan:
                if getattr(regla, "requiere_espacio_id", None):
                    msgs.append(f"{regla.requisito.lower()} de '{req.nombre}'")
                else:
                    msgs.append(f"{regla.requisito.lower()} de TODOS los espacios hasta {regla.requiere_todos_hasta_anio}°")
            raise ValidationError(f"No cumple correlatividades para CURSAR: faltan {', '.join(msgs)}.")

    def __str__(self):
        return f"{self.inscripcion.estudiante} · {self.espacio.nombre} · {self.anio_academico}"


# ===================== Signals =====================

@receiver(post_save, sender=Movimiento)
def _recalc_promedio_on_mov(sender, instance, **kwargs):
    try:
        instance.inscripcion.recalcular_promedio()
    except Exception:
        pass

@receiver(post_save, sender=EstudianteProfesorado)
def _update_legajo_estado(sender, instance, **kwargs):
    """Recalcula y persiste el estado de legajo al guardar la inscripción."""
    try:
        estado = instance.calcular_legajo_estado()
        if estado != instance.legajo_estado:
            EstudianteProfesorado.objects.filter(pk=instance.pk).update(legajo_estado=estado)
    except Exception:
        pass


# ===================== ROLES / USUARIOS =====================

User = get_user_model()

class Docente(models.Model):
    dni = models.CharField(max_length=20, unique=True)
    apellido = models.CharField(max_length=120)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.dni})"

class DocenteEspacio(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name="asignaciones")
    espacio = models.ForeignKey(EspacioCurricular, on_delete=models.CASCADE, related_name="asignaciones_docentes")
    desde = models.DateField(null=True, blank=True)
    hasta = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("docente", "espacio")]

    def __str__(self):
        return f"{self.docente} → {self.espacio}"

# acceso M2M via 'espacios'
Docente.add_to_class(
    "espacios",
    models.ManyToManyField(EspacioCurricular, through=DocenteEspacio, related_name="docentes", blank=True)
)

class UserProfile(models.Model):
    ROLES = [
        ("ESTUDIANTE", "Estudiante"),
        ("DOCENTE", "Docente"),
        ("BEDEL", "Bedelía"),
        ("TUTOR", "Tutor"),
        ("SECRETARIA", "Secretaría"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=ROLES, default="ESTUDIANTE")

    # vínculos opcionales según rol
    estudiante = models.ForeignKey(Estudiante, null=True, blank=True, on_delete=models.SET_NULL, related_name="usuarios")
    docente = models.ForeignKey(Docente, null=True, blank=True, on_delete=models.SET_NULL, related_name="usuarios")
    profesorados_permitidos = models.ManyToManyField(Profesorado, blank=True, related_name="usuarios_habilitados")

    def __str__(self):
        return f"{self.user.username} [{self.rol}]"

@receiver(post_save, sender=User)
def _crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


# --- Actividad / Novedades -----------------------------------------------

class Actividad(models.Model):
    ACCIONES = [
        ("MOV_ALTA", "Carga de movimiento"),
        ("INSC_PROF", "Inscripción a profesorado"),
        ("INSC_ESP", "Inscripción a materia"),
        ("LOGIN", "Ingreso"),
        ("LOGOUT", "Salida"),
    ]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="actividades")
    rol_cache = models.CharField(max_length=20, blank=True)   # guardo el rol del momento
    accion = models.CharField(max_length=20, choices=ACCIONES)
    detalle = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        u = self.user.username if self.user else "—"
        return f"[{self.creado:%Y-%m-%d %H:%M}] {u} · {self.get_accion_display()}"
