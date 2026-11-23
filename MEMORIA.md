# Optimización y Heurística en el Diseño de Horarios Universitarios: Planificación Integrada de la Escuela de Ingeniería Informática (EII – ULPGC)

**Asignatura:** Optimización y Heurística (OH)  
**Titulación:** Grado en Ciencia e Ingeniería de Datos (GCID)  
**Centro:** Escuela de Ingeniería Informática (EII), Universidad de Las Palmas de Gran Canaria (ULPGC)  
**Curso Académico:** 2026–2027  
**Propuesta:** D1 — *Diseño de horarios para la Escuela de Ingeniería Informática (EII)*  
**Autores:** María Naranjo Peñate · Inés Torres Sánchez · Yone Suárez Viera 

---

## 1. Título del Proyecto y Autores

* **Título:** Optimización y Heurística en el Diseño de Horarios Universitarios: Planificación Integrada de la Escuela de Ingeniería Informática (EII – ULPGC) mediante Programación con Restricciones y Metaheurísticas.
* **Equipo de autores y reparto de responsabilidades:**
  * **Inés Torres Sánchez:** Arquitectura inicial del repositorio y modelo base (`modelo_base.py`, `restricciones.py`, `visualizador.py`), formulación matemática común y desarrollo integral del **Grado en Ciencia e Ingeniería de Datos (`GCID/`)** (CP-SAT global por cuatrimestre + Recocido Simulado propio de 60.000 iteraciones).
  * **Yone Suárez Viera:** Desarrollo integral del **Grado en Ingeniería Informática (`GII/`)** (4 cursos completos, turnos de mañana y tarde, jerarquía de subgrupos, CP-SAT + Recocido Simulado propio desde cero + suite de benchmark multi-semilla con línea base aleatoria), **integración modular de las tres ramas** y construcción del **Cuadro de Mandos Interactivo unificado en Streamlit** (`app.py`, `live_runner.py`).
  * **María Naranjo Peñate:** Desarrollo integral del **Grado en Ingeniería Física y Matemática (`GIFM/`)** (desglose automático de asignaturas en bloques semanales, modelado de semanas activas, jornada ampliada excepcional y pipeline híbrido CP-SAT → Recocido Simulado).

---

## 2. Resumen del Proyecto

El diseño de horarios universitarios (*University Course Timetabling Problem*, UCTP) es un problema clásico de optimización combinatoria NP-hard. Este proyecto resuelve de forma automática, rigurosa y reproducible la planificación semanal de los **tres grados oficiales** de la Escuela de Ingeniería Informática (EII) de la ULPGC para el curso académico **2026–2027**: el Grado en Ingeniería Informática (**GII**), el Grado en Ciencia e Ingeniería de Datos (**GCID**) y el Grado en Ingeniería Física y Matemática (**GIFM**). En conjunto se modelan **12 cursos completos** (24 calendarios semestrales), **598 sesiones docentes en catálogo** (**645 bloques horarios** tras el desglose semanal de GIFM), **1.127 horas lectivas** y **27 espacios físicos** entre aulas de teoría y laboratorios especializados.

Partiendo de una formulación matemática común (variables de inicio, duración y asignación de aula con restricciones duras de no solapamiento docente, alumnado, capacidad y continuidad diaria, y restricciones blandas de compactación, descarga del viernes y estabilidad espacial), se implementan y comparan dos paradigmas principales: un **método exacto de Programación con Restricciones** mediante **Google OR-Tools (CP-SAT)** y **tres implementaciones propias desde cero en Python puro de Recocido Simulado (*Simulated Annealing*, SA)**, validadas frente a una línea base de Búsqueda Aleatoria.

Mientras el muestreo aleatorio fracasa sistemáticamente (**0 % de factibilidad**), tanto CP-SAT como el Recocido Simulado alcanzan un **100 % de soluciones factibles** dentro de cada titulación en tiempos de pocos segundos, reduciendo drásticamente los huecos del alumnado (hasta un 100 % en 1º GII y 0 huecos en todo GCID) y concentrando menos de un 1 % de bloques en las últimas horas del viernes. Finalmente, toda la solución se unifica en un **cuadro de mandos interactivo en Streamlit** que visualiza horarios por curso, grupo, profesor y aula, contrasta directamente con los PDFs oficiales de la EII y permite ejecutar optimizaciones en vivo.

---

## 3. Introducción y Motivación

La elaboración manual de los horarios académicos en una escuela politécnica como la EII de la ULPGC es un proceso operativo de altísima complejidad. En un mismo edificio (Edificio de Informática y Matemáticas del Campus de Tafira) conviven tres titulaciones con estructuras docentes muy heterogéneas:

1. **Grado en Ingeniería Informática (GII):** 4 cursos y 2 semestres, con alta matriculación en 1º y 2º que exige desdobles en **Turno de Mañana** (Grupos 1 y 2, 08:30–14:30) y **Turno de Tarde** (Grupo 3, 14:30–20:30), tres modalidades jerárquicas (teoría, prácticas de aula y laboratorios con hasta 5 subgrupos paralelos) y uso del Laboratorio de Física (`LF-4`).
2. **Grado en Ciencia e Ingeniería de Datos (GCID):** 4 cursos en turno de mañana que comparten aulas entre cursos del mismo cuatrimestre, exigen **compactación estricta sin horas libres** para todos los subgrupos (`41–44`), reparto equilibrado en 1º curso y **liberación completa de jueves y viernes en 3º (2º semestre)** para prácticas externas en empresa.
3. **Grado en Ingeniería Física y Matemática (GIFM):** 4 cursos caracterizados por sesiones teóricas largas (4–6 h semanales) que deben dividirse en bloques equilibrados, docencia con **semanas activas parciales** (p. ej. semanas 1–8 o 9–15) y alta densidad horaria en 3º (2º cuatrimestre), que requiere activar una **ampliación excepcional de jornada (08:30–16:30)**.

