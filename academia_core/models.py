# academia_core/models.py
from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings

import os
import re

from django.core.exceptions import ValidationError, FieldError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.contrib.auth import get_user_model


# --- Choices administrativos ---
class LegajoEstado(models.TextChoices):
    COMPLETO = "COMPLETO", "Completo"
    INCOMPLETO = "INCOMPLETO", "Incompleto"


class CondicionAdmin(models.TextChoices):
    REGULAR = "REGULAR", "Regular"
    CONDICIONAL = "CONDICIONAL", "Condicional"


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
    profesorado = models.ForeignKey(
        Profesorado, on_delete=models.CASCADE, related_name="planes"
    )
    resolucion = models.CharField(max_length=30)  # ej: 1935/14
    resolucion_slug = models.SlugField(max_length=100, blank=True, null=True)
    nombre = models.CharField(max_length=120, blank=True)  # ej: Plan 2014
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

    # ### INICIO DE LA ACTUALIZACIÓN SOLICITADA ###
    contacto_emergencia_tel = models.CharField(
        "Tel. de emergencia", max_length=30, blank=True, null=True
    )
    contacto_emergencia_parentesco = models.CharField(
        "Parentesco (emergencia)", max_length=50, blank=True, null=True
    )
    # ### FIN DE LA ACTUALIZACIÓN SOLICITADA ###

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

    # --- Accesos convenientes ---
    @property
    def cursadas_qs(self):
        """
        QuerySet de InscripcionEspacio del alumno (con select_related).
        Útil para filtrar por año académico, espacio, estado, etc.
        """
        from .models import InscripcionEspacio  # import local para evitar ciclos

        return InscripcionEspacio.objects.filter(
            inscripcion__estudiante=self
        ).select_related("espacio", "inscripcion", "inscripcion__profesorado")

    @property
    def espacios_qs(self):
        """
        QuerySet de EspacioCurricular que cursó/inscribe (cualquier año). DISTINCT para evitar duplicados.
        """
        from .models import EspacioCurricular

        return EspacioCurricular.objects.filter(
            cursadas__inscripcion__estudiante=self
        ).distinct()

    def espacios_en_anio(self, anio_academico: int):
        """Materias del alumno en un año académico dado."""
        return self.espacios_qs.filter(cursadas__anio_academico=anio_academico)


# --- EstudianteProfesorado --------------------------------------------------


