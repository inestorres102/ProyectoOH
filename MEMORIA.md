# Optimización de Horarios Universitarios para la Escuela de Ingeniería Informática (EII – ULPGC)

**Asignatura:** Optimización y Heurística (OH)  
**Titulación:** Grado en Ciencia e Ingeniería de Datos (GCID)  
**Centro:** Escuela de Ingeniería Informática (EII), Universidad de Las Palmas de Gran Canaria (ULPGC)  
**Curso Académico:** 2026–2027  
**Propuesta:** D1 — *Diseño de horarios para la Escuela de Ingeniería Informática (EII)*  
**Autores:** María Naranjo Peñate · Inés Torres Sánchez · Yone Suárez Viera

---

## 1. Título del Proyecto y Autores

* **Título:** Optimización de Horarios Universitarios para la Escuela de Ingeniería Informática (EII – ULPGC) mediante Programación con Restricciones y Recocido Simulado.
* **Reparto de trabajo del equipo:**
  * **Inés Torres Sánchez:** Diseño inicial del proyecto (`modelo_base.py`, `restricciones.py`, `visualizador.py`), planteamiento base del modelo y desarrollo completo del **Grado en Ciencia e Ingeniería de Datos (`GCID/`)** (CP-SAT conjunto para los 4 cursos de cada cuatrimestre + Recocido Simulado propio de 60.000 iteraciones).
  * **Yone Suárez Viera:** Desarrollo completo del **Grado en Ingeniería Informática (`GII/`)** (4 cursos, turnos de mañana y tarde, jerarquía de subgrupos, CP-SAT + Recocido Simulado propio desde cero + comparativa con 5 semillas frente a búsqueda aleatoria), **integración de las tres titulaciones** en un mismo repositorio y creación de la **aplicación interactiva en Streamlit** (`app.py`, `live_runner.py`).
  * **María Naranjo Peñate:** Desarrollo completo del **Grado en Ingeniería Física y Matemática (`GIFM/`)** (división automática de asignaturas en bloques semanales, control de semanas activas, ampliación excepcional de horario en 3º y combinación de CP-SAT con Recocido Simulado).

---

## 2. Resumen del Proyecto

En este proyecto resolvemos de forma automática la elaboración de los horarios semanales de los **tres grados oficiales** de la Escuela de Ingeniería Informática (EII) de la ULPGC para el curso **2026–2027**: Ingeniería Informática (**GII**), Ciencia e Ingeniería de Datos (**GCID**) e Ingeniería Física y Matemática (**GIFM**). En total se planifican **12 cursos completos** (24 horarios semestrales), **598 sesiones en los ficheros de datos** (**645 bloques horarios** tras dividir las asignaturas largas de GIFM), **1.127 horas lectivas a la semana** y **27 aulas y laboratorios**.

Para resolver el problema formulamos un modelo con restricciones obligatorias (sin choques de profesores, alumnos ni aulas, respetando la capacidad y sin partir clases entre dos días) y criterios de calidad (evitar horas libres entre clases, descargar las últimas horas del viernes y mantener aulas preferidas). Comparamos dos enfoques: un método exacto de **Programación con Restricciones** usando **Google OR-Tools (CP-SAT)** y **tres implementaciones propias desde cero en Python de Recocido Simulado**, evaluadas además frente a una **Búsqueda Aleatoria** como referencia básica.

Mientras la búsqueda aleatoria no consigue ningún horario válido (**0 %**), tanto CP-SAT como el Recocido Simulado logran el **100 % de horarios válidos** en cada titulación en pocos segundos, reduciendo drásticamente los huecos respecto a los horarios oficiales publicados y dejando menos de un 1 % de bloques en las últimas horas del viernes. Todo el sistema se integra en una **aplicación interactiva en Streamlit** que permite consultar horarios por curso, grupo, profesor y aula, compararlos con los PDFs oficiales y lanzar optimizaciones en directo.

---

## 3. Introducción y Motivación

Diseñar los horarios de una escuela universitaria es una tarea muy compleja y repetitiva cuando se hace a mano. En el Edificio de Informática y Matemáticas de la ULPGC conviven tres grados distintos que comparten instalaciones y tienen reglas diferentes:

1. **Grado en Ingeniería Informática (GII):** tiene 4 cursos y 2 semestres. En 1º y 2º hay muchos alumnos, por lo que existen dos grupos de **mañana** (Grupos 1 y 2, de 08:30 a 14:30) y un grupo de **tarde** (Grupo 3, de 14:30 a 20:30), además de clases de teoría, prácticas de aula y hasta 5 subgrupos de laboratorio (incluyendo el Laboratorio de Física `LF-4`).
2. **Grado en Ciencia e Ingeniería de Datos (GCID):** tiene 4 cursos de mañana que comparten aulas entre sí, exige **0 horas libres (huecos)** para todos los subgrupos (`41–44`), limita la carga diaria en 1º y deja **jueves y viernes completamente libres en 3º (2º semestre)** para que el alumnado pueda hacer prácticas externas.
3. **Grado en Ingeniería Física y Matemática (GIFM):** tiene asignaturas teóricas de 4 a 6 horas semanales que deben repartirse en varios bloques, clases que solo se imparten en **determinadas semanas** del cuatrimestre (por ejemplo, semanas 1–8 o 9–15) y un 2º cuatrimestre de 3º con tanta carga horaria que obliga a ampliar la jornada hasta las 16:30.

