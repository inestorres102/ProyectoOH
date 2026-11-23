# Proyecto de Optimización y Heurística — Planificación de Horarios EII (ULPGC)

Sistema integrado de optimización combinatoria y cuadro de mandos interactivo para el **Diseño Automático de Horarios de la Escuela de Ingeniería Informática (EII - ULPGC)**, curso académico **2026–2027** (Propuesta **D1**, asignatura *Optimización y Heurística*, GCID).

El repositorio unifica de forma modular e independiente las **tres titulaciones de grado** de la Escuela bajo una arquitectura común y una interfaz web en **Streamlit**:

* **`GII/`** — Grado en Ingeniería Informática *(Yone)*
* **`GCID/`** — Grado en Ciencia e Ingeniería de Datos *(Inés)*
* **`GIFM/`** — Grado en Ingeniería Física y Matemática *(María)*

---

## 📁 Estructura del Repositorio Integrado

```text
ProyectoOH/
├── app.py                        # Cuadro de mandos interactivo unificado (Streamlit)
├── interactive_tools.py          # Exportador .ics, modo Estudiante y validador manual en tiempo real
├── live_runner.py                # Ejecutor aislado: What-If, Replay del SA y Carrera de Algoritmos
├── generar_activos_integracion.py# Generador reproducible de activos unificados y horarios SA de GII
├── dashboard_data/               # Caché unificada de horarios resueltos (CP-SAT y SA, 3 carreras)
├── .streamlit/config.toml        # Configuración visual (tema académico ULPGC)
├── requirements.txt              # Dependencias unificadas del proyecto completo
├── MEMORIA.md                    # Memoria académica unificada del equipo (12 apartados + uso de IA)
├── README.md                     # Documentación general del proyecto integrado
├── GII/                          # Grado en Ingeniería Informática (4 cursos, mañana y tarde)
│   ├── datos/                    # clases.csv (364 sesiones) y aulas.csv (27 aulas)
│   ├── src/                      # CP-SAT, Recocido Simulado propio, restricciones, visualizador y benchmark
│   ├── horarios/                 # 18 horarios PNG (CP-SAT: 1º–4º, Grupos 1, 2, 3 y conjuntos)
│   ├── horarios_SA/              # 18 horarios PNG (Recocido Simulado: 1º–4º, Grupos 1, 2, 3 y conjuntos)
│   ├── memoria/                  # MEMORIA.md, benchmark_resultados.csv y gráficas experimentales
│   ├── horario_GII_2026_2027.pdf # Horario oficial EII 2026–2027 (contraste visual)
│   └── README.md
├── GCID/                         # Grado en Ciencia e Ingeniería de Datos (4 cursos)
│   ├── datos/                    # clases_gcid.csv (150 sesiones) y aulas.csv (26 aulas)
│   ├── src/                      # CP-SAT global, Recocido Simulado (60.000 iter.), restricciones y visualizador
│   ├── horarios_CP-SAT/          # 8 horarios PNG (1º–4º, S1 y S2)
│   ├── horarios_metaheuristica/  # 8 horarios PNG generados por Recocido Simulado
│   ├── graficas/                 # Curvas de convergencia SA (1er y 2º semestre)
│   ├── horario_GCID_2026_2027.pdf# Horario oficial EII 2026–2027 (contraste visual)
│   └── README.md
└── GIFM/                         # Grado en Ingeniería Física y Matemática (4 cursos)
    ├── datos/                    # clases.csv (84 sesiones base), datos originales y aulas.csv (27 aulas)
    ├── src/                      # CP-SAT, paquete metaheuristica/ (SA híbrido), restricciones y visualizador
    ├── resultados/               # 16 horarios PNG (8 CP-SAT + 8 SA), CSVs resueltos y estadísticas SA
    └── horario_GIFM_2026_2027.pdf# Horario oficial EII 2026–2027 (contraste visual)
```

---

## 🚀 Instalación y Ejecución del Cuadro de Mandos (Streamlit)

Se recomienda Python 3.10 o superior. Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