class EstudianteProfesorado(models.Model):
    estudiante = models.ForeignKey(
        "Estudiante", on_delete=models.CASCADE, related_name="inscripciones_carrera"
    )
    profesorado = models.ForeignKey(
        "Profesorado", on_delete=models.PROTECT, related_name="inscripciones"
    )
    plan = models.ForeignKey(
        "PlanEstudios",
        on_delete=models.PROTECT,
        related_name="inscripciones",
        null=True,
        blank=True,
    )
    cohorte = models.PositiveSmallIntegerField(default=2025)
    # ... (resto de campos/documentación)

    # Datos del trayecto
    libreta = models.CharField("Libreta", max_length=50, blank=True, default="")

    # Curso introductorio
    CI_CHOICES = [
        ("Aprobado", "Aprobado"),
        ("Desaprobado", "Desaprobado"),
        ("En curso", "En curso"),
        ("No aplica", "No aplica"),
    ]
    curso_introductorio = models.CharField(
        max_length=20, choices=CI_CHOICES, blank=True
    )

    # Checks simples para cartón
    legajo_entregado = models.BooleanField(default=False)
    libreta_entregada = models.BooleanField("Libreta entregada", default=False)

    # Documentación base
    doc_dni_legalizado = models.BooleanField(default=False)
    doc_titulo_sec_legalizado = models.BooleanField(default=False)
    doc_cert_medico = models.BooleanField(default=False)
    doc_fotos_carnet = models.BooleanField(default=False, verbose_name="Fotos carnet")
    doc_folios_oficio = models.BooleanField(default=False, verbose_name="Folios oficio")

    # Certificación Docente (adicionales)
    doc_titulo_terciario_legalizado = models.BooleanField(
        "Doc título terciario/universitario legalizado", default=False
    )
    doc_incumbencias = models.BooleanField("Incumbencias presentadas", default=False)

    # DDJJ / Nota de compromiso (solo exigible cuando CONDICIONAL)
    nota_compromiso = models.BooleanField(default=False)

    # Situación académica declarada
    adeuda_materias = models.BooleanField(default=False)
    adeuda_detalle = models.TextField(blank=True)  # compatibilidad
    colegio = models.CharField(max_length=120, blank=True)  # compatibilidad

    # === NUEVOS ===
    titulo_en_tramite = models.BooleanField("Título en trámite", default=False)
    materias_adeudadas = models.TextField("Materias adeudadas", blank=True, default="")
    institucion_origen = models.CharField(
        "Escuela / Institución", max_length=200, blank=True, default=""
    )
    # =============

    # Estado cacheado
    legajo_estado = models.CharField(
        "Legajo estado",
        max_length=20,
        choices=LegajoEstado.choices,
        default=LegajoEstado.INCOMPLETO,
    )
    condicion_admin = models.CharField(
        "Condición administrativa",
        max_length=20,
        choices=CondicionAdmin.choices,
        default=CondicionAdmin.CONDICIONAL,
    )

    # Promedio general (cacheado, por signal o llamado manual)
    promedio_general = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    # Observaciones opcionales
    legajo = models.CharField(max_length=50, blank=True)

    def clean(self):
        # si hay plan, debe pertenecer al profesorado elegido
        if (
            self.plan_id
            and self.profesorado_id
            and getattr(self.plan, "profesorado_id", None)
            and self.plan.profesorado_id != self.profesorado_id
        ):
            raise ValidationError("El plan seleccionado no pertenece al profesorado.")

    def save(self, *args, **kwargs):
        self.full_clean()
        # No llamar a super() aquí si recalcular_promedio ya lo hace
        if "update_fields" not in kwargs:
            self.legajo_estado = self.calcular_legajo_estado()
            self.condicion_admin = self.calcular_condicion_admin()
        super().save(*args, **kwargs)

    class Meta:
        # un mismo estudiante no debería tener dos inscripciones al MISMO plan
        constraints = [
            models.UniqueConstraint(
                fields=["estudiante", "plan"], name="uniq_estudiante_plan"
            )
        ]
        ordering = ["estudiante__apellido", "estudiante__nombre", "profesorado__nombre"]

    def __str__(self):
        return f"{self.estudiante} → {self.profesorado}"

    # ----------------- Helpers de negocio -----------------
    def profesorado_es_certificacion_docente(self) -> bool:
        """
        Usa un booleano del modelo Profesoroado si existe (es_certificacion),
        si no, detecta por el nombre.
        """
        prof = getattr(self, "profesorado", None)
        if prof is None:
            return False
        if hasattr(prof, "es_certificacion"):
            return bool(getattr(prof, "es_certificacion"))
        nombre = (getattr(prof, "nombre", "") or "").lower()
        return ("certificación docente" in nombre) or (
            "certificacion docente" in nombre
        )

    def curso_intro_aprobado(self) -> bool:
        val = getattr(self, "curso_introductorio", None)
        s = (str(val) if val is not None else "").strip().upper()
        return s in {"APROBADO", "APROBADA", "SI", "SÍ", "OK", "TRUE", "1"}

    def requisitos_obligatorios(self):
        """Lista [(campo, requerido_bool)] según sea CD o no."""
        base = [
            ("doc_dni_legalizado", True),
            ("doc_cert_medico", True),
            ("doc_fotos_carnet", True),
            ("doc_folios_oficio", True),
        ]
        if self.profesorado_es_certificacion_docente():
            base += [
                ("doc_titulo_terciario_legalizado", True),
                ("doc_incumbencias", True),
            ]
        else:
            base += [("doc_titulo_sec_legalizado", True)]
        return base

    # --------- Cálculos cacheados ---------
    def calcular_legajo_estado(self) -> str:
        """COMPLETO = base + (sec o ter+inc) y NO título en trámite."""
        ok = True
        for campo, requerido in self.requisitos_obligatorios():
            val = bool(getattr(self, campo))
            ok = ok and (val if requerido is True else val >= requerido)
        # Nunca puede ser completo si el título está en trámite
        if self.titulo_en_tramite:
            ok = False
        return LegajoEstado.COMPLETO if ok else LegajoEstado.INCOMPLETO

    def legajo_completo(self) -> bool:
        return self.calcular_legajo_estado() == LegajoEstado.COMPLETO

    def calcular_condicion_admin(self) -> str:
        """
        REGULAR solo si legajo COMPLETO y NO adeuda materias.
        En cualquier otro caso -> CONDICIONAL.
        """
        return (
            CondicionAdmin.REGULAR
            if (self.legajo_completo() and not self.adeuda_materias)
            else CondicionAdmin.CONDICIONAL
        )

    @property
    def es_condicional(self) -> bool:
        return self.calcular_condicion_admin() == CondicionAdmin.CONDICIONAL

    # --------- Promedio (igual que tenías) ---------
    def _mov_aprueba(self, m) -> bool:
        if m.condicion is None:
            return False

        # FIN Regular >= 6
        if (
            m.tipo == "FIN"
            and m.condicion.codigo == "REGULAR"
            and m.nota_num is not None
            and m.nota_num >= 6
        ):
            return True
        # REG Promoción / Aprobado
        if m.tipo == "REG" and m.condicion.codigo in {"PROMOCION", "APROBADO"}:
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
                        n = Decimal(
                            int(
                                "".join(ch for ch in m.nota_texto if ch.isdigit())
                                or "0"
                            )
                        )
                        notas.append(n)
                    except Exception:
                        pass
        if notas:
            prom = sum(notas) / Decimal(len(notas))
            self.promedio_general = prom.quantize(Decimal("0.01"))
        else:
            self.promedio_general = None
        self.save(update_fields=["promedio_general"])

    