Cuando esta planificación se aborda de forma manual mediante hojas de cálculo, requiere semanas de ajustes iterativos y suele dejar horas muertas (huecos) en la jornada del alumnado o cargas elevadas en las últimas franjas del viernes. Aplicar técnicas formales de **Programación con Restricciones (CP-SAT)** y **Metaheurísticas (Recocido Simulado)** permite automatizar el proceso, garantizar la ausencia total de conflictos legales y optimizar de forma cuantificable la calidad de vida académica de estudiantes y profesorado.

---

## 4. Descripción del Problema y Estado del Arte

### 4.1. Taxonomía del Problema (UCTP)
El problema abordado pertenece a la clase del *Curriculum-Based Course Timetabling Problem* (CB-CTT), una de las formulaciones estándar de las competiciones internacionales *International Timetabling Competitions* (**ITC 2002**, **ITC 2007 — Track 3** e **ITC 2019**).

Desde el punto de vista de la complejidad computacional, el UCTP es **NP-hard en sentido fuerte**, ya que generaliza el problema clásico de coloreado de grafos (*Graph Coloring Problem*), donde cada sesión es un vértice, cada recurso compartido (profesor, subgrupo de estudiantes o aula) induce una arista de conflicto y las franjas horarias corresponden a los colores. Para $|S|$ sesiones, $|T|$ franjas horarias y $|R|$ aulas, la cardinalidad teórica del espacio de búsqueda crece exponencialmente:

$$|\Omega| = (|T| \times |R|)^{|S|}$$

Incluso para una única instancia mediana como 2º GII (1er semestre, Grupo 1: $|S|=31$, $|T|=30$, $|R|=27$), el espacio de estados supera los $810^{31} \approx 1{,}83 \times 10^{90}$ estados posibles; en el problema global de 1er cuatrimestre de GCID ($|S|=86$, $|T|=30$, $|R|=26$) supera los $780^{86} \approx 5{,}3 \times 10^{248}$ estados.

### 4.2. Estado del Arte en la Literatura
La literatura científica distingue dos grandes familias de métodos para UCTP:
* **Métodos Exactos (MILP y Programación con Restricciones):** Burke, Kingston y de Werra (2004) y Bettinelli, Cordeau y Malucelli (2015) revisan formulaciones exactas mediante Programación Lineal Entera Mixta y *Branch-and-Cut-and-Price*. En los últimos años, los solvers modernos de Programación con Restricciones basados en cláusulas SAT (*Lazy Clause Generation* / CDCL), como **Google OR-Tools CP-SAT** (Perron y Furnon, 2024), han demostrado una gran eficacia en problemas con restricciones globales de no solapamiento (`AddNoOverlap`) e intervalos opcionales (`NewOptionalIntervalVar`).
* **Metaheurísticas de Trayectoria y Población:** Schaerf (1999) y Lewis (2008) sintetizan la superioridad práctica de las metaheurísticas de búsqueda local —especialmente **Recocido Simulado** (*Simulated Annealing*, Kirkpatrick et al., 1983), **Búsqueda Tabú** y *Variable Neighborhood Search*— para optimizar funciones objetivo no lineales con múltiples penalizaciones blandas (como los huecos diarios por subgrupo). Kostuch (2005) demostró en los benchmarks oficiales de la ITC que el Recocido Simulado con operadores de reubicación e intercambio (*relocate* y *swap*) ofrece un equilibrio excelente entre calidad de solución y tiempo de cómputo.

---

## 5. Formulación Matemática

El problema se clasifica como un problema de optimización **combinatorio, discreto, no convexo, altamente restringido y determinista**.

### 5.1. Conjuntos e Índices Comunes
* $S = \{1, \dots, N_S\}$: conjunto de sesiones o bloques horarios a planificar, con duración $d_s \in \mathbb{Z}^+$ horas y aforo requerido $a_s$.
* $T = \{0, \dots, H \cdot 5 - 1\}$: horizonte temporal semanal de 5 días por $H$ franjas diarias ($H=6$ en jornada ordinaria 08:30–14:30 o tarde 14:30–20:30; $H=8$ en la ampliación excepcional 08:30–16:30 de 3º GIFM C2).
* $R = \{1, \dots, N_R\}$: conjunto de espacios físicos de la EII ($N_R = 27$), cada uno con tipología $\tau_r \in \{\text{Teoría}, \text{Laboratorio}\}$ y capacidad $C_r$.
* $P$: conjunto de docentes; $S(p) \subseteq S$ son las sesiones impartidas por el profesor $p$.
* $G_{\text{atóm}}$: conjunto de subgrupos atómicos disjuntos de alumnado (p. ej., $\{41, 42, 43, 44\}$); $S(g) \subseteq S$ son todas las sesiones (teoría, prácticas de aula y laboratorios) a las que asiste el subgrupo $g$.

### 5.2. Variables de Decisión
En la formulación matemática unificada, la asignación espacio-temporal puede representarse mediante variables binarias tri-indexadas $X_{s, t, r} \in \{0, 1\}$ (igual a 1 si la sesión $s$ inicia en la franja $t$ dentro del aula $r$) o, de forma equivalente y más compacta en CP-SAT, mediante:
* $t_s \in \{0, \dots, |T| - d_s\}$: franja de inicio entera de la sesión $s$, con fin $e_s = t_s + d_s$ e intervalo $I_s = [t_s, e_s)$.
* $y_{s, r} \in \{0, 1\}$: variable booleana que vale 1 si la sesión $s$ se imparte en el aula $r$ (asociada a un intervalo opcional $I_{s, r}^{\text{opt}}$).

