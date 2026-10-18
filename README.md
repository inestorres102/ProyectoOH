# Proyecto de Optimización y Heurística: Diseño de Horarios para la EII - ULPGC

Este repositorio contiene la solución completa, rigurosa y reproducible para la propuesta **D1: Diseño de horarios para la Escuela de Ingeniería Informática (EII)** de la asignatura *Optimización y Heurística* (Grado en Ciencia e Ingeniería de Datos, ULPGC, Curso 2026-2027).

---

## 📋 Descripción del Proyecto

El proyecto aborda la planificación y optimización del calendario docente del **Grado en Ingeniería Informática (GII)** utilizando los datos reales de la Escuela:
* **4 Cursos completos** (1º, 2º, 3º y 4º de GII) en ambos semestres (1º y 2º).
* **364 sesiones docentes** entre teoría, clases de aula y prácticas de laboratorio.
* **Turno de Mañana** (08:30 a 14:30) y **Turno de Tarde** (14:30 a 20:30).
* **27 espacios físicos** clasificados entre aulas de teoría, laboratorios de informática y el laboratorio de física (`LF-4`).

### Métodos Implementados:
1. **Línea Base (Random Search):** Generador estocástico uniforme de referencia ($N=5.000$ iteraciones).
2. **Método Exacto (Google OR-Tools CP-SAT):** Formulación mediante Programación con Restricciones.
3. **Metaheurística Propia (Recocido Simulado / *Simulated Annealing*):** Implementada **íntegramente desde cero en Python puro** (sin librerías de optimización externas), con operadores de vecindario especializados (reubicación y swaps) y enfriamiento geométrico.

---

## 📁 Estructura del Repositorio

```text
ProyectoOH-GII/
├── datos/
│   ├── clases.csv                   # Catálogo completo de las 364 sesiones docentes
│   └── aulas.csv                    # Catálogo de 27 aulas físicas con tipos y capacidades
├── src/
│   ├── modelo_base.py               # Solver exacto mediante OR-Tools CP-SAT y exportador
│   ├── metaheuristica_sa.py         # Recocido Simulado programado desde cero en Python puro
│   ├── restricciones.py             # Modelado de restricciones duras, blandas y subgrupos
│   ├── visualizador.py              # Renderizado gráfico idéntico a las hojas oficiales EII
│   └── evaluador_benchmark.py       # Suite experimental comparativa multi-semilla
├── memoria/
│   ├── MEMORIA.md                   # Memoria académica completa con los 12 apartados requeridos
│   ├── benchmark_resultados.csv     # Resultados experimentales brutos de todas las semillas
│   ├── tabla_comparativa.md         # Tabla con medias y desviaciones típicas
│   ├── grafica_comparativa_benchmark.png # Gráfica comparativa de calidad y tiempo
│   └── curva_convergencia_sa.png    # Gráfica de convergencia térmica del Recocido Simulado
├── horarios/                        # Horarios generados en PNG (300 DPI) para 1º, 2º, 3º y 4º
│   ├── 1GII/
│   ├── 2GII/
│   ├── 3GII/
│   └── 4GII/
├── requirements.txt                 # Dependencias del proyecto
└── README.md                        # Documentación técnica del proyecto
```

---

## 🚀 Instalación y Requisitos

Se requiere Python 3.10 o superior. Para instalar las dependencias necesarias:

```bash
pip install -r requirements.txt
```

---

## 🛠️ Guía de Ejecución

### 1. Ejecutar el Solver Exacto y Generar Horarios Oficiales (CP-SAT)
Para resolver las asignaciones de todos los cursos y generar los horarios visuales en `horarios/`:
```bash
python src/modelo_base.py
```

### 2. Ejecutar la Metaheurística Propia (Recocido Simulado)
Para ejecutar el algoritmo de Recocido Simulado programado desde cero y trazar su curva de convergencia:
```bash
python src/metaheuristica_sa.py
```

### 3. Reproducir la Suite Experimental Completa (Benchmark)
Para ejecutar la comparativa rigurosa entre Búsqueda Aleatoria, Recocido Simulado (5 semillas estadísticas) y CP-SAT:
```bash
python src/evaluador_benchmark.py
```
Este comando regenera automáticamente los ficheros en `memoria/` (`benchmark_resultados.csv`, `tabla_comparativa.md` y `grafica_comparativa_benchmark.png`).

---

## 📊 Resumen de Resultados Experimentales

| Instancia | Método | Tiempo Medio | Coste Huecos | Violaciones Duras | Factibilidad |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **1º GII (S1)** | Búsqueda Aleatoria | 0.69 s | 400.00 | 6.00 | **0.0 %** |
| **1º GII (S1)** | OR-Tools CP-SAT | 1.57 s | 190.00 | 0.00 | **100.0 %** |
| **1º GII (S1)** | **Recocido Simulado (Propio)** | 5.11 s | **0.00** | **0.00** | **100.0 %** |
| **2º GII (S1)** | Búsqueda Aleatoria | 0.93 s | 415.00 | 14.00 | **0.0 %** |
| **2º GII (S1)** | OR-Tools CP-SAT | 1.37 s | 270.00 | 0.00 | **100.0 %** |
| **2º GII (S1)** | **Recocido Simulado (Propio)** | 2.15 s | **58.00** | **0.00** | **100.0 %** |
| **3º GII (S1)** | Búsqueda Aleatoria | 0.94 s | 670.00 | 16.00 | **0.0 %** |
| **3º GII (S1)** | OR-Tools CP-SAT | 1.40 s | 140.00 | 0.00 | **100.0 %** |
| **3º GII (S1)** | **Recocido Simulado (Propio)** | 2.76 s | **61.00** | **0.00** | **100.0 %** |

---

## 📖 Memoria del Proyecto

La memoria académica completa, que detalla el marco teórico, estado del arte, formulación matemática formal, pseudocódigo, análisis experimental, discusión crítica y declaración del uso de IA, se encuentra en:
👉 [`memoria/MEMORIA.md`](memoria/MEMORIA.md)

---

## 👤 Autor

* **Yone** — Grado en Ciencia e Ingeniería de Datos (GCID), Escuela de Ingeniería Informática, ULPGC.