Hacer estos horarios a mano con hojas de cálculo lleva mucho tiempo y suele dejar horas muertas en medio del día o demasiadas clases los viernes a última hora. Aplicar técnicas de optimización y heurística permite automatizar el proceso, evitar errores humanos y conseguir horarios mucho más cómodos para estudiantes y profesores.

---

## 4. Descripción del Problema y Enfoques de Resolución

### 4.1. ¿Por qué es un problema difícil de optimización?
El problema de diseño de horarios universitarios (*University Course Timetabling*) consiste en decidir **qué día, a qué hora y en qué aula** se imparte cada clase semanal, cumpliendo una serie de reglas obligatorias y tratando de que el horario resultante sea lo más cómodo posible.

Aunque parezca sencillo a pequeña escala, es un problema combinatorio **NP-difícil**: conforme aumenta el número de clases, el número de horarios posibles crece de forma exponencial y es completamente imposible probarlos todos uno por uno. Si tenemos $|S|$ sesiones, $|T|$ franjas horarias posibles y $|R|$ aulas, el número de combinaciones teóricas es:

$$|\Omega| = (|T| \times |R|)^{|S|}$$

Por ejemplo, solo para un grupo de 2º GII (1er semestre: $|S|=31$ clases, $|T|=30$ franjas semanales, $|R|=27$ aulas), hay $810^{31} \approx 1{,}83 \times 10^{90}$ combinaciones posibles. En el 1er cuatrimestre de GCID (los 4 cursos juntos: $|S|=86$, $|T|=30$, $|R|=26$) el número supera $780^{86}$. Por eso necesitamos algoritmos inteligentes que encuentren buenos horarios sin revisar todas las opciones.

### 4.2. Enfoques utilizados
Para resolver este problema se han utilizado dos familias de métodos complementarias:
* **Programación con Restricciones (Google OR-Tools CP-SAT):** En lugar de probar horarios al azar, le indicamos al solver cuáles son las variables (hora de inicio y aula de cada clase) y qué reglas obligatorias deben cumplirse (por ejemplo, que un profesor o un aula no tengan dos clases a la vez). El solver descarta automáticamente combinaciones imposibles y busca una solución válida que minimice las penalizaciones.
* **Recocido Simulado (*Simulated Annealing*, programado desde cero en Python):** Parte de una solución inicial y va probando pequeños cambios (mover una clase a otra hora o aula, o intercambiar dos clases entre sí). Si el cambio mejora el horario, lo acepta siempre; si lo empeora un poco, puede aceptarlo con una cierta probabilidad controlada por una «temperatura» que va bajando poco a poco. Esto le permite al principio explorar soluciones diferentes sin quedarse atascado, y al final afinar los detalles del horario.

---

## 5. Formulación Matemática

### 5.1. Clasificación del problema
* **Discreto:** las variables toman valores enteros o finitos (franjas horarias `0, 1, 2, ...` y aulas concretas del catálogo), no valores continuos.
* **No convexo:** al ser un problema combinatorio con variables enteras y saltos discretos entre horas y aulas, existen muchos mínimos locales donde una búsqueda simple puede quedarse atrapada.
* **Con restricciones:** hay reglas obligatorias (duras) que todo horario válido tiene que cumplir sin excepción.
* **Determinista:** todos los datos de entrada (clases, duraciones, profesores, grupos y aulas) son fijos y conocidos de antemano.

### 5.2. Conjuntos y datos de entrada
* $S$: conjunto de sesiones o bloques de clase a colocar. Cada sesión $s \in S$ tiene una duración $d_s$ (en horas), un tipo (teoría, aula o laboratorio), un número de alumnos $a_s$, un profesor asignado y un grupo/subgrupo de estudiantes.
* $T = \{0, 1, \dots, 5H - 1\}$: franjas horarias de la semana (5 días de lunes a viernes por $H$ horas diarias). Normalmente $H = 6$ (de 08:30 a 14:30 en mañana, o de 14:30 a 20:30 en tarde), salvo en 3º GIFM (2º cuatrimestre), donde $H = 8$ (de 08:30 a 16:30).
* $R$: conjunto de aulas y laboratorios disponibles ($27$ espacios en total), cada uno con su tipo y su capacidad máxima $C_r$.
* $P$: conjunto de profesores. Llamamos $S(p)$ a las sesiones que imparte el profesor $p$.
* $G$: conjunto de subgrupos básicos de alumnos (por ejemplo, `41, 42, 43, 44`). Llamamos $S(g)$ a todas las clases a las que asiste el subgrupo $g$ (incluyendo tanto sus laboratorios como las teorías de su grupo completo).

### 5.3. Variables de decisión
Coincidiendo directamente con el código implementado en Python, para cada sesión $s \in S$ decidimos dos cosas:
1. **Hora de inicio:** $\text{inicio}_s \in \{0, \dots, |T| - d_s\}$ (número entero que indica la franja en la que empieza la sesión). Su hora de finalización queda determinada como $\text{fin}_s = \text{inicio}_s + d_s$, ocupando el intervalo $[\text{inicio}_s, \text{fin}_s)$.
2. **Aula asignada:** una variable binaria $y_{s,r} \in \{0, 1\}$ para cada aula compatible $r \in R$, que vale $1$ si la sesión $s$ se imparte en el aula $r$ y $0$ en caso contrario.

### 5.4. Restricciones duras (obligatorias)
Un horario solo es válido si cumple el 100 % de las siguientes condiciones:
1. **Una única aula compatible por sesión:** cada clase debe tener exactamente una aula asignada, del tipo adecuado (teoría o laboratorio) y con capacidad suficiente ($C_r \ge a_s$):
   $$\sum_{r \in R_{\text{válidas}}(s)} y_{s,r} = 1 \quad \forall s \in S$$
