

"""
MODELO BASE DE OPTIMIZACIÓN DE HORARIOS
Grado en Ingeniería en Diseño y Fabricación / GIFM

Genera los horarios de los cuatro cursos y los dos cuatrimestres
utilizando Google OR-Tools CP-SAT.
"""

from pathlib import Path

import pandas as pd
from ortools.sat.python import cp_model

from restricciones import (
    aplicar_restriccion_estudiantes,
    aplicar_restriccion_cambio_dia,
    aplicar_restriccion_profesores,
    aplicar_restriccion_aulas,
    aplicar_restricciones_blandas
)

from visualizador import exportar_horario_png


# ---------------------------------------------------------
# CONFIGURACIÓN GENERAL
# ---------------------------------------------------------

RUTA_PROYECTO = Path(__file__).resolve().parent.parent

RUTA_DATOS = RUTA_PROYECTO / "datos"
RUTA_RESULTADOS = RUTA_PROYECTO / "resultados"

ARCHIVO_CLASES = RUTA_DATOS / "clases.csv"
ARCHIVO_AULAS = RUTA_DATOS / "aulas.csv"

DIAS = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes"
]

HORAS_INICIO = 8
HORAS_FIN = 14

HORAS_POR_DIA = HORAS_FIN - HORAS_INICIO
NUM_DIAS = len(DIAS)

TOTAL_SLOTS = NUM_DIAS * HORAS_POR_DIA

TIEMPO_MAXIMO_SOLVER = 30


# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def cargar_datos():
    """Carga los CSV de clases y aulas."""

    if not ARCHIVO_CLASES.exists():
        raise FileNotFoundError(
            f"No se encuentra el archivo: {ARCHIVO_CLASES}"
        )

    if not ARCHIVO_AULAS.exists():
        raise FileNotFoundError(
            f"No se encuentra el archivo: {ARCHIVO_AULAS}"
        )

    df_clases = pd.read_csv(
        ARCHIVO_CLASES,
        encoding="utf-8-sig"
    )

    df_aulas = pd.read_csv(
        ARCHIVO_AULAS,
        encoding="utf-8-sig"
    )

    columnas_obligatorias = [
        "id_sesion",
        "asignatura",
        "tipo",
        "grupo",
        "duracion_horas",
        "num_alumnos",
        "tipo_aula_requerida",
        "profesor",
        "curso",
        "cuatrimestre"
    ]

    faltantes = [
        columna
        for columna in columnas_obligatorias
        if columna not in df_clases.columns
    ]

    if faltantes:
        raise ValueError(
            "Faltan columnas obligatorias en clases.csv: "
            + ", ".join(faltantes)
        )

    if "semanas_activas" not in df_clases.columns:
        df_clases["semanas_activas"] = ""

    # Convertir columnas numéricas.
    for columna in [
        "curso",
        "cuatrimestre",
        "duracion_horas",
        "num_alumnos"
    ]:
        df_clases[columna] = pd.to_numeric(
            df_clases[columna],
            errors="raise"
        ).astype(int)

    if (df_clases["duracion_horas"] <= 0).any():
        raise ValueError(
            "Hay sesiones con duración igual o inferior a cero."
        )

    if (df_clases["num_alumnos"] < 0).any():
        raise ValueError(
            "Hay sesiones con número de alumnos negativo."
        )

    return df_clases, df_aulas


def dividir_en_bloques(df_clases):
    """
    Divide las horas semanales de cada sesión en bloques
    de dos horas y, si es necesario, un bloque de una hora.

    Ejemplos:
        1 hora -> 1
        2 horas -> 2
        3 horas -> 2 + 1
        4 horas -> 2 + 2
        5 horas -> 2 + 2 + 1

    Cada bloque conserva la información de su sesión original.
    """

    bloques = []

    for indice_original, fila in df_clases.iterrows():

        duracion_total = int(fila["duracion_horas"])

        duraciones = []

        while duracion_total >= 2:
            duraciones.append(2)
            duracion_total -= 2

        if duracion_total == 1:
            duraciones.append(1)

        for numero_bloque, duracion in enumerate(
            duraciones,
            start=1
        ):

            nuevo_bloque = fila.to_dict()

            nuevo_bloque["duracion_horas"] = duracion

            nuevo_bloque["indice_sesion_original"] = (
                indice_original
            )

            nuevo_bloque["numero_bloque"] = numero_bloque

            nuevo_bloque["id_bloque"] = (
                f"{fila['id_sesion']}_B{numero_bloque}"
                f"_FILA{indice_original}"
            )

            bloques.append(nuevo_bloque)

    df_bloques = pd.DataFrame(bloques)

    return df_bloques.reset_index(drop=True)


def obtener_hora(slot):
    """Convierte una posición absoluta en su etiqueta horaria."""

    hora_idx = int(slot) % HORAS_POR_DIA

    hora = HORAS_INICIO + hora_idx

    return f"{hora:02d}:30-{hora + 1:02d}:30"


