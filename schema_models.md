# Inventario de modelos — academia_core

## Profesorado  
Tabla: `academia_core_profesorado`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `planes` | `ForeignKey` | REL→PlanEstudios | ✔ |  |  |  |
| `inscripciones` | `ForeignKey` | REL→EstudianteProfesorado | ✔ |  |  |  |
| `espacios` | `ForeignKey` | REL→EspacioCurricular | ✔ |  |  |  |
| `usuarios_habilitados` | `ManyToManyField` | M2M→UserProfile | ✔ |  |  | ✔ |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `nombre` | `CharField` |  |  |  | ✔ |  |
| `plan_vigente` | `CharField` |  |  |  |  |  |
| `slug` | `SlugField` |  | ✔ |  | ✔ |  |

## PlanEstudios  
Tabla: `academia_core_planestudios`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `inscripciones` | `ForeignKey` | REL→EstudianteProfesorado | ✔ |  |  |  |
| `espacios` | `ForeignKey` | REL→EspacioCurricular | ✔ |  |  |  |
| `correlatividades` | `ForeignKey` | REL→Correlatividad | ✔ |  |  |  |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `profesorado` | `ForeignKey` | FK→Profesorado |  |  |  |  |
| `resolucion` | `CharField` |  |  |  |  |  |
| `resolucion_slug` | `SlugField` |  | ✔ |  |  |  |
| `nombre` | `CharField` |  |  |  |  |  |
| `vigente` | `BooleanField` |  |  |  |  |  |
| `observaciones` | `TextField` |  |  |  |  |  |

## Estudiante  
Tabla: `academia_core_estudiante`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `inscripciones_carrera` | `ForeignKey` | REL→EstudianteProfesorado | ✔ |  |  |  |
| `usuarios` | `ForeignKey` | REL→UserProfile | ✔ |  |  |  |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `dni` | `CharField` |  |  |  | ✔ |  |
| `apellido` | `CharField` |  |  |  |  |  |
| `nombre` | `CharField` |  |  |  |  |  |
| `fecha_nacimiento` | `DateField` |  | ✔ |  |  |  |
| `lugar_nacimiento` | `CharField` |  |  |  |  |  |
| `email` | `CharField` |  |  |  |  |  |
| `telefono` | `CharField` |  |  |  |  |  |
| `localidad` | `CharField` |  |  |  |  |  |
| `activo` | `BooleanField` |  |  |  |  |  |
| `foto` | `FileField` |  | ✔ |  |  |  |
| `contacto_emergencia_tel` | `CharField` |  | ✔ |  |  |  |
| `contacto_emergencia_parentesco` | `CharField` |  | ✔ |  |  |  |

## EstudianteProfesorado  
Tabla: `academia_core_estudianteprofesorado`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `movimientos` | `ForeignKey` | REL→Movimiento | ✔ |  |  |  |
| `cursadas` | `ForeignKey` | REL→InscripcionEspacio | ✔ |  |  |  |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `estudiante` | `ForeignKey` | FK→Estudiante |  |  |  |  |
| `profesorado` | `ForeignKey` | FK→Profesorado |  |  |  |  |
| `plan` | `ForeignKey` | FK→PlanEstudios | ✔ |  |  |  |
| `cohorte` | `PositiveSmallIntegerField` |  |  |  |  |  |
| `libreta` | `CharField` |  |  |  |  |  |
| `curso_introductorio` | `CharField` |  |  |  |  |  |
| `legajo_entregado` | `BooleanField` |  |  |  |  |  |
| `libreta_entregada` | `BooleanField` |  |  |  |  |  |
| `doc_dni_legalizado` | `BooleanField` |  |  |  |  |  |
| `doc_titulo_sec_legalizado` | `BooleanField` |  |  |  |  |  |
| `doc_cert_medico` | `BooleanField` |  |  |  |  |  |
| `doc_fotos_carnet` | `BooleanField` |  |  |  |  |  |
| `doc_folios_oficio` | `BooleanField` |  |  |  |  |  |
| `doc_titulo_terciario_legalizado` | `BooleanField` |  |  |  |  |  |
| `doc_incumbencias` | `BooleanField` |  |  |  |  |  |
| `nota_compromiso` | `BooleanField` |  |  |  |  |  |
| `adeuda_materias` | `BooleanField` |  |  |  |  |  |
| `adeuda_detalle` | `TextField` |  |  |  |  |  |
| `colegio` | `CharField` |  |  |  |  |  |
| `titulo_en_tramite` | `BooleanField` |  |  |  |  |  |
| `materias_adeudadas` | `TextField` |  |  |  |  |  |
| `institucion_origen` | `CharField` |  |  |  |  |  |
| `legajo_estado` | `CharField` |  |  |  |  |  |
| `condicion_admin` | `CharField` |  |  |  |  |  |
| `promedio_general` | `DecimalField` |  | ✔ |  |  |  |
| `legajo` | `CharField` |  |  |  |  |  |