2. **No partir sesiones entre días:** toda sesión debe empezar y terminar el mismo día (es decir, $\text{inicio}_s$ y $\text{fin}_s - 1$ deben pertenecer al mismo día de la semana).
3. **Sin choques de profesorado:** ningún profesor $p \in P$ puede impartir dos sesiones cuyas franjas $[\text{inicio}_s, \text{fin}_s)$ se solapen.
4. **Sin choques de estudiantes (respetando la jerarquía de grupos):** para cada subgrupo básico $g \in G$, ninguna pareja de sesiones en $S(g)$ puede coincidir a la misma hora. Así, una clase de teoría del grupo completo bloquea automáticamente a todos sus subgrupos de prácticas y laboratorio.
5. **Sin choques de aulas:** dos sesiones no pueden ocupar la misma aula a la misma hora (salvo en GIFM cuando corresponden a semanas distintas del cuatrimestre que no coinciden).

### 5.5. Restricciones blandas y función objetivo
Entre los horarios que cumplen las reglas anteriores, buscamos minimizar una puntuación de penalización (**menor coste = mejor horario**):

$$\min \; \text{Coste} = W_{\text{duras}} \cdot \text{Choques} + w_{\text{huecos}} \cdot \text{Huecos} + w_{\text{viernes}} \cdot \text{Viernes} + w_{\text{aula}} \cdot \text{Aula}$$

* En **CP-SAT**, las restricciones duras se exigen directamente al solver ($\text{Choques} = 0$) y la función objetivo minimiza solo los términos blandos.
* En **Recocido Simulado**, cualquier choque duro se penaliza con un peso muy alto ($W_{\text{duras}} \gg w_{\text{blandas}}$) para que el algoritmo elimine primero todos los choques y después mejore la calidad del horario.

Cada titulación adapta los detalles según sus propias normas docentes:

| Característica | GII | GCID | GIFM |
| :--- | :--- | :--- | :--- |
| **Cómo se resuelve** | Por curso, semestre y turno (Mañana G1+G2 juntos; Tarde G3 aparte) | Los **4 cursos a la vez** por cuatrimestre compartiendo aulas | Por curso y cuatrimestre, dividiendo antes asignaturas largas en bloques |
| **Huecos entre clases** | Restricción blanda penalizada ($w_{\text{huecos}} = 15$ en SA; minimizado en CP-SAT) | **Restricción dura obligatoria** (`0` huecos para todos los subgrupos `41–44`) | Se busca compactar el día y repartir bien los bloques |
| **Viernes última hora** | Penalizado ($w_{\text{viernes}} = 10$) | Penalizado (`+10` pts en franjas `12:30–14:30`) | Penalizado en las últimas horas del viernes |
| **Aula preferida** | Sin aula fija (se elige cualquiera compatible por capacidad) | Preferencia por el aula `A2-5` para teoría (`+25` pts si sale de ella) | Preferencia por el aula `A3-1` para teoría |
| **Reglas especiales** | Turno de tarde (14:30–20:30) para G3 en 1º; jerarquía de subgrupos; lab `LF-4` | Teorías de 1º en días distintos; máx. 4 h/día en 1º; **jueves y viernes libres en 3º S2** (prácticas) | Semanas activas parciales (`1-8`, `9-15`, etc.); **jornada ampliada 08:30–16:30 en 3º C2** |

---

## 6. Métodos de Optimización Desarrollados

### 6.1. Línea base: Búsqueda Aleatoria (*Random Search*)
En `GII/src/evaluador_benchmark.py` se implementó una línea base muy sencilla: genera **5.000 horarios al azar** (respetando solo el turno y aulas compatibles) y se queda con el de menor penalización. Su objetivo es comprobar si el problema es realmente difícil y demostrar cuánto aportan nuestros algoritmos frente a probar al azar.

### 6.2. Método exacto: Google OR-Tools CP-SAT
En las tres titulaciones (`GII/src/modelo_base.py`, `GCID/src/modelo_base.py` y `GIFM/src/modelo_base.py`) se utilizó la librería **Google OR-Tools (CP-SAT)** creando variables de inicio, intervalos de tiempo (`NewIntervalVar`), intervalos opcionales por aula (`NewOptionalIntervalVar`) y la restricción `AddNoOverlap` para evitar cualquier solapamiento. Elegimos CP-SAT porque encaja de forma muy natural con problemas de horarios y nos sirve de referencia exacta muy rápida para compararla con nuestra propia metaheurística.

### 6.3. Metaheurística propia: Recocido Simulado (en Python puro)
Cumpliendo el requisito principal de la asignatura, el **Recocido Simulado** fue programado **desde cero en Python** sin usar librerías externas de optimización. Lo elegimos porque es fácil de adaptar a cualquier criterio de calidad (como contar huecos diarios por subgrupo) y permite escapar de malas soluciones iniciales sin quedarse bloqueado.