### 5.3. Restricciones Duras Comunes (*Hard Constraints*)
1. **Unicidad de asignación y compatibilidad de aula:** cada sesión $s \in S$ se asigna exactamente a un aula compatible en tipo y capacidad ($C_r \ge a_s$):
   $$\sum_{r \in R_{\text{comp}}(s)} y_{s, r} = 1 \quad \forall s \in S, \qquad y_{s, r} = 0 \quad \forall r \notin R_{\text{comp}}(s)$$
2. **Continuidad intradiaria (no partir sesiones entre días):**
   $$\left\lfloor \frac{t_s}{H} \right\rfloor = \left\lfloor \frac{t_s + d_s - 1}{H} \right\rfloor \quad \forall s \in S$$
3. **No solapamiento de profesorado:** ningún docente puede impartir dos sesiones a la vez:
   $$\text{NoOverlap}\big(\{I_s \mid s \in S(p)\}\big) \quad \forall p \in P$$
4. **Jerarquía y no colisión de alumnado:** dos sesiones que compartan algún subgrupo atómico $g \in G_{\text{atóm}}$ no pueden coincidir (una sesión de teoría de grupo completo bloquea automáticamente a todos sus subgrupos de aula y laboratorio):
   $$\text{NoOverlap}\big(\{I_s \mid s \in S(g)\}\big) \quad \forall g \in G_{\text{atóm}}$$
5. **Exclusividad física de aula:** dos sesiones no pueden ocupar el mismo aula a la misma hora (teniendo en cuenta semanas activas compatibles en GIFM):
   $$\text{NoOverlap}\big(\{I_{s, r}^{\text{opt}} \mid s \in S\}\big) \quad \forall r \in R$$

### 5.4. Restricciones Blandas y Extensiones Específicas por Titulación
La función de coste global combina penalizaciones de restricciones duras (en el caso de la metaheurística, con peso dominante $W_{\text{duras}} \gg w_{\text{blandas}}$) y criterios de calidad pedagógica:

$$\min \; \Phi(X) = W_{\text{duras}} \cdot N_{\text{duras}}(X) + w_{\text{huecos}} \cdot C_{\text{huecos}}(X) + w_{\text{viernes}} \cdot C_{\text{viernes}}(X) + w_{\text{aula}} \cdot C_{\text{aula}}(X)$$

| Dimensión del modelo | GII | GCID | GIFM |
| :--- | :--- | :--- | :--- |
| **Ámbito de acoplamiento** | Por curso, semestre y turno (Mañana G1+G2 juntos; Tarde G3 aparte) | Global por cuatrimestre (4 cursos simultáneos compartiendo aulas) | Por curso y cuatrimestre con división previa en bloques |
| **Huecos / ventanas diarias** | Restricción blanda penalizada ($w_{\text{hueco}}=15$ en SA; minimización en CP-SAT) | **Restricción dura obligatoria** ($0$ huecos para todos los subgrupos `41–44`) | Compactación intradiaria y equilibrio de bloques semanales |
| **Viernes última hora** | Penalizado en CP-SAT y SA ($w_{\text{viernes}}=10$) | Penalizado ($+10$ pts en franjas `12:30–14:30`) | Penalizado en franjas finales del viernes |
| **Aula de referencia** | Dinámica por capacidad (sin aula fija forzada) | Preferencia blanda aula `A2-5` para teoría (`+25` pts) | Preferencia blanda aula `A3-1` para teoría |
| **Reglas propias de la titulación** | Turno tarde (14:30–20:30) para G3 en 1º; jerarquía G17–G22; `LF-4` | Teorías de 1º en días distintos; máx. 4 h/día en 1º; **J–V libres en 3º S2** (prácticas externas) | Semanas activas parciales (`1-8`, `9-15`, etc.); **jornada ampliable 08:30–16:30 en 3º C2** |

---

## 6. Métodos de Optimización Desarrollados

### 6.1. Línea Base: Búsqueda Aleatoria (*Random Search*)
Para cuantificar objetivamente la dificultad del espacio de búsqueda, en `GII/src/evaluador_benchmark.py` se implementó una línea base estocástica uniforme ($N = 5.000$ muestreos válidos en dominio de turnos y aulas compatibles por instancia), conservando la solución de menor energía encontrada.

### 6.2. Método Exacto: Google OR-Tools CP-SAT
En las tres titulaciones (`GII/src/modelo_base.py`, `GCID/src/modelo_base.py` y `GIFM/src/modelo_base.py`), el modelo se formula con variables enteras de inicio, intervalos continuos (`NewIntervalVar`), intervalos opcionales por aula (`NewOptionalIntervalVar`) y restricciones globales `AddNoOverlap` y `AddDivisionEquality`. El solver CP-SAT combina propagación de dominios, búsqueda por ramificación y aprendizaje de cláusulas por conflicto (CDCL), encontrando soluciones factibles u óptimas en pocos segundos.

### 6.3. Metaheurística Propia: Recocido Simulado (*Simulated Annealing* en Python Puro)
Cumpliendo el requisito central de la asignatura, el núcleo metaheurístico fue programado **íntegramente desde cero en Python puro**, adoptando tres configuraciones adaptadas a la estructura de cada grado:

```text
Algoritmo 1: Recocido Simulado Unificado para Timetabling (UCTP)
Entrada: Sesiones S, Aulas R, T_inicial, T_final, alpha, iter_max
Salida: Mejor asignación X*, energía E* e historial de convergencia

1:  X <- GenerarSolucionInicial(S, R)   // Aleatoria en GII/GCID; solución CP-SAT en GIFM
2:  E <- EvaluarEnergia(X)              // W_duras * N_duras + coste_blando
3:  X* <- X ;  E* <- E ;  T <- T_inicial
4:  Mientras no se alcance criterio de parada (T <= T_final o iter >= iter_max):
5:      X_vec <- GenerarVecino(X)       // Relocate temporal, cambio de aula o Swap
6:      E_vec <- EvaluarEnergia(X_vec)
7:      Delta <- E_vec - E
8:      Si Delta <= 0 o Uniforme(0,1) < exp(-Delta / T) entonces:
9:          X <- X_vec ;  E <- E_vec
10:         Si E < E* entonces:
11:             X* <- X ;  E* <- E
12:     Actualizar T <- alpha * T       // Enfriamiento geométrico
13: Retornar X*, E*
```

* **GII (`GII/src/metaheuristica_sa.py`):** Parte de solución aleatoria; operadores *Relocate* (70 %) y *Swap* entre sesiones compatibles (30 %); $T_0=120$, $T_f=0{,}01$, $\alpha=0{,}985$, $L=140$–$150$ iteraciones por temperatura ($\approx 24.300$ evaluaciones), con estructuras precomputadas $O(1)$ que alcanzan $>13.000$ estados/s en Python puro.
* **GCID (`GCID/src/metaheuristica.py`):** Resuelve los **4 cursos completos del cuatrimestre de forma simultánea** desde inicialización aleatoria; tres movimientos de vecindario (45 % reubicación temporal, 35 % cambio de aula compatible, 20 % intercambio de franjas entre sesiones); $60.000$ iteraciones con $T_0=5.000 \to T_f=0{,}1$ y penalizaciones escalonadas ($10.000$ por choque duro, $2.000$ por hora de hueco, $10$/$25$ por preferencias blandas).
* **GIFM (`GIFM/src/metaheuristica/`):** Arquitectura modular (`evaluacion.py`, `movimientos.py`, `recocido_simulado.py`) con **enfoque híbrido (CP-SAT → SA)**: parte de la solución factible obtenida por CP-SAT y explora $1.000$ movimientos vecinos factibles ($T_0=10$, $T_f=0{,}01$, $\alpha=0{,}995$) validando y refinando la calidad del horario.

---

## 7. Implementación, Evolución del Código y Dificultades Encontradas

### 7.1. Arquitectura Modular Integrada
Cada titulación trabaja en una carpeta independiente con cálculo dinámico de rutas (`Path(__file__).resolve().parent.parent` u `os.path.dirname(os.path.abspath(__file__))`), integradas bajo una raíz común en Git:

```text
ProyectoOH/
├── app.py                         # Cuadro de mandos interactivo en Streamlit (6 vistas)
├── live_runner.py                 # Ejecutor aislado en subproceso para el Simulador en Vivo
├── generar_activos_integracion.py # Generador reproducible de caché unificada y horarios SA GII
├── dashboard_data/                # Caché unificada de 1.290 bloques resueltos (CP-SAT y SA)
├── MEMORIA.md / README.md         # Documentación académica y técnica unificada
├── GII/                           # Ingeniería Informática (datos, src, horarios CP-SAT/SA, PDF, memoria)
├── GCID/                          # Ciencia e Ingeniería de Datos (datos, src, horarios CP-SAT/SA, PDF, gráficas)
└── GIFM/                          # Ingeniería Física y Matemática (datos, src, resultados CP-SAT/SA, PDF)
```

### 7.2. Evolución Iterativa del Desarrollo y Resolución de Incidencias Reales
El proyecto evolucionó mediante control de versiones en Git (ramas `main`, `GCID`, `GII`, `GIFM` e `integracion`), resolviendo progresivamente problemas reales de ingeniería y modelado:

1. **Del prototipo sin restricciones a la modularización (`modelo_base.py` → `restricciones.py`):** La primera versión creaba las variables `start_vars`, `end_vars` e `interval_vars` sobre 30 slots sin ninguna restricción de solape (colocando todas las clases a la misma hora) para validar la lectura de `datos/clases.csv` y el solver CP-SAT. A continuación se separó la lógica de restricciones duras y blandas en `src/restricciones.py`.
2. **Desorden en consola, filtrado de capacidad de aulas y error de volcado del diccionario:** Inicialmente la salida aparecía ordenada por `id_sesion` (desordenando días de la semana), lo que se corrigió ordenando por `Slot` (`0..29`). A continuación se añadió el filtrado de `aulas_compatibles` exigiendo simultáneamente coincidencia de tipología y aforo suficiente (`capacidad >= num_alumnos`), junto con la columna `semestre` en `clases.csv` para soportar ambos cuatrimestres. Al incorporar las variables booleanas de aula (`aula_assign`), un error en `asignaciones.append` volcó el diccionario completo en lugar del aula elegida, y un fallo posterior de iteración provocó salidas repetidas con `"Sin aula"`. Se resolvió consultando específicamente `solver.Value(aula_asignada[(s_id, a_id)]) == 1`, eliminando una llamada duplicada en `modelo_base.py` y separando la salida gráfica en `visualizador.py`.
3. **Escalado a los desdobles y jerarquía de subgrupos de GII:** Al pasar de GCID (2–4 subgrupos) a GII (hasta 5 subgrupos `41–45` en 3º y 3 grupos completos `G1, G2, G3` en 1º con prácticas de aula `G17–G22`), el tratamiento plano de cadenas de grupo provocaba solapes entre teoría, prácticas de aula y laboratorios. Se implementó un mapeo jerárquico de subgrupos atómicos (`obtener_subgrupos_estudiantes`), se pasó a asignación dinámica de aulas por capacidad sin imponer aula fija (`aula_preferida=None` en GII) y se incorporó el parámetro `es_tarde` para aislar el turno vespertino (14:30–20:30).
4. **Infactibilidad por ausencia del Laboratorio de Física (`LF-4`):** Al incorporar el 2º semestre de 1º GII (*Fundamentos Físicos de la Informática*), CP-SAT devolvió `INFEASIBLE`. La inspección reveló que faltaba el laboratorio especializado `LF-4` en `datos/aulas.csv`; tras añadirlo, el modelo convergió de inmediato.
5. **Renderizado de desdobles simultáneos en `visualizador.py`:** Cuando varios subgrupos coincidían a la misma hora en distintos laboratorios, la primera versión de Matplotlib superponía los bloques. Se implementó un algoritmo de asignación dinámica de carriles (*lane allocation*), adaptando además en GCID el número de carriles por curso (4 carriles en 1º–2º, 2 en 3º y ancho completo en 4º).
6. **Semanas activas y saturación horaria en GIFM:** En GIFM fue necesario dividir sesiones de 4–6 h en bloques semanales (`dividir_en_bloques`), modelar compatibilidad temporal por semanas activas (`semanas_activas`) y habilitar la ampliación automática de jornada a 8 horas (08:30–16:30) exclusivamente para 3º GIFM (2º cuatrimestre), donde la jornada ordinaria de 6 horas resultaba infactible.
7. **Integración de las 3 ramas y colisiones de `sys.modules` en el Simulador en Vivo:** Como `GII/src/`, `GCID/src/` y `GIFM/src/` definen módulos con el mismo nombre (`modelo_base.py`, `restricciones.py`, `visualizador.py`), importarlos en el mismo proceso de Python provocaba colisiones. Se diseñó `live_runner.py` para ejecutar cada optimizador en un **subproceso aislado** escribiendo resultados en un directorio temporal sin alterar los ficheros del repositorio. Asimismo, se unificó la experiencia visual de las tres carreras en una cuadrícula HTML interactiva con paleta oficial EII homogénea (resolviendo la divergencia de colores del visualizador original de GIFM sin modificar el código de su autora).

---

## 8. Datos Utilizados (Origen, Descripción y Licencia)

* **Origen y licencia:** Todos los datos son **100 % reales**, extraídos directamente de los **horarios oficiales públicos del curso académico 2026–2027** publicados por la **Escuela de Ingeniería Informática de la Universidad de Las Palmas de Gran Canaria (EII – ULPGC)** en su portal institucional (`eii.ulpgc.es`), utilizados con finalidad estrictamente académica y docente. Los tres documentos oficiales fuente se incluyen en el repositorio para trazabilidad y contraste directo:
  * `GII/horario_GII_2026_2027.pdf`
  * `GCID/horario_GCID_2026_2027.pdf` *(V6 – 28/10/2026)*
  * `GIFM/horario_GIFM_2026_2027.pdf` *(V5 – 23/09/2026)*
* **Preprocesado y estructura tabular:** Las tablas PDF oficiales se estructuraron y normalizaron en archivos CSV por titulación (`clases.csv` / `clases_gcid.csv` y `aulas.csv`), limpiando espacios en columnas, validando aforos por grupo y separando bloques horarios en GIFM (`GIFM/src/unificar_clases.py`).

| Titulación | Fichero de datos | Cursos / Cuatris | Sesiones CSV | Bloques horario | Horas/Sem | Asignaturas | Docentes | Aulas catálogo |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GII** | `GII/datos/clases.csv` | 1º–4º (S1 y S2) | 364 | 364 | 625 h | 39 | 30 | 27 |
| **GCID** | `GCID/datos/clases_gcid.csv` | 1º–4º (S1 y S2) | 150 | 150 | 260 h | 38 | 42 | 26 |
| **GIFM** | `GIFM/datos/clases.csv` | 1º–4º (S1 y S2) | 84 | 131 | 242 h | 46 | 41 | 27 |
| **Total EII** | **Unificado en `dashboard_data/`** | **12 cursos (24 cal.)** | **598** | **645** | **1.127 h** | **123** | **104 únicos** | **27 espacios** |

---

## 9. Experimentación y Resultados

### 9.1. GII — Benchmark Multi-Semilla (Baseline vs. CP-SAT vs. Recocido Simulado)
Se evaluaron tres instancias representativas de GII ejecutando la Búsqueda Aleatoria ($N=5.000$), OR-Tools CP-SAT y el Recocido Simulado propio sobre **5 semillas estadísticas independientes** (`semillas = [1, 2, 3, 4, 5]`, datos en `GII/memoria/benchmark_resultados.csv`):