## EspacioCurricular  
Tabla: `academia_core_espaciocurricular`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `correlativas_de` | `ForeignKey` | REL→Correlatividad | ✔ |  |  |  |
| `correlativas_requeridas` | `ForeignKey` | REL→Correlatividad | ✔ |  |  |  |
| `espaciocondicion` | `ForeignKey` | REL→EspacioCondicion | ✔ |  |  |  |
| `movimientos` | `ForeignKey` | REL→Movimiento | ✔ |  |  |  |
| `cursadas` | `ForeignKey` | REL→InscripcionEspacio | ✔ |  |  |  |
| `docentes` | `ManyToManyField` | M2M→Docente | ✔ |  |  | ✔ |
| `asignaciones_docentes` | `ForeignKey` | REL→DocenteEspacio | ✔ |  |  |  |
| `horarios` | `ForeignKey` | REL→Horario | ✔ |  |  |  |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `profesorado` | `ForeignKey` | FK→Profesorado |  |  |  |  |
| `plan` | `ForeignKey` | FK→PlanEstudios | ✔ |  |  |  |
| `anio` | `CharField` |  |  |  |  |  |
| `cuatrimestre` | `CharField` |  |  |  |  |  |
| `nombre` | `CharField` |  |  |  |  |  |
| `horas` | `PositiveIntegerField` |  |  |  |  |  |
| `formato` | `CharField` |  |  |  |  |  |
| `libre_habilitado` | `BooleanField` |  |  |  |  |  |

## Correlatividad  
Tabla: `academia_core_correlatividad`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `plan` | `ForeignKey` | FK→PlanEstudios |  |  |  |  |
| `espacio` | `ForeignKey` | FK→EspacioCurricular |  |  |  |  |
| `tipo` | `CharField` |  |  |  |  |  |
| `requisito` | `CharField` |  |  |  |  |  |
| `requiere_espacio` | `ForeignKey` | FK→EspacioCurricular | ✔ |  |  |  |
| `requiere_todos_hasta_anio` | `PositiveSmallIntegerField` |  | ✔ |  |  |  |
| `observaciones` | `CharField` |  |  |  |  |  |

## Condicion  
Tabla: `academia_core_condicion`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `espaciocondicion` | `ForeignKey` | REL→EspacioCondicion | ✔ |  |  |  |
| `movimientos` | `ForeignKey` | REL→Movimiento | ✔ |  |  |  |
| `codigo` | `CharField` |  |  | ✔ | ✔ |  |
| `nombre` | `CharField` |  |  |  |  |  |
| `tipo` | `CharField` |  |  |  |  |  |

## EspacioCondicion  
Tabla: `academia_core_espaciocondicion`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `espacio` | `ForeignKey` | FK→EspacioCurricular |  |  |  |  |
| `condicion` | `ForeignKey` | FK→Condicion |  |  |  |  |

## Movimiento  
Tabla: `academia_core_movimiento`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `inscripcion` | `ForeignKey` | FK→EstudianteProfesorado |  |  |  |  |
| `espacio` | `ForeignKey` | FK→EspacioCurricular |  |  |  |  |
| `tipo` | `CharField` |  |  |  |  |  |
| `fecha` | `DateField` |  | ✔ |  |  |  |
| `condicion` | `ForeignKey` | FK→Condicion | ✔ |  |  |  |
| `nota_num` | `DecimalField` |  | ✔ |  |  |  |
| `nota_texto` | `CharField` |  |  |  |  |  |
| `folio` | `CharField` |  |  |  |  |  |
| `libro` | `CharField` |  |  |  |  |  |
| `disposicion_interna` | `CharField` |  |  |  |  |  |
| `ausente` | `BooleanField` |  |  |  |  |  |
| `ausencia_justificada` | `BooleanField` |  |  |  |  |  |
| `creado` | `DateTimeField` |  |  |  |  |  |