```text
Algoritmo: Recocido Simulado para Horarios
Entrada: sesiones, aulas, T_inicial, T_final, alpha, max_iter
Salida: mejor horario encontrado y su coste

1. horario <- generar horario inicial (aleatorio en GII/GCID; desde CP-SAT en GIFM)
2. coste <- evaluar(horario)          // choques duros * peso_alto + penalizaciones blandas
3. mejor_horario <- horario ; mejor_coste <- coste
4. T <- T_inicial
5. Mientras T > T_final (o no se llegue a max_iter):
6.     vecino <- modificar ligeramente horario (mover 1 clase o intercambiar 2 clases)
7.     coste_vecino <- evaluar(vecino)
8.     diferencia <- coste_vecino - coste
9.     Si diferencia <= 0 O random(0, 1) < exp(-diferencia / T):
10.        horario <- vecino ; coste <- coste_vecino
11.        Si coste < mejor_coste:
12.            mejor_horario <- horario ; mejor_coste <- coste
13.    T <- T * alpha                 // bajar la temperatura poco a poco
14. Devolver mejor_horario, mejor_coste
```

* **Configuración por titulación:**
  * **GII (`GII/src/metaheuristica_sa.py`):** parte de una solución aleatoria; en cada paso elige entre mover una sesión a otra hora/aula (75 %) o intercambiar las horas de dos sesiones (25 %); $T_0 = 120$, $T_f = 0{,}01$, $\alpha = 0{,}985$, con $140$–$150$ iteraciones por temperatura ($\approx 24.300$ evaluaciones en total).
  * **GCID (`GCID/src/metaheuristica.py`):** resuelve los **4 cursos del cuatrimestre juntos** partiendo de una solución aleatoria; combina mover una clase de hora (45 %), cambiar solo su aula (35 %) e intercambiar horas entre dos clases (20 %); $60.000$ iteraciones con $T_0 = 5.000 \to T_f = 0{,}1$ y penalizaciones escalonadas ($10.000$ por choque duro, $2.000$ por hueco, $10$/$25$ por viernes/aula).
  * **GIFM (`GIFM/src/metaheuristica/`):** enfoque **híbrido (CP-SAT → Recocido Simulado)** dividido en tres módulos (`evaluacion.py`, `movimientos.py` y `recocido_simulado.py`); parte de la solución ya válida de CP-SAT y explora $1.000$ movimientos vecinos válidos ($T_0 = 10$, $T_f = 0{,}01$, $\alpha = 0{,}995$) para comprobar si puede mejorar todavía más el coste.
* **Coste computacional:** en cada iteración la función de evaluación recorre las $|S|$ sesiones para comprobar choques y contar huecos (coste lineal $O(|S|)$ por iteración, es decir, $O(\text{iter} \cdot |S|)$ en total). Al guardar las compatibilidades en diccionarios y conjuntos de Python en lugar de leer tablas de `pandas` dentro del bucle, el algoritmo consigue evaluar miles de horarios por segundo.

---

## 7. Implementación, Evolución del Código y Dificultades Encontradas

### 7.1. Organización del repositorio
Cada titulación trabaja en su propia carpeta independiente usando rutas relativas al propio archivo (`Path(__file__)`), todo integrado en un mismo repositorio Git:

```text
ProyectoOH/
├── app.py                         # Aplicación web interactiva en Streamlit
├── interactive_tools.py           # Funciones extra (exportación .ics, editor manual, modo estudiante)
├── live_runner.py                 # Lanza los optimizadores en procesos separados para el simulador
├── generar_activos_integracion.py # Genera la caché unificada y los horarios SA de GII
├── dashboard_data/                # Datos unificados de los horarios resueltos (CP-SAT y SA)
├── MEMORIA.md / README.md         # Memoria del proyecto y guía de ejecución
├── GII/                           # Ingeniería Informática (datos, src, horarios, PDF, memoria)
├── GCID/                          # Ciencia e Ingeniería de Datos (datos, src, horarios, PDF, gráficas)
└── GIFM/                          # Ingeniería Física y Matemática (datos, src, resultados, PDF)
```

### 7.2. Evolución del proyecto y problemas reales resueltos
Durante el desarrollo por ramas en Git (`main`, `GCID`, `GII`, `GIFM` e `integracion`) nos encontramos con varios problemas prácticos que fuimos corrigiendo paso a paso:

1. **Primer prototipo sin restricciones:** la primera versión de `modelo_base.py` solo cargaba `clases.csv` y creaba variables en 30 franjas sin reglas de solapamiento (ponía todas las clases al lunes a las 08:30) para confirmar que OR-Tools funcionaba. Después separamos todas las reglas en `restricciones.py`.
2. **Errores de orden, capacidad de aulas y texto `"Sin aula"`:** inicialmente la tabla por consola salía desordenada por ID en vez de por día y hora; se corrigió ordenando por franja (`0..29`). También añadimos la comprobación de capacidad (`capacidad >= num_alumnos`) y la columna `semestre`. Al añadir las aulas, un bug guardaba todo el diccionario de variables en vez del nombre del aula elegida y otro fallo imprimía `"Sin aula"`; se arregló comprobando qué variable `aula_asignada` valía `1` y moviendo el dibujado de horarios a `visualizador.py`.
3. **Jerarquía de subgrupos y turno de tarde en GII:** al pasar a GII (3 grupos en 1º con prácticas de aula `G17–G22` y hasta 5 subgrupos de laboratorio `41–45`), tratar los nombres de grupo como textos sueltos hacía que una clase de teoría coincidiese con un laboratorio del mismo grupo. Se solucionó traduciendo cada grupo a sus subgrupos básicos, quitando la obligación de aula fija y añadiendo el parámetro `es_tarde` para separar el horario de tarde (14:30–20:30).
4. **Modelo infactible por falta del Laboratorio de Física (`LF-4`):** al meter el 2º semestre de 1º GII (*Fundamentos Físicos de la Informática*), CP-SAT devolvía `INFEASIBLE`. Al revisarlo vimos que faltaba añadir el laboratorio `LF-4` a `datos/aulas.csv`; en cuanto lo añadimos, el modelo se resolvió sin problema.
5. **Clases a la misma hora que se tapaban en el dibujo:** cuando varios subgrupos tenían laboratorio a la misma hora, la primera versión de `visualizador.py` pintaba una caja encima de otra. Se añadió un reparto automático por columnas que divide la casilla según cuántos subgrupos coincidan a la vez.
6. **Semanas parciales y falta de horas en 3º GIFM:** en GIFM hubo que dividir sesiones de 4–6 horas en bloques más cortos (`dividir_en_bloques`), comprobar qué semanas activas coincidían entre sí y ampliar automáticamente la jornada a 8 horas (08:30–16:30) en 3º GIFM (2º cuatrimestre), porque en 6 horas diarias no cabían todas las clases.
7. **Integración de las tres ramas en la app:** como las tres carpetas tenían archivos llamados igual (`modelo_base.py`, `restricciones.py`, `visualizador.py`), importarlos juntos en Python provocaba que se mezclaran. Para resolverlo, `live_runner.py` ejecuta cada optimizador en un proceso separado usando una carpeta temporal, sin pisar los ficheros de nadie.