try:
    EstudianteProfesorado.LegajoEstado
except AttributeError:
    EstudianteProfesorado.LegajoEstado = LegajoEstado
    EstudianteProfesorado.CondicionAdmin = CondicionAdmin


class EspacioCurricular(models.Model):
    CUATRIS = [
        ("1", "1º Cuatr."),
        ("2", "2º Cuatr."),
        ("A", "Anual"),
    ]
    plan = models.ForeignKey(
        PlanEstudios, on_delete=models.CASCADE, related_name="espacios"
    )
    anio = models.CharField(max_length=10)  # ej: "1°", "2°"
    cuatrimestre = models.CharField(max_length=1, choices=CUATRIS)
    nombre = models.CharField(max_length=160)
    horas = models.PositiveIntegerField(default=0)
    formato = models.CharField(max_length=80, blank=True)
    libre_habilitado = models.BooleanField(
        default=False, help_text="Permite rendir en condición de Libre"
    )

    class Meta:
        ordering = ["anio", "cuatrimestre", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "nombre"],
                name="uq_espacio_plan_nombre",
            ),
            models.CheckConstraint(
                name="anio_valido_1a4",
                condition=models.Q(anio__in=["1°", "2°", "3°", "4°"]),
            ),
        ]

    def __str__(self):
        return f"{self.anio} {self.get_cuatrimestre_display()} - {self.nombre}"

    @property
    def anio_num(self) -> int:
        try:
            return int("".join(ch for ch in self.anio if ch.isdigit()))
        except Exception:
            return 0

    @property
    def es_edi(self) -> bool:
        n = (getattr(self, "nombre", "") or "").lower()
        return "edi" in n


# ===================== Correlatividades =====================


class Correlatividad(models.Model):
    TIPO = [("CURSAR", "Para cursar"), ("RENDIR", "Para rendir")]
    REQ = [("REGULARIZADA", "Regularizada"), ("APROBADA", "Aprobada")]

    plan = models.ForeignKey(
        PlanEstudios, on_delete=models.CASCADE, related_name="correlatividades"
    )
    espacio = models.ForeignKey(
        EspacioCurricular, on_delete=models.CASCADE, related_name="correlativas_de"
    )
    tipo = models.CharField(max_length=10, choices=TIPO)
    requisito = models.CharField(max_length=14, choices=REQ)

    requiere_espacio = models.ForeignKey(
        EspacioCurricular,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="correlativas_requeridas",
    )
    requiere_todos_hasta_anio = models.PositiveSmallIntegerField(null=True, blank=True)
    observaciones = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["espacio__anio", "espacio__cuatrimestre", "espacio__nombre"]
        # constraints y indexes pueden ir aquí si son necesarios

    def __str__(self):
        if self.requiere_espacio:
            req = f"{self.requiere_espacio.anio} {self.requiere_espacio.get_cuatrimestre_display()} - {self.requiere_espacio.nombre}"
        else:
            req = f"todos hasta {self.requiere_todos_hasta_anio}°"
        return f"[{self.plan.resolucion}] {self.espacio.nombre} / {self.tipo} → {self.requisito}: {req}"