## InscripcionEspacio  
Tabla: `academia_core_inscripcionespacio`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `estado_logs` | `ForeignKey` | REL→InscripcionEspacioEstadoLog | ✔ |  |  |  |
| `finales` | `ForeignKey` | REL→InscripcionFinal | ✔ |  |  |  |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `inscripcion` | `ForeignKey` | FK→EstudianteProfesorado |  |  |  |  |
| `espacio` | `ForeignKey` | FK→EspacioCurricular |  |  |  |  |
| `anio_academico` | `PositiveIntegerField` |  |  |  |  |  |
| `fecha_inscripcion` | `DateField` |  |  |  |  |  |
| `estado` | `CharField` |  |  |  |  |  |
| `fecha_baja` | `DateField` |  | ✔ |  |  |  |
| `motivo_baja` | `TextField` |  |  |  |  |  |
| `created_at` | `DateTimeField` |  |  |  |  |  |
| `updated_at` | `DateTimeField` |  |  |  |  |  |

## InscripcionEspacioEstadoLog  
Tabla: `academia_core_inscripcionespacioestadolog`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `insc_espacio` | `ForeignKey` | FK→InscripcionEspacio |  |  |  |  |
| `estado` | `CharField` |  |  |  |  |  |
| `fecha` | `DateTimeField` |  |  |  |  |  |
| `usuario` | `ForeignKey` | FK→User | ✔ |  |  |  |
| `nota` | `TextField` |  |  |  |  |  |

## Docente  
Tabla: `academia_core_docente`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `asignaciones` | `ForeignKey` | REL→DocenteEspacio | ✔ |  |  |  |
| `usuarios` | `ForeignKey` | REL→UserProfile | ✔ |  |  |  |
| `horarios` | `ForeignKey` | REL→Horario | ✔ |  |  |  |
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `dni` | `CharField` |  |  |  | ✔ |  |
| `apellido` | `CharField` |  |  |  |  |  |
| `nombre` | `CharField` |  |  |  |  |  |
| `email` | `CharField` |  |  |  |  |  |
| `activo` | `BooleanField` |  |  |  |  |  |
| `espacios` | `ManyToManyField` | M2M→EspacioCurricular |  |  |  | ✔ |

## DocenteEspacio  
Tabla: `academia_core_docenteespacio`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `docente` | `ForeignKey` | FK→Docente |  |  |  |  |
| `espacio` | `ForeignKey` | FK→EspacioCurricular |  |  |  |  |
| `desde` | `DateField` |  | ✔ |  |  |  |
| `hasta` | `DateField` |  | ✔ |  |  |  |

## UserProfile  
Tabla: `academia_core_userprofile`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `user` | `OneToOneField` | O2O→User |  |  | ✔ |  |
| `rol` | `CharField` |  |  |  |  |  |
| `estudiante` | `ForeignKey` | FK→Estudiante | ✔ |  |  |  |
| `docente` | `ForeignKey` | FK→Docente | ✔ |  |  |  |
| `profesorados_permitidos` | `ManyToManyField` | M2M→Profesorado |  |  |  | ✔ |

## Actividad  
Tabla: `academia_core_actividad`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `user` | `ForeignKey` | FK→User | ✔ |  |  |  |
| `rol_cache` | `CharField` |  |  |  |  |  |
| `accion` | `CharField` |  |  |  |  |  |
| `detalle` | `TextField` |  |  |  |  |  |
| `creado` | `DateTimeField` |  |  |  |  |  |

## InscripcionFinal  
Tabla: `academia_core_inscripcionfinal`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `inscripcion_cursada` | `ForeignKey` | FK→InscripcionEspacio |  |  |  |  |
| `fecha_examen` | `DateField` |  |  |  |  |  |
| `creado` | `DateTimeField` |  |  |  |  |  |
| `estado` | `CharField` |  |  |  |  |  |
| `nota_final` | `PositiveSmallIntegerField` |  | ✔ |  |  |  |
| `ausente` | `BooleanField` |  |  |  |  |  |
| `ausencia_justificada` | `BooleanField` |  |  |  |  |  |

## Horario  
Tabla: `academia_core_horario`

| Campo | Tipo | Relación | Null | PK | Unique | M2M |
|------:|:-----|:--------:|:----:|:--:|:------:|:---:|
| `id` | `BigAutoField` |  |  | ✔ | ✔ |  |
| `espacio` | `ForeignKey` | FK→EspacioCurricular |  |  |  |  |
| `dia_semana` | `IntegerField` |  |  |  |  |  |
| `hora_inicio` | `TimeField` |  |  |  |  |  |
| `hora_fin` | `TimeField` |  |  |  |  |  |
| `docente` | `ForeignKey` | FK→Docente | ✔ |  |  |  |