---

## 8. Datos Utilizados (Origen, Descripción y Licencia)

* **Origen y uso:** Todos los datos son **100 % reales**, sacados de los **horarios oficiales públicos del curso 2026–2027** publicados por la **Escuela de Ingeniería Informática de la ULPGC** (`eii.ulpgc.es`), usados exclusivamente con fines académicos. Los tres PDFs originales están guardados en el repositorio para poder comprobar y comparar cualquier horario:
  * `GII/horario_GII_2026_2027.pdf`
  * `GCID/horario_GCID_2026_2027.pdf` *(V6 – 28/10/2026)*
  * `GIFM/horario_GIFM_2026_2027.pdf` *(V5 – 23/09/2026)*
* **Preprocesado:** Las tablas de los PDFs se pasaron a archivos CSV limpios (`clases.csv` / `clases_gcid.csv` y `aulas.csv`), comprobando capacidades, nombres de profesores, subgrupos y dividiendo los bloques semanales de GIFM con `GIFM/src/unificar_clases.py`.

| Titulación | Archivo de datos | Cursos / Cuatris | Sesiones CSV | Bloques horario | Horas/Sem | Asignaturas | Profesores | Aulas |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GII** | `GII/datos/clases.csv` | 1º–4º (S1 y S2) | 364 | 364 | 625 h | 39 | 30 | 27 |
| **GCID** | `GCID/datos/clases_gcid.csv` | 1º–4º (S1 y S2) | 150 | 150 | 260 h | 38 | 42 | 26 |
| **GIFM** | `GIFM/datos/clases.csv` | 1º–4º (S1 y S2) | 84 | 131 | 242 h | 46 | 41 | 27 |
| **Total EII** | **Unificado en `dashboard_data/`** | **12 cursos (24 cal.)** | **598** | **645** | **1.127 h** | **123** | **104 únicos** | **27 espacios** |

---

## 9. Experimentación y Resultados

### 9.0. Marcador General (Comparativa rápida)
Para entender los resultados de un vistazo, la siguiente tabla resume cómo rinde cada método en los criterios que más importan a alumnos y profesores (cumplir reglas, evitar huecos, evitar viernes a última hora, usar el aula habitual y tardar poco):

| Qué medimos | 🎲 Al Azar *(Referencia)* | 🟢 OR-Tools CP-SAT | 🟠 Recocido Simulado *(Propio)* | Mejor |
| :--- | :---: | :---: | :---: | :---: |
| **Horarios sin ningún choque** *(3 carreras)* | **0 %** *(6–16 choques)* | **100 %** | **100 %** | Empate (`100 %`) |
| **GII — Calidad en huecos y viernes** *(media 1º–3º)* | Muy malo (`495 pts`) | Bueno (`200 pts`) | **Muy bueno (`40 pts`, -80 %)** | **Recocido Simulado** |
| **GII — Clases que caen en viernes** *(todo el grado)* | — | 52 clases | **16 clases (-69 %)** | **Recocido Simulado** |
| **GCID — 0 horas libres (huecos)** *(4 cursos)* | — | **100 %** (`0` huecos) | **100 %** (`0` huecos) | Empate (`100 %`) |
| **GCID — Teorías en su aula fija (`A2-5`)** | — | **92 %** (`44 / 48`) | 75 % (`36 / 48`) | **CP-SAT** |
| **GIFM — Teorías en su aula fija (`A3-1`)** | — | **100 %** (`75 / 75`) | **100 %** (`75 / 75`) | Empate (`100 %`) |
| **GIFM — Horarios sin viernes a última hora** | — | **7 / 8** (`88 %`) | **7 / 8** (`88 %`) | Empate |
| **Velocidad** *(tiempo en generar horario)* | < 1 s *(no válido)* | **1,4 – 10,8 s** | **2,2 – 11,1 s** *(GIFM: 2–30 s)* | **CP-SAT** |

A continuación se detalla el resultado real de cada titulación.

### 9.1. GII — Comparativa con 5 semillas (Aleatoria vs. CP-SAT vs. Recocido Simulado)
Se probaron tres cursos de GII ejecutando Búsqueda Aleatoria (5.000 intentos al azar), CP-SAT y Recocido Simulado con **5 semillas distintas** (`semillas = [1, 2, 3, 4, 5]`, datos en `GII/memoria/benchmark_resultados.csv`).