# ===================== Condiciones Académicas (Dinámicas) =====================


class TipoCondicion(models.TextChoices):
    CURSADA = "REG", "Cursada"
    FINAL = "FIN", "Final"


class Condicion(models.Model):
    codigo = models.CharField(
        max_length=50,
        primary_key=True,
        help_text="Código único, ej: 'REGULAR', 'PROMOCION'",
    )
    nombre = models.CharField(
        max_length=100, help_text="Nombre para mostrar, ej: 'Regular', 'Promoción'"
    )
    tipo = models.CharField(max_length=3, choices=TipoCondicion.choices)

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"

    class Meta:
        verbose_name = "Condición Académica"
        verbose_name_plural = "Condiciones Académicas"


class EspacioCondicion(models.Model):
    espacio = models.ForeignKey(EspacioCurricular, on_delete=models.CASCADE)
    condicion = models.ForeignKey(Condicion, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.espacio.nombre} → permite {self.condicion.nombre}"

    class Meta:
        unique_together = (("espacio", "condicion"),)
        verbose_name = "Condición por Espacio"
        verbose_name_plural = "Condiciones por Espacio"


# ---------- Helpers de estado académico (correlatividades) ----------

REG_OK_CODIGOS = {"PROMOCION", "APROBADO", "REGULAR"}


def _tiene_regularizada(
    insc: EstudianteProfesorado, esp: EspacioCurricular, hasta_fecha=None
) -> bool:
    qs = insc.movimientos.filter(
        espacio=esp, tipo="REG", condicion__codigo__in=REG_OK_CODIGOS
    )
    if hasta_fecha:
        qs = qs.filter(fecha__lte=hasta_fecha)
    return qs.exists()


def _tiene_aprobada(
    insc: EstudianteProfesorado, esp: EspacioCurricular, hasta_fecha=None
) -> bool:
    qs1 = insc.movimientos.filter(
        espacio=esp, tipo="REG", condicion__codigo__in={"PROMOCION", "APROBADO"}
    )
    qs2 = insc.movimientos.filter(
        espacio=esp, tipo="FIN", condicion__codigo="REGULAR", nota_num__gte=6
    )
    qs3 = insc.movimientos.filter(
        espacio=esp,
        tipo="FIN",
        condicion__codigo="EQUIVALENCIA",
        nota_texto__iexact="Equivalencia",
    )
    if hasta_fecha:
        qs1 = qs1.filter(fecha__lte=hasta_fecha)
        qs2 = qs2.filter(fecha__lte=hasta_fecha)
        qs3 = qs3.filter(fecha__lte=hasta_fecha)
    return qs1.exists() or qs2.exists() or qs3.exists()


def _cumple_correlativas(
    insc: EstudianteProfesorado, esp: EspacioCurricular, tipo: str, fecha=None
):
    reglas = Correlatividad.objects.filter(plan=esp.plan, espacio=esp, tipo=tipo)
    faltan = []
    for r in reglas:
        if r.requiere_espacio:
            reqs = [r.requiere_espacio]
        else:
            reqs = list(
                EspacioCurricular.objects.filter(plan=esp.plan).filter(
                    anio__in=[
                        f"{i}°"
                        for i in range(1, (r.requiere_todos_hasta_anio or 0) + 1)
                    ]
                )
            )
        for req in reqs:
            if r.requisito == "REGULARIZADA":
                ok = _tiene_regularizada(insc, req, hasta_fecha=fecha)
            else:
                ok = _tiene_aprobada(insc, req, hasta_fecha=fecha)
            if not ok:
                faltan.append((r, req))
    return (len(faltan) == 0), faltan


def _tiene_regularidad_vigente(
    insc: EstudianteProfesorado, esp: EspacioCurricular, a_fecha
) -> bool:
    limite = a_fecha - timedelta(days=730)
    return insc.movimientos.filter(
        espacio=esp, tipo="REG", condicion__codigo="REGULAR", fecha__gte=limite
    ).exists()