def obtener_dia(slot):
    """Obtiene el día correspondiente a una posición absoluta."""

    dia_idx = int(slot) // HORAS_POR_DIA

    return DIAS[dia_idx]


def obtener_aula_asignada(solver, asignaciones, indice):
    """Devuelve el aula seleccionada por el solver."""

    for aula_id, variable in asignaciones[indice].items():

        if solver.Value(variable) == 1:
            return aula_id

    return "Sin asignar"


# ---------------------------------------------------------
# CONSTRUCCIÓN Y RESOLUCIÓN DEL MODELO
# ---------------------------------------------------------

def generar_horario(curso, cuatrimestre, abrir_imagen=False):
    """
    Genera el horario optimizado de un curso y cuatrimestre.

    Parámetros:
        curso: número del curso (1, 2, 3 o 4).
        cuatrimestre: 1 o 2.
        abrir_imagen: indica si se abre el PNG al terminar.
    """

    print("\n" + "=" * 65)
    print(
        f"GENERANDO HORARIO: {curso}º GIFM - "
        f"{cuatrimestre}º CUATRIMESTRE"
    )
    print("=" * 65)

    # 1. Cargar los datos.
    df_clases, df_aulas = cargar_datos()

    # 2. Filtrar curso y cuatrimestre.
    df_filtrado = df_clases[
        (df_clases["curso"] == curso)
        &
        (df_clases["cuatrimestre"] == cuatrimestre)
    ].copy()

    df_filtrado = df_filtrado.reset_index(drop=True)

    if df_filtrado.empty:
        print(
            f"No hay sesiones para {curso}º GIFM, "
            f"{cuatrimestre}º cuatrimestre."
        )
        return None

    print(
        f"Sesiones originales: {len(df_filtrado)}"
    )

    # 3. Dividir las sesiones en bloques.
    df_bloques = dividir_en_bloques(df_filtrado)

    df_bloques = df_bloques.reset_index(drop=True)

    numero_bloques = len(df_bloques)

    print(
        f"Bloques horarios que se deben colocar: "
        f"{numero_bloques}"
    )

    # 4. Crear el modelo.
    model = cp_model.CpModel()

    start_vars = []
    end_vars = []
    interval_vars = []

    # 5. Crear variables de inicio, fin e intervalo.
    for i, fila in df_bloques.iterrows():

        duracion = int(fila["duracion_horas"])

        inicio = model.NewIntVar(
            0,
            TOTAL_SLOTS - duracion,
            f"inicio_{i}"
        )

        fin = model.NewIntVar(
            duracion,
            TOTAL_SLOTS,
            f"fin_{i}"
        )

        model.Add(fin == inicio + duracion)

        intervalo = model.NewIntervalVar(
            inicio,
            duracion,
            fin,
            f"intervalo_{i}"
        )

        start_vars.append(inicio)
        end_vars.append(fin)
        interval_vars.append(intervalo)

    # 6. Los bloques de una misma sesión deben estar
    # en días diferentes.
    grupos_sesion = df_bloques.groupby(
        "indice_sesion_original"
    ).groups

    for indice_original, indices in grupos_sesion.items():

        indices = list(indices)

        if len(indices) <= 1:
            continue

        dias_bloques = []

        for indice in indices:

            dia_bloque = model.NewIntVar(
                0,
                NUM_DIAS - 1,
                f"dia_sesion_{indice_original}_{indice}"
            )

            model.AddDivisionEquality(
                dia_bloque,
                start_vars[indice],
                HORAS_POR_DIA
            )

            dias_bloques.append(dia_bloque)

        model.AddAllDifferent(dias_bloques)

    # 7. Aplicar restricciones de estudiantes.
    print("Aplicando restricciones de estudiantes...")

    aplicar_restriccion_estudiantes(
        model,
        df_bloques,
        interval_vars
    )

    # 8. Aplicar restricciones de cambio de día.
    print("Aplicando restricciones de horario diario...")

    aplicar_restriccion_cambio_dia(
        model,
        start_vars,
        end_vars,
        HORAS_POR_DIA
    )

    # 9. Aplicar restricciones de profesores.
    print("Aplicando restricciones de profesores...")

    aplicar_restriccion_profesores(
        model,
        df_bloques,
        interval_vars
    )

    # 10. Aplicar restricciones de aulas.
    print("Aplicando restricciones de aulas...")

    aula_asignada = aplicar_restriccion_aulas(
        model,
        df_bloques,
        start_vars,
        end_vars,
        df_aulas
    )

    # 11. Aplicar preferencias blandas.
    print("Aplicando preferencias de optimización...")

    aplicar_restricciones_blandas(
        model,
        start_vars,
        df_bloques,
        TOTAL_SLOTS,
        aula_asignada,
        aula_preferida="A3-1"
    )

    # 12. Resolver el modelo.
    solver = cp_model.CpSolver()

    solver.parameters.max_time_in_seconds = (
        TIEMPO_MAXIMO_SOLVER
    )

    solver.parameters.num_search_workers = 8

    print("\nBuscando una solución...")

    estado = solver.Solve(model)

    # 13. Comprobar el resultado.
    if estado not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE
    ):

        print(
            "\nNo se ha encontrado una solución factible."
        )

        print(
            "Estado del solver:",
            solver.StatusName(estado)
        )

        return None

    print("\n¡Horario generado correctamente!")

    print(
        "Estado:",
        solver.StatusName(estado)
    )

    print(
        "Tiempo de resolución:",
        round(solver.WallTime(), 2),
        "segundos"
    )

    if estado == cp_model.OPTIMAL:
        print("Se ha encontrado una solución óptima.")
    else:
        print(
            "Se ha encontrado una solución factible, "
            "pero no se garantiza que sea óptima."
        )

    # 14. Extraer los resultados.
    resultados = []

    for i, fila in df_bloques.iterrows():

        slot = solver.Value(start_vars[i])

        duracion = int(fila["duracion_horas"])

        aula = obtener_aula_asignada(
            solver,
            aula_asignada,
            i
        )

        semanas = fila.get("semanas_activas", "")

        if pd.isna(semanas):
            semanas = ""

        resultados.append({
            "Slot": slot,
            "Sesion": fila["id_bloque"],
            "Sesion_original": fila["id_sesion"],
            "Asignatura": fila["asignatura"],
            "Tipo": fila["tipo"],
            "Grupo": fila["grupo"],
            "Dia": obtener_dia(slot),
            "Hora": obtener_hora(slot),
            "Duracion": f"{duracion}h",
            "Duracion_horas": duracion,
            "Aula": aula,
            "Profesor": fila["profesor"],
            "Semanas_activas": str(semanas)
        })

    df_resultado = pd.DataFrame(resultados)

    df_resultado = df_resultado.sort_values(
        by=["Slot", "Asignatura"]
    ).reset_index(drop=True)

    # 15. Mostrar resumen del horario.
    print("\nResumen del horario:")

    print(
        df_resultado[
            [
                "Asignatura",
                "Tipo",
                "Grupo",
                "Dia",
                "Hora",
                "Duracion",
                "Aula",
                "Semanas_activas"
            ]
        ].to_string(index=False)
    )

    # 16. Exportar el PNG.
    RUTA_RESULTADOS.mkdir(
        parents=True,
        exist_ok=True
    )

    nombre_archivo = (
        f"horario_{curso}GIFM_{cuatrimestre}cuatri.png"
    )

    ruta_salida = RUTA_RESULTADOS / nombre_archivo

    titulo = (
        f"CALENDARIO ACADÉMICO — {curso}º GIFM "
        f"({cuatrimestre}º CUATRIMESTRE)"
    )

    exportar_horario_png(
        df_resultado,
        ruta_salida=str(ruta_salida),
        abrir_al_terminar=abrir_imagen,
        titulo=titulo
    )

    return df_resultado