* **¿Cómo funciona la puntuación en GII?** Menor = mejor (`0` = perfecto). Cada **choque obligatorio** suma `+2.000` pts; cada **hora libre (hueco)** suma `+15` pts; y cada hora de clase el **viernes** suma `+10 × posición de la hora`.

| Instancia | Método | Clases | Tiempo Medio (s) | ± Desv. | Puntuación Total | ± Desv. | Choques | Penaliz. Blanda (huecos + viernes) | ¿Válido? |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1º GII – S1** | Búsqueda Aleatoria | 24 | 0,69 s | — | 12.400,00 | — | 6 | 400,00 | **0 %** |
| **1º GII – S1** | OR-Tools CP-SAT | 24 | 1,57 s | — | 190,00 | — | 0 | 190,00 | **100 %** |
| **1º GII – S1** | **Recocido Simulado (Propio)** | 24 | 5,11 s | ±0,48 s | **0,00** | ±0,00 | **0** | **0,00** | **100 %** |
| **2º GII – S1** | Búsqueda Aleatoria | 31 | 0,93 s | — | 28.415,00 | — | 14 | 415,00 | **0 %** |
| **2º GII – S1** | OR-Tools CP-SAT | 31 | 1,37 s | — | 270,00 | — | 0 | 270,00 | **100 %** |
| **2º GII – S1** | **Recocido Simulado (Propio)** | 31 | 2,15 s | ±0,28 s | **58,00** | ±38,34 | **0** | **58,00** | **100 %** |
| **3º GII – S1** | Búsqueda Aleatoria | 30 | 0,94 s | — | 32.670,00 | — | 16 | 670,00 | **0 %** |
| **3º GII – S1** | OR-Tools CP-SAT | 30 | 1,40 s | — | 140,00 | — | 0 | 140,00 | **100 %** |
| **3º GII – S1** | **Recocido Simulado (Propio)** | 30 | 2,76 s | ±0,75 s | **61,00** | ±22,75 | **0** | **61,00** | **100 %** |

* **En resumen:** al azar es imposible sacar un horario sin choques (`0 %`). CP-SAT elimina todos los choques en menos de 1,6 segundos, pero deja bastantes huecos y clases el viernes (`140–270` pts). Nuestro Recocido Simulado saca **100 % de horarios válidos en las 5 semillas** y recorta esa penalización entre un **56 % y un 100 %** (llegando a `0` perfecto en 1º GII: sin choques, sin huecos y sin clases el viernes). En `GII/memoria/curva_convergencia_sa.png` se ve cómo elimina los choques en las primeras 2.000 iteraciones y luego afina huecos y viernes.

### 9.2. GCID — Optimización conjunta de los 4 cursos por cuatrimestre
Resultados recogidos en `GCID/README.md` y medidos sobre los horarios generados (`GCID/graficas/convergencia_SA_1er.png` y `convergencia_SA_2do.png`).

* **¿Qué se compara en GCID?** Ambos métodos cumplen siempre **0 choques y 0 huecos** en los 4 cursos a la vez. La diferencia está en cuántas teorías logran quedarse en el aula habitual **`A2-5`** (`+25` pts si sale fuera) y cuántas clases tocan el **viernes a última hora** (`+10` pts).

| Cuatrimestre y Método | Clases (4 cursos) | Choques | Horas libres (huecos) | Teorías en aula `A2-5` | Viernes última hora | Tiempo | Penalización |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1er Sem. — CP-SAT** | 86 | **0** | **0** | **25 / 28 (89 %)** | 1 clase | **10,8 s** | **85 pts** *(óptimo)* |
| **1er Sem. — Recocido Simulado** | 86 | **0** | **0** | 22 / 28 (79 %) | 1 clase | 11,1 s | 160 pts |
| **2º Sem. — CP-SAT** | 64 | **0** | **0** | **19 / 20 (95 %)** | **0 clases** | **4,8 s** | **25 pts** *(óptimo)* |
| **2º Sem. — Recocido Simulado** | 64 | **0** | **0** | 14 / 20 (70 %) | **0 clases** | 9,5 s | 150 pts |

* **En resumen:** los dos métodos garantizan **0 choques y 0 horas muertas** en los 4 cursos. CP-SAT gana aquí porque mete más clases de teoría en el aula `A2-5` (**92 %** en total frente al **75 %** del Recocido Simulado) y tarda algo menos.

### 9.3. GIFM — Evaluación de los 8 horarios (CP-SAT + Recocido Simulado)
Resultados sacados de los 8 ficheros `GIFM/resultados/estadisticas_recocido_*.csv` y los horarios generados. En GIFM, el Recocido Simulado parte del horario válido de CP-SAT y realiza 1.000 pruebas de mejora comprobando que no queden choques, que todas las teorías usen su aula habitual **`A3-1`** (`+5` pts si sale fuera) y que ninguna clase caiga en las **dos últimas horas del viernes** (`+10` pts).

