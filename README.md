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
├── live_runner.py                # Ejecutor aislado en subproceso para el Simulador en Vivo
├── generar_activos_integracion.py# Generador reproducible de activos unificados y horarios SA de GII
├── dashboard_data/               # Caché unificada de horarios resueltos (CP-SAT y SA, 3 carreras)
├── .streamlit/config.toml        # Configuración visual (tema académico ULPGC)
├── requirements.txt              # Dependencias unificadas del proyecto completo
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
1. **🗓️ Explorador de Horarios:** Cuadrícula interactiva unificada con la paleta oficial EII para `GII`, `GCID` y `GIFM` (alternando entre **CP-SAT**, **Recocido Simulado** y **comparativa directa CP-SAT vs. SA** con buscador/resaltador en vivo), **contraste directo frente a los 3 PDFs oficiales 2026–2027** recortados al semestre exacto, y tabla filtrable con descarga de CSV y láminas PNG (300 DPI).
2. **🏠 Visión General (EII):** KPIs consolidados de la Escuela (598 sesiones, 1.127 horas semanales, 27 espacios físicos) y gráficas interactivas por titulación, curso y modalidad.
3. **📊 Resultados y Convergencia:** Benchmark multi-semilla de GII (Random Search vs. CP-SAT vs. SA), resultados globales de GCID con curvas de convergencia y estadísticas de las 8 instancias de GIFM.
4. **⚡ Simulador en Vivo:** Ejecución real e interactiva de **CP-SAT** o **Recocido Simulado** sobre cualquiera de las tres titulaciones con parámetros ajustables y trazado de la curva de convergencia en directo, ejecutado en subproceso aislado sin alterar los archivos del repositorio.
5. **📚 Modelo Matemático y Catálogo:** Formulación formal UCTP ($X_{s,t,r}$), catálogo gráfico de aulas y buscador unificado de asignaturas y profesorado en las tres titulaciones.

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

* **Yone** — GII + Integración y Cuadro de Mandos Unificado
* **Inés** — GCID + Coordinación y Formulación Común
* **María** — GIFM