### Vistas incluidas en el cuadro de mandos (`app.py`)
1. **🗓️ Explorador de Horarios:** Cuadrícula interactiva unificada con paleta EII (CP-SAT, SA y comparativa directa con buscador/resaltador), **🎓 Modo Mi Horario de Estudiante** (por subgrupo exacto o matrícula mixta multi-curso con cálculo de huecos y exportación a Google Calendar `.ics`), **🕹️ Editor Manual (Reto vs. Algoritmo)** con validador de restricciones en tiempo real, **contraste directo frente a los 3 PDFs oficiales 2026–2027** recortados al semestre exacto, y tabla con descargas CSV / `.ics` / PNG (300 DPI).
2. **👨‍🏫 Horarios por Profesor y Aula:** Calendario semanal individual de cualquier docente (con exportación `.ics`) o aula física, **mapa de calor de ocupación de espacios EII** y **auditoría automática de acoplamiento inter-titulación**.
3. **🏠 Visión General (EII):** KPIs consolidados de la Escuela (598 sesiones / 645 bloques, 1.127 horas semanales, 27 espacios físicos) y gráficas interactivas por titulación, curso y modalidad.
4. **📊 Resultados y Convergencia:** Benchmark multi-semilla de GII (Random Search vs. CP-SAT vs. SA), resultados globales de GCID con curvas de convergencia y estadísticas de las 8 instancias de GIFM.
5. **⚡ Simulador en Vivo (Laboratorio What-If, Replay SA y Carrera):** Reoptimización en directo ante **incidencias reales** (cierre de aulas, bloqueo de días por profesor, sliders de pesos multiobjetivo), **🎬 Replay paso a paso del Recocido Simulado** (viendo cómo desaparecen los conflictos conforme baja la temperatura) y **🏁 Carrera en directo** (Aleatorio vs. CP-SAT vs. SA).
6. **📚 Modelo Matemático y Catálogo:** Formulación formal UCTP ($X_{s,t,r}$), catálogo gráfico de aulas y buscador global de asignaturas y profesorado. Incluye además **🖥️ Modo Presentación (Proyector)** en la barra lateral.

---

## 📖 Memoria Académica Unificada

La memoria grupal completa del proyecto (12 apartados oficiales + declaración del uso de IA con ejemplos de *prompts*, evolución del código, resultados de GII/GCID/GIFM, contraste con horarios oficiales y análisis de acoplamiento inter-titulación) se encuentra en:
👉 [`MEMORIA.md`](MEMORIA.md)

---

## 🛠️ Ejecución Independiente de cada Titulación

Todos los módulos resuelven sus rutas dinámicamente respecto a su propia carpeta, por lo que pueden ejecutarse directamente desde la raíz del repositorio:

### GII (Grado en Ingeniería Informática)
```bash
python GII/src/modelo_base.py
python GII/src/metaheuristica_sa.py
python GII/src/evaluador_benchmark.py
```

### GCID (Grado en Ciencia e Ingeniería de Datos)
```bash
python GCID/src/modelo_base.py
python GCID/src/metaheuristica.py
```

### GIFM (Grado en Ingeniería Física y Matemática)
```bash
python GIFM/src/modelo_base.py
```

---

## 📊 Resumen Global de Resultados

| Titulación | Cursos | Sesiones | Horas/Sem | Motores Implementados | Factibilidad | Particularidades Modeladas |
| :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| **GII** | 1º–4º (S1 y S2) | 364 | 625 h | CP-SAT + SA Propio + Random Baseline | **100 %** | Turno tarde (G3), subgrupos jerárquicos, `LF-4` |
| **GCID** | 1º–4º (S1 y S2) | 150 | 260 h | CP-SAT Global + SA Propio (60k iter.) | **100 %** | 0 huecos duros, equilibrio 1º, J–V libres 3º S2, aula `A2-5` |
| **GIFM** | 1º–4º (S1 y S2) | 84 | 242 h | Híbrido CP-SAT → SA (1.000 iter.) | **100 %** | Bloques con semanas activas, aula `A3-1`, jornada ampliada 3º S2 |

---

## 👥 Equipo

* **Yone Suárez Viera** — GII + Integración y Cuadro de Mandos Unificado
* **Inés Torres Sánchez** — GCID + Arquitectura Base y Formulación Común
* **María Naranjo Peñate** — GIFM + Desglose en Bloques y Pipeline Híbrido CP-SAT → SA