| Curso y Cuatrimestre | Clases | ¿Sin choques? | Teorías en su aula (`A3-1`) | Viernes última hora | Tiempo SA | Resultado |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1º GIFM – 1er Cuatri** | 11 | Sí (`0`) | 9 / 9 (**100 %**) | **0 clases** | 5,6 s | **Perfecto** (`0` pts) |
| **1º GIFM – 2º Cuatri** | 11 | Sí (`0`) | 7 / 7 (**100 %**) | **0 clases** | 5,7 s | **Perfecto** (`0` pts) |
| **2º GIFM – 1er Cuatri** | 12 | Sí (`0`) | 8 / 8 (**100 %**) | **0 clases** | 7,1 s | **Perfecto** (`0` pts) |
| **2º GIFM – 2º Cuatri** | 20 | Sí (`0`) | 10 / 10 (**100 %**) | **0 clases** | 15,1 s | **Perfecto** (`0` pts) |
| **3º GIFM – 1er Cuatri** | 19 | Sí (`0`) | 12 / 12 (**100 %**) | **0 clases** | 7,4 s | **Perfecto** (`0` pts) |
| **3º GIFM – 2º Cuatri** *(hasta 16:30)* | 31 | Sí (`0`) | 14 / 14 (**100 %**) | **1 clase** *(de 31)* | 30,3 s | **Casi perfecto** (`10` pts) |
| **4º GIFM – 1er Cuatri** | 19 | Sí (`0`) | 11 / 11 (**100 %**) | **0 clases** | 5,8 s | **Perfecto** (`0` pts) |
| **4º GIFM – 2º Cuatri** | 8 | Sí (`0`) | 4 / 4 (**100 %**) | **0 clases** | 2,3 s | **Perfecto** (`0` pts) |

* **En resumen:** los 8 horarios salen **100 % sin choques** y el **100 % de las teorías (75 de 75)** se imparten en su aula `A3-1`. En 7 de los 8 horarios el resultado es **perfecto (`0` fallos)** y el Recocido Simulado confirma en sus 1.000 iteraciones que no se puede mejorar más; solo en **3º C2** (el más saturado, con 31 clases) queda 1 sola clase al final del viernes.

### 9.4. Comparación con los horarios oficiales publicados (2026–2027)
En la aplicación web (`app.py`) se pueden ver cara a cara nuestros **24 horarios generados** frente a los **3 PDFs oficiales** de la EII. Comparándolos se aprecian mejoras directas:
* **1º GCID (1er Semestre):** en el horario oficial (`V6`), el subgrupo `43` tiene **1 hora libre** el miércoles (`11:30–12:30`) y el subgrupo `44` tiene **2 horas libres** el viernes (`10:30–12:30`) seguidas de laboratorio de `IC1` a última hora (`12:30–14:30`). Nuestras soluciones eliminan **todos los huecos** (0 horas libres para los subgrupos `41–44`) y evitan esa última franja del viernes.
* **1º GII (1er Semestre, Grupo 1):** el Recocido Simulado propio logra **0 huecos** y deja el **viernes totalmente libre**, frente al horario oficial que reparte prácticas hasta el viernes.
* **Últimas horas del viernes en toda la Escuela:** de los 645 bloques semanales de las 3 titulaciones, solo **3 bloques en CP-SAT** y **4 en SA** (`< 0,7 %`) caen en las últimas horas del viernes.

### 9.5. Visualización interactiva (`app.py`)
Para cubrir todos los requisitos de visualización de la propuesta D1 e ir un paso más allá, construimos un cuadro de mandos en **Streamlit** (`python -m streamlit run app.py`, con **Modo Presentación** para proyectar en clase):
1. **Horarios por curso, grupo y subgrupo:** cuadrícula interactiva con los colores oficiales de la EII, comparativa directa CP-SAT vs. SA, contraste frente a los PDFs oficiales, **Modo Mi Horario de Estudiante** (permite filtrar tu subgrupo o asignaturas de varios cursos y exportar el calendario a Google Calendar en `.ics`) y un **Editor Manual** donde el usuario puede mover clases y ver en tiempo real si provoca choques.
2. **Horarios por profesor y por aula:** horario semanal individual de cualquier profesor (exportable a `.ics`) o aula física (`A1-1` a `LF-4`), mapa de calor de ocupación de aulas y comprobación de choques entre carreras.
3. **Laboratorio en vivo:** permite probar cambios en directo (cerrar un aula, bloquear un día a un profesor o cambiar pesos de penalización), ver paso a paso cómo el Recocido Simulado pasa del desorden inicial a un horario limpio, y lanzar una **carrera en directo** entre Búsqueda Aleatoria, CP-SAT y Recocido Simulado.

---

## 10. Discusión y Limitaciones

1. **¿Qué método funciona mejor y cuándo?**
   * **OR-Tools CP-SAT** funciona mejor cuando todas las reglas son obligatorias y el objetivo es sencillo de expresar (como en GCID, donde encuentra el óptimo exacto de los 4 cursos en menos de 11 s, o en GIFM, donde sirve de punto de partida inmediato).
   * **Recocido Simulado (propio)** brilla cuando queremos optimizar criterios más difíciles de formular para un solver exacto (como minimizar los huecos diarios de cada subgrupo en GII, donde reduce el coste entre un 56 % y un 100 % frente a CP-SAT) y además permite cambiar o añadir penalizaciones de forma muy sencilla.
2. **Limitación principal — Resolución separada por titulación:**
   * Al resolverse `GII/`, `GCID/` y `GIFM/` por separado, cada carrera garantiza **0 conflictos internos**, pero **no se coordinan entre sí las aulas ni los profesores que dan clase en más de un grado**.
   * Nuestra auditoría automática en `app.py` mide exactamente este impacto: hay **7 profesores compartidos** en el 1er cuatrimestre (por ejemplo, *Carmelo Rubén García Rodríguez*, *Cayetano Guerra Artal*, *Javier Sánchez Pérez*, *José Carlos Ruiz Luque* y *José Juan Hernández Cabrera*) y **2 profesores compartidos** en el 2º cuatrimestre. Al no resolver las tres carreras juntas, en el 1er cuatrimestre aparecen **84 solapes de aula** y **14 de profesor** entre grados distintos en CP-SAT (81 y 11 en SA), y en el 2º cuatrimestre **54 de aula** y **3 de profesor** (66 y 7 en SA).
