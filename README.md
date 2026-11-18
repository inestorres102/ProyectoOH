# Planificación Automática de Horarios Académicos — GCID (ULPGC)

Sistema de optimización combinatoria para la generación automática de calendarios semestrales del **Grado en Ciencia e Ingeniería de Datos (GCID)** en la Escuela de Ingeniería Informática (ULPGC), desarrollado para la asignatura **Optimización y Heurística**.

El proyecto aborda el problema completo de los **4 cursos (1.º a 4.º)** y **2 cuatrimestres** (81 sesiones en el 1.er semestre y 59 en el 2.º semestre, distribuidas en 26 aulas), implementando y comparando dos paradigmas de resolución:
1. **Método Exacto:** Programación con Restricciones mediante **Google OR-Tools (`CP-SAT`)**.
2. **Metaheurística de Trayectoria:** **Recocido Simulado (*Simulated Annealing*)** implementado desde cero en Python.

---

## Estructura del Repositorio

```text
Proyecto_OH/
├── datos/
│   ├── aulas.csv                   # Catálogo de aulas de teoría y laboratorios con sus capacidades
│   └── clases_gcid.csv             # Sesiones lectivas de 1º a 4º curso (ambos cuatrimestres)
├── src/
│   ├── modelo_base.py              # Solver exacto basado en OR-Tools CP-SAT
│   ├── restricciones.py            # Definición formal de restricciones duras y blandas
│   ├── metaheuristica.py           # Implementación de Recocido Simulado y gráficas de convergencia
│   └── visualizador.py  
├── graficas/ 
│   ├── convergencia_SA_1er.png     # Gráfica de convergencia del primer cuatrimestre
│   └── convergencia_SA_2do.png     # Gráfica de convergencia del segundo cuatrimestre
├── horarios_CP-SAT/                # Horarios generados mediante CP-SAT
│   ├── primero/ 
│   │   └── horario_1GCID_1er.png 
│   │   └── horario_1GCID_2do.png
│   ├── segundo/
│   │   └── horario_2GCID_1er.png 
│   │   └── horario_2GCID_2do.png
│   ├── tercero/
│   │   └── horario_3GCID_1er.png 
│   │   └── horario_3GCID_2do.png
│   ├── cuarto/ 
│   │   └── horario_4GCID_1er.png 
│   │   └── horario_4GCID_2do.png 
├── horarios_metaheuristica/         # Horarios generados mediante metaheurística
│   ├── primero/ 
│   │   └── horario_SA_1GCID_1er.png 
│   │   └── horario_SA_1GCID_2do.png
│   ├── segundo/
│   │   └── horario_SA_2GCID_1er.png 
│   │   └── horario_SA_2GCID_2do.png
│   ├── tercero/
│   │   └── horario_SA_3GCID_1er.png 
│   │   └── horario_SA_3GCID_2do.png
│   ├── cuarto/ 
│   │   └── horario_SA_4GCID_1er.png 
│   │   └── horario_SA_4GCID_2do.png
├── .gitignore
├── requirements.txt                 
└── README.md
```

---

## Formulación del Problema

El horizonte semanal consta de **30 franjas horarias discretas** (de lunes a viernes, de `08:30` a `14:30`, en bloques de 1 hora).

### Restricciones Duras (Obligatorias)
* **No solapamiento de estudiantes:** Evita conflictos dentro de cada curso entre grupos generales (`17`, `18`) y sus subgrupos de laboratorio (`41`–`44`).
* **No solapamiento de profesorado:** Ningún docente puede impartir dos sesiones simultáneamente.
* **Capacidad y tipología de aulas:** Asignación exclusiva a aulas de `Teoria` o `Laboratorio` con aforo suficiente para el número de alumnos matriculados.
* **Continuidad diaria:** Ninguna sesión puede dividirse entre dos días distintos.
* **Compactación sin huecos:** Los grupos no tienen horas libres intermedias entre clases dentro de una misma jornada.
* **Prácticas Externas (3.º GCID — 2.º Semestre):** Jueves y viernes quedan completamente libres de docencia presencial para facilitar las prácticas en empresa.

### Restricciones Blandas (Función Objetivo a Minimizar)
* **Penalización por viernes a última hora (`+10` pts):** Evita programar inicios de clase en las franjas de `12:30–14:30` del viernes.
* **Preferencia de aula de referencia (`+25` pts):** Prioriza el aula `A2-5` para las sesiones de teoría del grupo general (`G17`).

---

## Instalación y Uso

### 1. Requisitos
Asegúrate de tener Python 3.10+ instalado junto con las siguientes dependencias:

```bash
pip install ortools pandas matplotlib
```

### 2. Ejecutar el Modelo Exacto (CP-SAT)
Optimiza ambos cuatrimestres garantizando el óptimo global y genera los 8 calendarios PNG (`horario_<curso>GCID_<semestre>.png`):

```bash
python src/modelo_base.py
```

### 3. Ejecutar la Metaheurística (Recocido Simulado)
Ejecuta el algoritmo de *Simulated Annealing* (60.000 iteraciones con enfriamiento geométrico y criterio de Metropolis), exporta los 8 horarios (`horario_SA_<curso>GCID_<semestre>.png`) y genera las curvas de convergencia (`convergencia_SA_1er.png` y `convergencia_SA_2do.png`):

```bash
python src/metaheuristica.py
```

---

## Resumen de Resultados Experimentales

| Métrica | CP-SAT (1.er Sem.) | Recocido Simulado (1.er Sem.) | CP-SAT (2.º Sem.) | Recocido Simulado (2.º Sem.) |
| :--- | :---: | :---: | :---: | :---: |
| **Sesiones planificadas** | 81 | 81 | 59 | 59 |
| **Choques duros** | `0` | `0` | `0` | `0` |
| **Horas libres (huecos)** | `0` | `0` | `0` | `0` |
| **Penalización blanda** | **85** *(óptimo)* | **150** | **25** *(óptimo)* | **50** |
| **Tiempo de ejecución** | `7.50 s` | `8.12 s` | `1.73 s` | `4.67 s` |

* **Visualización adaptativa:** `visualizador.py` detecta automáticamente el número de subgrupos activos de cada curso para renderizar 4 carriles paralelos en 1.º y 2.º, 2 carriles en 3.º y tarjetas a ancho completo en 4.º curso.