# ---------------------------------------------------------
# GENERAR LOS OCHO HORARIOS
# ---------------------------------------------------------

def generar_todos_los_horarios():
    """
    Genera los horarios de los cuatro cursos
    y sus dos cuatrimestres.
    """

    resultados = {}

    total = 8
    contador = 0

    for curso in range(1, 5):

        for cuatrimestre in range(1, 3):

            contador += 1

            print(
                f"\nPROGRESO: {contador}/{total}"
            )

            try:

                resultado = generar_horario(
                    curso,
                    cuatrimestre,
                    abrir_imagen=False
                )

                resultados[
                    (curso, cuatrimestre)
                ] = resultado

            except Exception as error:

                print(
                    "\nERROR al generar el horario de "
                    f"{curso}º GIFM, "
                    f"{cuatrimestre}º cuatrimestre:"
                )

                print(error)

                resultados[
                    (curso, cuatrimestre)
                ] = None

    # Resumen final.
    print("\n" + "=" * 65)
    print("RESUMEN FINAL DE GENERACIÓN")
    print("=" * 65)

    generados = 0
    fallidos = 0

    for (curso, cuatrimestre), resultado in resultados.items():

        if resultado is not None:

            print(
                f"OK: {curso}º GIFM - "
                f"{cuatrimestre}º cuatrimestre"
            )

            generados += 1

        else:

            print(
                f"NO GENERADO: {curso}º GIFM - "
                f"{cuatrimestre}º cuatrimestre"
            )

            fallidos += 1

    print("\nHorarios generados:", generados)
    print("Horarios no generados:", fallidos)

    print(
        "\nLos resultados se encuentran en:",
        RUTA_RESULTADOS
    )

    return resultados


# ---------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------

if __name__ == "__main__":

    generar_todos_los_horarios()