| Instancia | Método | Sesiones | Tiempo Medio (s) | Desv. Tiempo | Energía Media | Desv. Energía | Violaciones Duras | Coste Huecos | Factibilidad |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1º GII – S1** | Búsqueda Aleatoria | 24 | 0.69 s | — | 12.400,00 | — | 6,00 | 400,00 | **0,0 %** |
| **1º GII – S1** | OR-Tools CP-SAT | 24 | 1.57 s | — | 190,00 | — | 0,00 | 190,00 | **100,0 %** |
| **1º GII – S1** | **Recocido Simulado (Propio)** | 24 | 5.11 s | ±0.48 s | **0,00** | ±0,00 | **0,00** | **0,00** | **100,0 %** |
| **2º GII – S1** | Búsqueda Aleatoria | 31 | 0.93 s | — | 28.415,00 | — | 14,00 | 415,00 | **0,0 %** |
| **2º GII – S1** | OR-Tools CP-SAT | 31 | 1.37 s | — | 270,00 | — | 0,00 | 270,00 | **100,0 %** |
| **2º GII – S1** | **Recocido Simulado (Propio)** | 31 | 2.15 s | ±0.28 s | **58,00** | ±38,34 | **0,00** | **58,00** | **100,0 %** |
| **3º GII – S1** | Búsqueda Aleatoria | 30 | 0.94 s | — | 32.670,00 | — | 16,00 | 670,00 | **0,0 %** |
| **3º GII – S1** | OR-Tools CP-SAT | 30 | 1.40 s | — | 140,00 | — | 0,00 | 140,00 | **100,0 %** |
| **3º GII – S1** | **Recocido Simulado (Propio)** | 30 | 2.76 s | ±0.75 s | **61,00** | ±22,75 | **0,00** | **61,00** | **100,0 %** |

* **Interpretación:** La búsqueda ciega no alcanza una sola solución legal ($0\%$ factibilidad). CP-SAT resuelve las restricciones en menos de $1{,}6\text{ s}$, mientras que el Recocido Simulado propio logra el **100 % de factibilidad en todas las semillas** y reduce el coste de huecos entre un **56 % y un 100 %** respecto a CP-SAT (reduciendo además las sesiones en viernes de 52 a solo 16 en todo el grado). En la curva de convergencia (`GII/memoria/curva_convergencia_sa.png`, 2 paneles: energía arriba, temperatura y tasa de aceptación abajo), se observa la caída abrupta a 0 conflictos duros antes de la iteración 2.000 y el refinamiento progresivo posterior hasta la estabilización.

### 9.2. GCID — Optimización Global por Cuatrimestre (4 Cursos Simultáneos)
Resultados comparativos documentados en `GCID/README.md` y reproducidos en la caché unificada (`GCID/graficas/convergencia_SA_1er.png` y `convergencia_SA_2do.png`):

| Métrica | CP-SAT (1er Sem.) | Recocido Simulado (1er Sem.) | CP-SAT (2º Sem.) | Recocido Simulado (2º Sem.) |
| :--- | :---: | :---: | :---: | :---: |
| **Sesiones planificadas (4 cursos)** | 86 | 86 | 64 | 64 |
| **Choques duros** | **0** | **0** | **0** | **0** |
| **Horas libres (huecos)** | **0** | **0** | **0** | **0** |
| **Penalización blanda** | **85** *(óptimo)* | 160 | **25** *(óptimo)* | 150 |
| **Tiempo de ejecución** | `10,78 s` | `11,08 s` | `4,77 s` | `9,45 s` |

* **Interpretación:** Al incluir la ausencia total de huecos como restricción dura en CP-SAT (y con penalización $2.000$ en SA), **ambos métodos logran 0 conflictos y 0 huecos en los 4 cursos**. En esta formulación global altamente acoplada, CP-SAT encuentra el óptimo exacto de preferencias blandas (aula `A2-5` y viernes) ligeramente más rápido y con menor penalización que el SA de 60.000 iteraciones.

### 9.3. GIFM — Pipeline Híbrido CP-SAT → Recocido Simulado (8 Instancias)
Resultados agregados directamente de los 8 ficheros `GIFM/resultados/estadisticas_recocido_*.csv`:

| Instancia | Bloques | Coste Inicial (CP-SAT) | Mejor Coste (SA) | Aceptados / 1.000 | Tiempo SA (s) | Horario Válido |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1º GIFM – C1** | 11 | 0 | **0** | 862 | 5,62 s | ✅ Sí |
| **1º GIFM – C2** | 11 | 0 | **0** | 844 | 5,68 s | ✅ Sí |
| **2º GIFM – C1** | 12 | 0 | **0** | 808 | 7,06 s | ✅ Sí |
| **2º GIFM – C2** | 20 | 0 | **0** | 799 | 15,05 s | ✅ Sí |
| **3º GIFM – C1** | 19 | 0 | **0** | 877 | 7,39 s | ✅ Sí |
| **3º GIFM – C2** *(jornada 08:30–16:30)* | 31 | 10 | **10** | 959 | 30,25 s | ✅ Sí |
| **4º GIFM – C1** | 19 | 0 | **0** | 928 | 5,84 s | ✅ Sí |
| **4º GIFM – C2** | 8 | 0 | **0** | 955 | 2,26 s | ✅ Sí |

* **Interpretación:** Los 8 horarios alcanzan el **100 % de validez**. En 7 de las 8 instancias, CP-SAT encuentra directamente el coste blando `0` (concentrando la teoría en `A3-1` y evitando viernes a última hora), y el Recocido Simulado confirma la optimalidad explorando entre 799 y 959 vecinos válidos por instancia sin degradar la solución.