# ===================== Movimientos académicos =====================

TIPO_MOV = [("REG", "Regularidad"), ("FIN", "Final")]


class Movimiento(models.Model):
    NOTA_MINIMA = 6

    inscripcion = models.ForeignKey(
        EstudianteProfesorado, on_delete=models.CASCADE, related_name="movimientos"
    )
    espacio = models.ForeignKey(
        EspacioCurricular, on_delete=models.CASCADE, related_name="movimientos"
    )
    tipo = models.CharField(max_length=3, choices=TIPO_MOV)
    fecha = models.DateField(null=True, blank=True)

    condicion = models.ForeignKey(
        Condicion,
        on_delete=models.PROTECT,
        related_name="movimientos",
        verbose_name="Condición",
        null=True,
        blank=True,
    )

    nota_num = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )
    nota_texto = models.CharField(max_length=40, blank=True)

    folio = models.CharField(max_length=20, blank=True)
    libro = models.CharField(max_length=20, blank=True)
    disposicion_interna = models.CharField(max_length=120, blank=True)

    ausente = models.BooleanField(default=False)
    ausencia_justificada = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado"]
        constraints = [
            models.CheckConstraint(
                name="nota_num_rango_valido",
                check=Q(nota_num__isnull=True)
                | (Q(nota_num__gte=0) & Q(nota_num__lte=10)),
            ),
        ]

    def _intentos_final_previos(self):
        qs = self.__class__.objects.filter(
            tipo="FIN",
            inscripcion=self.inscripcion,
            espacio=self.espacio,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        qs = qs.exclude(ausente=True, ausencia_justificada=True)
        return qs.order_by("fecha", "id")

    def clean(self):
        cond_codigo = self.condicion.codigo if self.condicion else None
        cond_tipo = self.condicion.tipo if self.condicion else None

        if self.condicion and self.tipo != cond_tipo:
            raise ValidationError(
                f"La condición '{self.condicion.nombre}' no es válida para un movimiento de tipo '{self.get_tipo_display()}'."
            )

        if self.tipo == "REG":
            if self.nota_num is not None and not (0 <= self.nota_num <= 10):
                raise ValidationError("La nota de Regularidad debe estar entre 0 y 10.")

            if (
                cond_codigo in {"LIBRE", "LIBRE-I", "LIBRE-AT"}
                and self.inscripcion.movimientos.filter(
                    espacio=self.espacio, tipo="REG", condicion__codigo="REGULAR"
                ).exists()
            ):
                raise ValidationError(
                    "No corresponde 'Libre' si el estudiante ya obtuvo Regular en este espacio."
                )

            if (
                hasattr(self.inscripcion, "es_condicional")
                and self.inscripcion.es_condicional
            ):
                if cond_codigo in {"PROMOCION", "APROBADO"}:
                    raise ValidationError(
                        "Estudiante condicional: no puede quedar Aprobado/Promoción por cursada."
                    )

        elif self.tipo == "FIN":
            if (
                hasattr(self.inscripcion, "legajo_completo")
                and not self.inscripcion.legajo_completo()
            ):
                raise ValidationError(
                    "No puede inscribirse a mesa: documentación/legajo incompleto."
                )

            if cond_codigo == "REGULAR":
                if not self.ausente:
                    if self.nota_num is None:
                        raise ValidationError("Debe cargar la nota o marcar Ausente.")
                    if self.nota_num < self.NOTA_MINIMA:
                        raise ValidationError(
                            "Nota de Final por regularidad debe ser >= 6."
                        )
                    if self.fecha and not _tiene_regularidad_vigente(
                        self.inscripcion, self.espacio, self.fecha
                    ):
                        raise ValidationError(
                            "La regularidad no está vigente (2 años)."
                        )

            if cond_codigo == "LIBRE":
                if (
                    hasattr(self.espacio, "libre_habilitado")
                    and not self.espacio.libre_habilitado
                ):
                    raise ValidationError("Este espacio no habilita condición Libre.")
                if _tiene_aprobada(self.inscripcion, self.espacio):
                    raise ValidationError(
                        "El espacio ya está aprobado; no corresponde rendir Libre."
                    )
                if _tiene_regularizada(self.inscripcion, self.espacio):
                    raise ValidationError(
                        "El estudiante está regular: no corresponde rendir Libre."
                    )
                if not self.ausente and self.nota_num is None:
                    raise ValidationError("Debe cargar la nota o marcar Ausente.")

            if cond_codigo == "EQUIVALENCIA":
                if (
                    not self.disposicion_interna
                    or self.nota_texto.lower() != "equivalencia"
                ):
                    raise ValidationError(
                        "Para Equivalencia, complete la Disposición y la nota de texto debe ser 'Equivalencia'."
                    )

            if cond_codigo != "EQUIVALENCIA":
                ok, faltan = _cumple_correlativas(
                    self.inscripcion, self.espacio, "RENDIR", fecha=self.fecha
                )
                if not ok:
                    msgs = [
                        f"{r.requisito.lower()} de '{req.nombre}'" for r, req in faltan
                    ]
                    raise ValidationError(
                        f"No cumple correlatividades para RENDIR: faltan {', '.join(msgs)}."
                    )

            prev = list(self._intentos_final_previos())
            if any((m.nota_num or 0) >= 6 and not m.ausente for m in prev):
                raise ValidationError(
                    "El espacio ya fue aprobado por final anteriormente."
                )
            if len(prev) >= 3:
                raise ValidationError(
                    "Alcanzó las tres posibilidades de final: debe recursar el espacio."
                )

        if self.inscripcion.profesorado_id != self.espacio.plan.profesorado_id:
            raise ValidationError(
                "El espacio no pertenece al mismo profesorado de la inscripción del estudiante."
            )

        if self.tipo == "REG":
            ok, faltan = _cumple_correlativas(
                self.inscripcion, self.espacio, "CURSAR", fecha=self.fecha
            )
            if not ok:
                msgs = [f"{r.requisito.lower()} de '{req.nombre}'" for r, req in faltan]
                raise ValidationError(
                    f"No cumple correlatividades para CURSAR: faltan {', '.join(msgs)}."
                )

    def __str__(self):
        return f"{self.inscripcion} · {self.espacio} · {self.condicion}"


# ===================== Inscripción a espacios (cursada por año) =====================
class EstadoInscripcion(models.TextChoices):
    EN_CURSO = "EN_CURSO", "En curso"
    BAJA = "BAJA", "Baja"


class InscripcionEspacio(models.Model):
    inscripcion = models.ForeignKey(
        EstudianteProfesorado, on_delete=models.CASCADE, related_name="cursadas"
    )
    espacio = models.ForeignKey(
        EspacioCurricular, on_delete=models.CASCADE, related_name="cursadas"
    )
    anio_academico = models.PositiveIntegerField()

    # renombrado desde 'fecha' y con auto_now_add (NO volver a definir 'fecha')
    fecha_inscripcion = models.DateField(auto_now_add=True)

    estado = models.CharField(
        max_length=10,
        choices=EstadoInscripcion.choices,
        default=EstadoInscripcion.EN_CURSO,
    )
    fecha_baja = models.DateField(null=True, blank=True)
    motivo_baja = models.TextField(blank=True, default="")

    # auditoría
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "-anio_academico",
            "espacio__anio",
            "espacio__cuatrimestre",
            "espacio__nombre",
        ]
        # unique_together = [("inscripcion", "espacio", "anio_academico")] # Replaced by UniqueConstraint
        indexes = [
            models.Index(
                fields=["inscripcion", "anio_academico"], name="idx_cursada_insc_anio"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["inscripcion", "espacio", "anio_academico"],
                name="uniq_insc_est_esp_ciclo",
            ),
            # EN_CURSO ⇒ fecha_baja debe ser NULL
            models.CheckConstraint(
                name="cursada_fecha_null_si_en_curso",
                check=(
                    ~Q(estado=EstadoInscripcion.EN_CURSO) | Q(fecha_baja__isnull=True)
                ),
            ),
            # BAJA ⇒ fecha_baja obligatoria
            models.CheckConstraint(
                name="cursada_fecha_baja_si_baja",
                check=(
                    Q(estado=EstadoInscripcion.BAJA, fecha_baja__isnull=False)
                    | ~Q(estado=EstadoInscripcion.BAJA)
                ),
            ),
            # fecha_baja ≥ fecha_inscripcion (o NULL)
            models.CheckConstraint(
                name="cursada_fecha_baja_ge_inscripcion",
                check=Q(fecha_baja__gte=F("fecha_inscripcion"))
                | Q(fecha_baja__isnull=True),
            ),
        ]

    def clean(self):
        # mismo profesorado
        if (
            self.inscripcion
            and self.espacio
            and self.inscripcion.profesorado_id != self.espacio.plan.profesorado_id
        ):
            raise ValidationError("El espacio pertenece a otro profesorado.")

        # coherencia estado/fecha_baja (además de constraints)
        if self.estado == EstadoInscripcion.BAJA and not self.fecha_baja:
            raise ValidationError("Debe indicar 'fecha_baja' cuando el estado es Baja.")
        if self.estado == EstadoInscripcion.EN_CURSO and self.fecha_baja:
            raise ValidationError(
                "No debe tener 'fecha_baja' si la cursada está En curso."
            )

        # correlatividades según fecha_inscripcion
        try:
            ok, faltan = _cumple_correlativas(
                self.inscripcion, self.espacio, "CURSAR", fecha=self.fecha_inscripcion
            )
        except Exception:
            ok, faltan = True, []
        if not ok:
            msgs = [f"{r.requisito.lower()} de '{req.nombre}'" for r, req in faltan]
            raise ValidationError(
                f"No cumple correlatividades para CURSAR: faltan {', '.join(msgs)}."
            )

    def __str__(self):
        return f"{self.inscripcion.estudiante} · {self.espacio.nombre} · {self.anio_academico}"