3. **Otras limitaciones:**
   * **Tipo genérico del laboratorio `LF-4`:** en `aulas.csv` aparece etiquetado simplemente como `Laboratorio`, por lo que algunas prácticas de informática de 1º pueden asignarse ahí. Crear un tipo aparte (`Laboratorio_Fisica`) resolvería ese detalle.
   * **Diferencias en la experimentación entre titulaciones:** en GII se ejecutó una prueba formal con 5 semillas y búsqueda aleatoria, mientras que en GCID y GIFM se evaluó con una sola semilla fija (`semilla = 42`).

---

## 11. Conclusiones y Trabajo Futuro

### Conclusiones
* Se ha desarrollado e integrado una solución completa de optimización de horarios para las **tres titulaciones oficiales de la EII – ULPGC (2026–2027)** con datos 100 % reales (598 sesiones / 645 bloques, 1.127 horas semanales y 27 espacios).
* Se ha comprobado en la práctica cómo se complementan la **Programación con Restricciones (OR-Tools CP-SAT)** y nuestra propia implementación de **Recocido Simulado**: ambos superan por completo a la búsqueda aleatoria y mejoran los horarios oficiales en compactación y descarga del viernes.
* Se ha construido una aplicación interactiva en **Streamlit** que unifica las tres carreras, permite consultar horarios por curso, grupo, profesor y aula, y deja probar los algoritmos en tiempo real.

### Trabajo futuro ("Para ir más allá")
1. **Resolver las tres carreras juntas en un solo modelo:** unir las sesiones de GII, GCID y GIFM en un único optimizador global para eliminar también los choques de aulas y profesores compartidos entre titulaciones.
2. **Reajustar horarios ante imprevistos cambiando lo mínimo:** dado un horario ya publicado, si hay una baja de profesor o cierra un aula, recalcular el horario moviendo el menor número posible de clases para molestar lo menos posible al alumnado.
3. **Incluir preferencias del profesorado:** permitir que cada docente indique franjas preferidas (por ejemplo, para tutorías o investigación) como una restricción blanda adicional.
4. **Aplicarlo al calendario de exámenes:** reutilizar la misma estructura de datos y algoritmos para planificar las convocatorias de exámenes de la EII evitando que un alumno tenga exámenes seguidos o el mismo día.

---

## Apartado Obligatorio: Declaración del Uso de la Inteligencia Artificial

De acuerdo con la normativa de la asignatura *Optimización y Heurística* (ULPGC), declaramos de forma transparente cómo hemos utilizado la Inteligencia Artificial en este proyecto:

1. **Herramientas utilizadas:** Asistentes conversacionales y de programación (Google Antigravity CLI / Gemini, ChatGPT y Claude).
2. **Tareas en las que se utilizó la IA:**
   * **Preparación de datos:** apoyo al pasar las tablas de los PDFs oficiales de GII, GCID y GIFM a archivos CSV ordenados y revisar errores de formato.
   * **Apoyo en código y optimización:** organización modular de `restricciones.py`, mejora de velocidad del Recocido Simulado en Python usando diccionarios en memoria, ajuste de rutas dinámicas (`Path(__file__)`) y ayuda en la construcción de `visualizador.py`, `app.py` y `live_runner.py`.
   * **Integración y documentación:** unión ordenada de las ramas Git en carpetas independientes, comprobación automática de resultados y apoyo en la redacción clara de la memoria.
3. **Ejemplos de peticiones (*prompts*) utilizadas:**
   * *«Implementa la restricción jerárquica de estudiantes (Teoría, Práctica de Aula y Laboratorio) teniendo en cuenta que el grupo 19 de aula une a los subgrupos 45 y 46 y que los grupos 1, 2 y 3 tienen horarios independientes».*
   * *«Organiza los archivos de la titulación en una carpeta independiente y calcula todas las rutas de forma dinámica respecto a `__file__` para que funcionen tras el merge en `main`».*
   * *«Haz una auditoría de cosas que se pueden mejorar en la visualización unificada de las 3 carreras y diseña un cuadro de mandos en Streamlit que incluya contraste con los PDFs oficiales y vista por profesor y aula».*
4. **Valoración crítica y errores detectados y corregidos por el equipo:**
   * La IA nos permitió trabajar más rápido en la depuración, las gráficas y la integración de la app, haciendo posible abarcar los **tres grados completos** de la Escuela en lugar de uno solo.
   * Sin embargo, tuvimos que detectar y corregir varios errores generados inicialmente por la IA: (a) tratar los subgrupos como textos independientes, lo que solapaba teoría y laboratorios; (b) imprimir diccionarios completos o `"Sin aula"` en las primeras versiones; (c) solapamiento visual de subgrupos simultáneos en `visualizador.py`; (d) falta del laboratorio `LF-4` que hacía infactible 1º GII; y (e) referencias bibliográficas imprecisas y tecnicismos innecesarios en un primer borrador de la memoria, que revisamos y limpiamos manualmente.
   * Todo el código, el modelo matemático, los resultados experimentales y las conclusiones han sido revisados, probados y comprendidos por los tres autores.