### 9.4. Contraste Directo con los Horarios Oficiales Publicados de la EII (2026–2027)
El cuadro de mandos (`app.py`) permite contrastar visualmente los **24 calendarios optimizados** frente a las páginas recortadas de los **3 PDFs oficiales**. A nivel cuantitativo se observan mejoras claras en calidad horaria:
* **1º GCID (1er Semestre):** En el PDF oficial de la EII (`V6`), el subgrupo `43` presenta **1 hora de hueco** el miércoles (`11:30–12:30` entre prácticas y `MD`) y el subgrupo `44` acumula **2 horas de hueco** el viernes (`10:30–12:30`) terminando además con laboratorio de `IC1` a última hora del viernes (`12:30–14:30`). Nuestras soluciones (tanto CP-SAT como SA) eliminan el **100 % de los huecos** (0 horas libres para todos los subgrupos `41–44`) y descargan completamente la franja final del viernes.
* **1º GII (1er Semestre, Grupo 1):** El Recocido Simulado propio alcanza **0 huecos** y deja el **viernes completamente libre** de docencia presencial, frente a jornadas oficiales con prácticas repartidas hasta el viernes.
* **Carga global de viernes en toda la Escuela:** Sobre los 645 bloques semanales de las 3 titulaciones, únicamente **3 bloques en CP-SAT** y **4 en SA** (`< 0,7 %`) recaen en las últimas franjas del viernes.

### 9.5. Visualización Unificada e Interactividad Avanzada (Propuesta D1 + "Para ir más allá")
El cuadro de mandos en **Streamlit** (`python -m streamlit run app.py`, con **Modo Presentación** para proyector) cubre íntegramente los requisitos de D1 e incorpora extensiones interactivas de alto valor demostrativo:
1. **Por Curso, Grupo y Subgrupo de Estudiante:** Cuadrícula interactiva unificada con paleta EII, comparativa directa CP-SAT vs. SA, **Modo Mi Horario de Estudiante** (filtro por subgrupo o matrícula mixta multi-curso con cálculo de huecos y exportación a Google Calendar `.ics`), **Editor Manual (Reto vs. Algoritmo)** con validación de restricciones en tiempo real y contraste frente a los 3 PDFs oficiales de la EII.
2. **Por Profesor y por Aula:** Vistas semanales individuales de cualquier docente (exportables a `.ics`) o aula física (`A1-1` a `LF-4`), **mapa de calor interactivo de saturación de espacios** y auditoría de acoplamiento inter-titulación.
3. **Laboratorio en Vivo (What-If, Replay SA y Carrera):** Permite simular **reoptimización ante incidencias** (cierre de aulas por obras, bloqueo de día de un profesor y ajuste de pesos de la función objetivo), visualizar un **Replay paso a paso del Recocido Simulado** desde el caos térmico inicial hasta el óptimo, y lanzar una **carrera en directo** (Búsqueda Aleatoria vs. CP-SAT vs. SA).

---

## 10. Discusión y Limitaciones

1. **Complementariedad entre CP-SAT y Recocido Simulado:**
   * **CP-SAT** destaca cuando las restricciones se expresan de forma lineal/lógica y el objetivo es sencillo o globalmente acoplado (como en GCID, donde alcanza el óptimo global exacto en $<11\text{ s}$, o en GIFM, donde sirve de generador inicial instantáneo).
   * **Recocido Simulado (propio)** brilla cuando la función objetivo incorpora métricas no lineales de compactación diaria (huecos por subgrupo en GII, donde reduce el coste entre un 56 % y un 100 % frente a CP-SAT) y ofrece además gran flexibilidad para incorporar penalizaciones arbitrarias sin explotar el número de variables auxiliares.
2. **Limitación principal — Acoplamiento Inter-Titulación (Auditoría Real):**
   * Al haberse resuelto cada grado en su propio módulo independiente (`GII/`, `GCID/`, `GIFM/`), cada titulación garantiza **0 conflictos internos**, pero **no se acoplan globalmente los recursos físicos ni el profesorado compartido entre titulaciones distintas**.
   * Nuestra auditoría automática integrada en `app.py` cuantifica exactamente este efecto: existen **7 docentes compartidos** en el 1er cuatrimestre (p. ej., *Carmelo Rubén García Rodríguez*, *Cayetano Guerra Artal*, *Javier Sánchez Pérez*, *José Carlos Ruiz Luque*, *José Juan Hernández Cabrera*) y **2 docentes compartidos** en el 2º cuatrimestre. Sin acoplamiento inter-grado aparecen en el 1er cuatrimestre **84 solapes de aula** y **14 solapes docentes** entre titulaciones distintas (en CP-SAT; 81 y 11 en SA), y en el 2º cuatrimestre **54 solapes de aula** y **3 docentes** (66 y 7 en SA).
3. **Otras limitaciones identificadas:**
   * **Especialización del Laboratorio de Física (`LF-4`):** En `aulas.csv`, `LF-4` figura con la categoría genérica `Laboratorio`, por lo que algunas prácticas de informática de 1º GII y 1º GIFM pueden ser asignadas a `LF-4`. Separar el tipo `Laboratorio_Fisica` evitaría esta asignación cruzada.
   * **Protocolo multi-semilla asimétrico:** Mientras en GII se ejecutó un benchmark formal con 5 semillas + línea base aleatoria, en GCID y GIFM los resultados se reportan sobre la semilla fija principal (`semilla=42`).

---

## 11. Conclusiones y Trabajo Futuro

### Conclusiones
* Se ha diseñado, implementado e integrado un sistema completo de optimización de horarios para las **tres titulaciones oficiales de la EII – ULPGC (2026–2027)** con datos reales (598 sesiones / 645 bloques, 1.127 horas semanales, 27 aulas).
* Se ha demostrado empíricamente la complementariedad entre la **Programación con Restricciones (OR-Tools CP-SAT)** y la **metaheurística propia de Recocido Simulado**, superando de forma abrumadora a la búsqueda aleatoria y mejorando la compactación y descarga de viernes respecto a los horarios oficiales publicados.
* Se ha cerrado el ciclo completo de ingeniería con un **cuadro de mandos interactivo en Streamlit** que unifica las tres titulaciones, permite inspeccionar horarios por curso, grupo, profesor y aula, y ejecuta optimizaciones en directo.