# (opcional, recomendado) Log de cambios de estado
class InscripcionEspacioEstadoLog(models.Model):
    insc_espacio = models.ForeignKey(
        InscripcionEspacio, on_delete=models.CASCADE, related_name="estado_logs"
    )
    estado = models.CharField(max_length=20)  # EN_CURSO/BAJA/…
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    nota = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-fecha"]


# ===================== Signals =====================


@receiver(post_save, sender=Movimiento)
def _recalc_promedio_on_mov(sender, instance, **kwargs):
    try:
        instance.inscripcion.recalcular_promedio()
    except Exception:
        pass


@receiver(post_save, sender=EstudianteProfesorado)
def _update_legajo_estado(sender, instance, **kwargs):
    try:
        estado = instance.calcular_legajo_estado()
        if estado != instance.legajo_estado:
            EstudianteProfesorado.objects.filter(pk=instance.pk).update(
                legajo_estado=estado
            )
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
    docente = models.ForeignKey(
        Docente, on_delete=models.CASCADE, related_name="asignaciones"
    )
    espacio = models.ForeignKey(
        EspacioCurricular,
        on_delete=models.CASCADE,
        related_name="asignaciones_docentes",
    )
    desde = models.DateField(null=True, blank=True)
    hasta = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("docente", "espacio")]

    def __str__(self):
        return f"{self.docente} → {self.espacio}"


Docente.add_to_class(
    "espacios",
    models.ManyToManyField(
        EspacioCurricular, through=DocenteEspacio, related_name="docentes", blank=True
    ),
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

    estudiante = models.ForeignKey(
        Estudiante,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios",
    )
    docente = models.ForeignKey(
        Docente,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios",
    )
    profesorados_permitidos = models.ManyToManyField(
        Profesorado, blank=True, related_name="usuarios_habilitados"
    )

    def __str__(self):
        return f"{self.user.username} [{self.rol}]"


@receiver(post_save, sender=User)
def _crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


# ===================== Inscripción a Mesa de Examen Final =====================


class Actividad(models.Model):
    ACCIONES = [
        ("MOV_ALTA", "Carga de movimiento"),
        ("INSC_PROF", "Inscripción a profesorado"),
        ("INSC_ESP", "Inscripción a materia"),
        ("LOGIN", "Ingreso"),
        ("LOGOUT", "Salida"),
    ]
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actividades",
    )
    rol_cache = models.CharField(max_length=20, blank=True)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    detalle = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        u = self.user.username if self.user else "—"
        return f"[{self.creado:%Y-%m-%d %H:%M}] {u} · {self.get_accion_display()}"


class InscripcionFinal(models.Model):
    inscripcion_cursada = models.ForeignKey(
        InscripcionEspacio, on_delete=models.CASCADE, related_name="finales"
    )
    fecha_examen = models.DateField()
    creado = models.DateTimeField(auto_now_add=True)

    ESTADOS = (
        ("INSCRIPTO", "Inscripto"),
        ("APROBADO", "Aprobado"),
        ("DESAPROBADO", "Desaprobado"),
        ("AUSENTE", "Ausente"),
    )

    estado = models.CharField(max_length=12, choices=ESTADOS, default="INSCRIPTO")
    nota_final = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    ausente = models.BooleanField(default=False)
    ausencia_justificada = models.BooleanField(default=False)

    class Meta:
        ordering = ["-creado"]
        unique_together = ("inscripcion_cursada", "fecha_examen")
        verbose_name = "Inscripción a Mesa Final"
        verbose_name_plural = "Inscripciones a Mesas Finales"

    def __str__(self):
        est = self.inscripcion_cursada.inscripcion.estudiante
        esp = self.inscripcion_cursada.espacio
        return f"{est.apellido}, {est.nombre} · {esp.nombre} [{self.fecha_examen}]"

    @property
    def estudiante(self):
        return self.inscripcion_cursada.inscripcion.estudiante

    @property
    def espacio(self):
        return self.inscripcion_cursada.espacio