### Trabajo Futuro ("Para ir más allá")
1. **Solver Maestro Acoplado de toda la EII:** Unificar las tres matrices de sesiones en un único modelo global (CP-SAT o algoritmo memético híbrido Genético + SA) que elimine simultáneamente los solapes inter-titulación de aulas y profesorado compartido detectados en nuestra auditoría.
2. **Reoptimización ante incidencias con mínima perturbación:** Dado un horario ya publicado y una baja docente o cierre de aula, minimizar el número de sesiones modificadas (*minimal perturbation problem*).
3. **Formulación multiobjetivo (Frente de Pareto):** Aplicar NSGA-II o suma ponderada adaptativa para equilibrar simultáneamente huecos del alumnado, preferencias individuales del profesorado y uso energético de aulas.
4. **Planificación del calendario de exámenes:** Extender la misma infraestructura de datos a la programación de convocatorias oficiales de la EII.

---

## 12. Referencias

1. **Bettinelli, A., Cordeau, J. F., & Malucelli, F. (2015).** *A branch-and-cut-and-price algorithm for the curriculum-based course timetabling problem.* Computers & Operations Research, 54, 80–92.
2. **Burke, E. K., Kingston, J. H., & de Werra, D. (2004).** *Applications to school, timetable and sports scheduling.* In Handbook of Graph Theory (pp. 520–539). CRC Press.
3. **Kirkpatrick, S., Gelatt, C. D., & Vecchi, M. P. (1983).** *Optimization by simulated annealing.* Science, 220(4598), 671–680.
4. **Kostuch, P. (2005).** *The University Course Timetabling Problem with a three-phase approach.* Practice and Theory of Automated Timetabling V (PATAT 2004), LNCS 3616, 109–125. Springer.
5. **Lewis, R. (2008).** *A survey of metaheuristic techniques for course timetabling.* Annals of Operations Research, 159(1), 167–190.
6. **Perron, L., & Furnon, V. (2024).** *OR-Tools — Google Optimization Tools.* Google LLC. https://developers.google.com/optimization
7. **Schaerf, A. (1999).** *A survey of automated timetabling.* Artificial Intelligence Review, 13(2), 87–127.
8. **Escuela de Ingeniería Informática – ULPGC (2026).** *Horarios Oficiales del Curso Académico 2026–2027 (GII, GCID y GIFM).* Universidad de Las Palmas de Gran Canaria.

---

## Apartado Obligatorio: Declaración del Uso de la Inteligencia Artificial

De acuerdo con la normativa de la asignatura *Optimización y Heurística* (ULPGC), declaramos de forma transparente el uso de herramientas de Inteligencia Artificial en el desarrollo de este proyecto:

1. **Herramientas utilizadas:** Asistentes conversacionales y agentes de programación basados en modelos de lenguaje avanzados (Google Antigravity CLI / Gemini, ChatGPT / Claude).
2. **Tareas en las que se utilizó la IA:**
   * **Estructuración y validación de datos:** Conversión de tablas oficiales en PDF de GII, GCID y GIFM a archivos CSV normalizados y comprobación de consistencia de columnas.
   * **Soporte de programación y optimización:** Modularización de `restricciones.py`, aceleración de la evaluación del Recocido Simulado en Python puro mediante estructuras precomputadas $O(1)$, resolución de rutas dinámicas (`Path(__file__)`) y construcción de `visualizador.py`, `app.py` y `live_runner.py`.
   * **Integración y documentación:** Unificación limpia de ramas Git en carpetas independientes, auditoría visual/estadística de resultados y apoyo en la maquetación técnica de la memoria.
3. **Ejemplos representativos de peticiones (*prompts*) utilizadas:**
   * *«Implementa la restricción jerárquica de estudiantes (Teoría, Práctica de Aula y Laboratorio) teniendo en cuenta que el grupo 19 de aula une a los subgrupos 45 y 46 y que los grupos 1, 2 y 3 tienen horarios independientes».*
   * *«Organiza los archivos de la titulación en una carpeta independiente y calcula todas las rutas de forma dinámica respecto a `__file__` para que funcionen tras el merge en `main`».*
   * *«Haz una auditoría de cosas que se pueden mejorar en la visualización unificada de las 3 carreras y diseña un cuadro de mandos en Streamlit que incluya contraste con los PDFs oficiales y vista por profesor y aula».*
4. **Valoración crítica y errores detectados y corregidos por el equipo:**
   * La IA aceleró significativamente la depuración sintáctica, la creación de gráficos y la integración del dashboard, permitiendo abordar las **tres titulaciones completas** en lugar de una sola.
   * Sin embargo, se detectaron y corrigieron varios errores generados inicialmente por la IA: (a) modelado inicial de grupos como cadenas independientes que solapaba clases de teoría con subgrupos de prácticas; (b) impresión del diccionario completo de variables booleanas en la columna `Aula` y salida `"Sin aula"` en las primeras iteraciones; (c) superposición visual de desdobles simultáneos en `visualizador.py`; (d) omisión inicial del laboratorio `LF-4` que hacía infactible 1º GII; y (e) asimetrías de colores y métricas al integrar las tres ramas, corregidas mediante nuestra auditoría visual y el renderizador interactivo unificado.
   * Todo el código, las formulaciones matemáticas, las ejecuciones experimentales y las conclusiones han sido verificados, probados y comprendidos íntegramente por los tres autores.