class Horario(models.Model):
    DIAS = [
        (1, "Lunes"),
        (2, "Martes"),
        (3, "Miércoles"),
        (4, "Jueves"),
        (5, "Viernes"),
        (6, "Sábado"),
    ]

    espacio = models.ForeignKey(
        EspacioCurricular, on_delete=models.CASCADE, related_name="horarios"
    )
    dia_semana = models.IntegerField(choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    docente = models.ForeignKey(
        Docente,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="horarios",
    )

    def __str__(self):
        return f"{self.espacio.nombre} - {self.get_dia_semana_display()} ({self.hora_inicio} - {self.hora_fin})"


class CorePerms(models.Model):
    """
    Modelo NO gestionado, solo para colgar permisos custom.
    No crea tablas; sirve para que existan los Permission en la BD.
    """
    class Meta:
        managed = False          # ← CAMBIO CLAVE (en lugar de proxy=True)
        default_permissions = () # no crear add/change/delete/view
        app_label = "academia_core"
        permissions = [
            ("open_close_windows", "Puede abrir/cerrar ventanas de inscripción"),
            ("enroll_self", "Puede inscribirse a sí mismo"),
            ("enroll_others", "Puede inscribir a terceros"),
            ("manage_correlatives", "Puede gestionar correlatividades"),
            ("publish_grades", "Puede publicar calificaciones"),
            ("view_any_student_record", "Puede ver ficha/cartón de cualquier estudiante"),
            ("edit_student_record", "Puede editar ficha/cartón de estudiantes"),
            ("view_inscripcioncarrera", "Puede ver inscripciones a carrera"),
            ("add_inscripcioncarrera", "Puede crear inscripciones a carrera"),
            ("change_inscripcioncarrera", "Puede editar inscripciones a carrera"),
        ]

class RequisitosIngreso(models.Model):
    # IMPORTANTE: ajustá el import / referencia ↓ a TU modelo de inscripción
    inscripcion = models.OneToOneField(
        "academia_core.EstudianteProfesorado",  # cambia TU_APP al label real de esa app
        on_delete=models.CASCADE,
        related_name="requisitos"
    )
    # Generales
    req_dni = models.BooleanField(default=False)
    req_cert_med = models.BooleanField(default=False)
    req_fotos = models.BooleanField(default=False)
    req_folios = models.BooleanField(default=False)
    # Título (para carreras generales)
    req_titulo_sec = models.BooleanField(default=False)
    req_titulo_tramite = models.BooleanField(default=False)
    req_adeuda = models.BooleanField(default=False)
    req_adeuda_mats = models.CharField(max_length=255, blank=True)
    req_adeuda_inst = models.CharField(max_length=255, blank=True)
    # Certificación Docente
    req_titulo_sup = models.BooleanField(default=False)
    req_incumbencias = models.BooleanField(default=False)
    # Nuevo: “Preinscripción”
    req_condicion = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Requisitos de {self.inscripcion_id}"
