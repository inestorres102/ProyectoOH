
from pathlib import Path

import pandas as pd
from ortools.sat.python import cp_model


# ---------------------------------------------------------
# IMPORTS COMPATIBLES CON MÓDULO O SCRIPT
# ---------------------------------------------------------

if __package__:
    from .restricciones import (
        aplicar_restriccion_estudiantes,
        aplicar_restriccion_cambio_dia,
        aplicar_restriccion_profesores,
        aplicar_restriccion_aulas,
        aplicar_restricciones_blandas
    )

    from .visualizador import exportar_horario_png

    from .metaheuristica.recocido_simulado import (
        ejecutar_recocido_simulado
    )

else:
    from restricciones import (
        aplicar_restriccion_estudiantes,
        aplicar_restriccion_cambio_dia,
        aplicar_restriccion_profesores,
        aplicar_restriccion_aulas,
        aplicar_restricciones_blandas
    )

    from visualizador import exportar_horario_png

    from metaheuristica.recocido_simulado import (
        ejecutar_recocido_simulado
    )


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

HORA_INICIO = 8
MINUTO_INICIO = 30

# Horario ordinario: 08:30-14:30.
HORAS_POR_DIA_NORMAL = 6

# Ampliación excepcional: 08:30-16:30.
HORAS_POR_DIA_AMPLIADO = 8

# Solo se permite ampliar este horario para este caso.
HORARIO_AMPLIABLE = (3, 2)

TIEMPO_MAXIMO_SOLVER = 120
NUM_TRABAJADORES_SOLVER = 8

AULA_PREFERIDA = "A3-1"


# ---------------------------------------------------------
# CARGA Y VALIDACIÓN DE DATOS
# ---------------------------------------------------------

def cargar_datos():
    """Carga y valida los CSV de clases y aulas."""

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

    columnas_aulas = [
        "id_aula",
        "tipo",
        "capacidad"
    ]

    faltantes_aulas = [
        columna
        for columna in columnas_aulas
        if columna not in df_aulas.columns
    ]

    if faltantes_aulas:
        raise ValueError(
            "Faltan columnas obligatorias en aulas.csv: "
            + ", ".join(faltantes_aulas)
        )

    # Normalizar el nombre de la columna de semanas.
    if "semanas_activas" not in df_clases.columns:

        if "semanas" in df_clases.columns:
            df_clases.rename(
                columns={"semanas": "semanas_activas"},
                inplace=True
            )

        else:
            raise ValueError(
                "Falta la columna 'semanas_activas' "
                "o su equivalente 'semanas' en clases.csv."
            )

    if (
        df_clases["semanas_activas"].isna().any()
        or (
            df_clases["semanas_activas"]
            .astype(str)
            .str.strip() == ""
        ).any()
    ):
        raise ValueError(
            "Hay sesiones sin semanas asignadas."
        )

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

    df_aulas["capacidad"] = pd.to_numeric(
        df_aulas["capacidad"],
        errors="raise"
    ).astype(int)

    # Comprobar valores.
    if not df_clases["curso"].between(1, 4).all():
        raise ValueError(
            "La columna curso debe contener valores entre 1 y 4."
        )

    if not df_clases["cuatrimestre"].between(1, 2).all():
        raise ValueError(
            "La columna cuatrimestre debe contener valores 1 o 2."
        )

    if (df_clases["duracion_horas"] <= 0).any():
        raise ValueError(
            "Hay sesiones con duración igual o inferior a cero."
        )

    if (df_clases["num_alumnos"] < 0).any():
        raise ValueError(
            "Hay sesiones con número de alumnos negativo."
        )

    if (df_aulas["capacidad"] <= 0).any():
        raise ValueError(
            "Hay aulas con capacidad igual o inferior a cero."
        )

    if df_clases["id_sesion"].isna().any():
        raise ValueError(
            "Hay sesiones sin identificador."
        )

    if df_aulas["id_aula"].isna().any():
        raise ValueError(
            "Hay aulas sin identificador."
        )

    if df_aulas["id_aula"].duplicated().any():
        duplicadas = df_aulas.loc[
            df_aulas["id_aula"].duplicated(),
            "id_aula"
        ].tolist()

        raise ValueError(
            f"Hay identificadores de aula duplicados: {duplicadas}"
        )

    return df_clases, df_aulas


# ---------------------------------------------------------
# DIVISIÓN DE SESIONES EN BLOQUES
# ---------------------------------------------------------

def dividir_en_bloques(df_clases):
    """
    Divide las horas semanales de cada sesión en bloques.

    Ejemplos:
        1 hora -> 1
        2 horas -> 2
        3 horas -> 2 + 1
        4 horas -> 2 + 2
        5 horas -> 2 + 2 + 1

    La duración representa horas semanales durante todas
    las semanas activas de la sesión.
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

    if not bloques:
        return pd.DataFrame()

    return pd.DataFrame(bloques).reset_index(drop=True)


# ---------------------------------------------------------
# FUNCIONES AUXILIARES DE HORARIO
# ---------------------------------------------------------

def obtener_hora(
    slot,
    duracion=1,
    horas_por_dia=HORAS_POR_DIA_NORMAL
):
    """Convierte una posición absoluta en su etiqueta horaria."""

    slot = int(slot)
    duracion = int(duracion)

    hora_idx = slot % horas_por_dia

    minutos_totales = (
        HORA_INICIO * 60
        + MINUTO_INICIO
        + hora_idx * 60
    )

    hora_inicio = minutos_totales // 60
    minuto_inicio = minutos_totales % 60

    minutos_finales = minutos_totales + duracion * 60

    hora_final = minutos_finales // 60
    minuto_final = minutos_finales % 60

    return (
        f"{hora_inicio:02d}:{minuto_inicio:02d}-"
        f"{hora_final:02d}:{minuto_final:02d}"
    )


def obtener_dia(
    slot,
    horas_por_dia=HORAS_POR_DIA_NORMAL
):
    """Obtiene el día correspondiente a una posición absoluta."""

    dia_idx = int(slot) // horas_por_dia

    if dia_idx < 0 or dia_idx >= len(DIAS):
        raise ValueError(
            f"Posición horaria fuera del calendario: {slot}"
        )

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

def resolver_modelo(
    df_bloques,
    df_aulas,
    horas_por_dia
):
    """
    Construye y resuelve el modelo para una jornada concreta.

    Devuelve:
        solver, estado, start_vars, end_vars, aula_asignada
    """

    numero_dias = len(DIAS)
    total_slots = numero_dias * horas_por_dia

    model = cp_model.CpModel()

    start_vars = []
    end_vars = []
    interval_vars = []

    # 1. Variables temporales.
    for i, fila in df_bloques.iterrows():

        duracion = int(fila["duracion_horas"])

        if duracion > horas_por_dia:
            raise ValueError(
                f"El bloque {fila['id_bloque']} dura "
                f"{duracion} horas y no cabe en una jornada "
                f"de {horas_por_dia} horas."
            )

        inicio = model.NewIntVar(
            0,
            total_slots - duracion,
            f"inicio_{i}"
        )

        fin = model.NewIntVar(
            duracion,
            total_slots,
            f"fin_{i}"
        )

        model.Add(fin == inicio + duracion)

        intervalo = model.NewIntervalVar(
            inicio,
            duracion,
            fin,
            f"intervalo_{i}"
        )

        # Impedir que un bloque cruce de un día al siguiente.
        hora_dentro_del_dia = model.NewIntVar(
            0,
            horas_por_dia - 1,
            f"hora_dia_{i}"
        )

        model.AddModuloEquality(
            hora_dentro_del_dia,
            inicio,
            horas_por_dia
        )

        model.Add(
            hora_dentro_del_dia + duracion
            <= horas_por_dia
        )

        start_vars.append(inicio)
        end_vars.append(fin)
        interval_vars.append(intervalo)

    # 2. Distribución de bloques de una misma sesión.
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
                numero_dias - 1,
                f"dia_sesion_{indice_original}_{indice}"
            )

            model.AddDivisionEquality(
                dia_bloque,
                start_vars[indice],
                horas_por_dia
            )

            dias_bloques.append(dia_bloque)

        # Los bloques de una misma sesión se distribuyen
        # en días diferentes.
        model.AddAllDifferent(dias_bloques)

    # 3. Restricciones de estudiantes.
    print("Aplicando restricciones de estudiantes...")

    aplicar_restriccion_estudiantes(
        model,
        df_bloques,
        interval_vars
    )

    # 4. Restricciones de jornada diaria.
    print("Aplicando restricciones de horario diario...")

    aplicar_restriccion_cambio_dia(
        model,
        start_vars,
        end_vars,
        horas_por_dia
    )

    # 5. Restricciones de profesores.
    print("Aplicando restricciones de profesores...")

    aplicar_restriccion_profesores(
        model,
        df_bloques,
        interval_vars
    )

    # 6. Restricciones de aulas.
    print("Aplicando restricciones de aulas...")

    aula_asignada = aplicar_restriccion_aulas(
        model,
        df_bloques,
        start_vars,
        end_vars,
        df_aulas
    )

    # 7. Preferencias de optimización.
    print("Aplicando preferencias de optimización...")

    aplicar_restricciones_blandas(
        model,
        start_vars,
        df_bloques,
        total_slots,
        aula_asignada,
        aula_preferida=AULA_PREFERIDA
    )

    # 8. Resolver.
    solver = cp_model.CpSolver()

    solver.parameters.max_time_in_seconds = (
        TIEMPO_MAXIMO_SOLVER
    )

    solver.parameters.num_search_workers = (
        NUM_TRABAJADORES_SOLVER
    )

    print("\nBuscando una solución...")

    estado = solver.Solve(model)

    return (
        solver,
        estado,
        start_vars,
        end_vars,
        aula_asignada
    )


# ---------------------------------------------------------
# GENERACIÓN DE UN HORARIO
# ---------------------------------------------------------

def generar_horario(
    curso,
    cuatrimestre,
    abrir_imagen=False
):
    """Genera el horario optimizado de un curso y cuatrimestre."""

    print("\n" + "=" * 65)
    print(
        f"GENERANDO HORARIO: {curso}º GIFM - "
        f"{cuatrimestre}º CUATRIMESTRE"
    )
    print("=" * 65)

    # Crear la carpeta de resultados.
    RUTA_RESULTADOS.mkdir(
        parents=True,
        exist_ok=True
    )

    # 1. Cargar datos.
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

    print(f"Sesiones originales: {len(df_filtrado)}")

    # 3. Dividir las sesiones en bloques.
    df_bloques = dividir_en_bloques(df_filtrado)

    if df_bloques.empty:
        print("No hay bloques horarios que programar.")
        return None

    print(
        "Bloques horarios que se deben colocar:",
        len(df_bloques)
    )

    # 4. Intentar primero la jornada normal.
    horas_por_dia = HORAS_POR_DIA_NORMAL

    print(
        f"\nProbando jornada ordinaria: "
        f"{HORA_INICIO:02d}:30-"
        f"{HORA_INICIO + horas_por_dia:02d}:30"
    )

    (
        solver,
        estado,
        start_vars,
        end_vars,
        aula_asignada
    ) = resolver_modelo(
        df_bloques,
        df_aulas,
        horas_por_dia
    )

    # 5. Si no hay solución, permitir ampliación únicamente
    # para 3.º GIFM - 2.º cuatrimestre.
    if (
        estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        and (curso, cuatrimestre) == HORARIO_AMPLIABLE
    ):

        print(
            "\nNo se ha encontrado solución con la jornada "
            "ordinaria."
        )

        horas_por_dia = HORAS_POR_DIA_AMPLIADO

        print(
            "Se vuelve a intentar con jornada ampliada: "
            f"{HORA_INICIO:02d}:30-"
            f"{HORA_INICIO + horas_por_dia:02d}:30"
        )

        (
            solver,
            estado,
            start_vars,
            end_vars,
            aula_asignada
        ) = resolver_modelo(
            df_bloques,
            df_aulas,
            horas_por_dia
        )

    # 6. Comprobar el resultado.
    if estado not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE
    ):

        print("\nNo se ha encontrado una solución factible.")

        print(
            "Estado del solver:",
            solver.StatusName(estado)
        )

        return None

    print("\n¡Horario generado correctamente!")

    print("Estado:", solver.StatusName(estado))

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

    if horas_por_dia == HORAS_POR_DIA_AMPLIADO:
        print(
            "AVISO: se ha utilizado la jornada ampliada "
            "hasta las 16:30."
        )

    # 7. Extraer resultados de CP-SAT.
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
            "Dia": obtener_dia(slot, horas_por_dia),
            "Hora": obtener_hora(
                slot,
                duracion,
                horas_por_dia
            ),
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

    # -----------------------------------------------------
    # 8. OPTIMIZACIÓN MEDIANTE RECOCIDO SIMULADO
    # -----------------------------------------------------

    print("\n" + "=" * 65)
    print("OPTIMIZACIÓN MEDIANTE RECOCIDO SIMULADO")
    print("=" * 65)

    resultado_sa = ejecutar_recocido_simulado(
        df_inicial=df_resultado,
        horas_por_dia=horas_por_dia,
        temperatura_inicial=10.0,
        temperatura_final=0.01,
        factor_enfriamiento=0.995,
        iteraciones_maximas=1000,
        semilla=42,
        mostrar_progreso=True
    )

    df_resultado_sa = resultado_sa["horario"].copy()

    # Actualizar las etiquetas de día y hora después
    # de los movimientos realizados por la metaheurística.
    df_resultado_sa["Dia"] = df_resultado_sa["Slot"].apply(
        lambda slot: obtener_dia(slot, horas_por_dia)
    )

    df_resultado_sa["Hora"] = df_resultado_sa.apply(
        lambda fila: obtener_hora(
            fila["Slot"],
            fila["Duracion_horas"],
            horas_por_dia
        ),
        axis=1
    )

    df_resultado_sa = df_resultado_sa.sort_values(
        by=["Slot", "Asignatura"]
    ).reset_index(drop=True)

    # Guardar horario optimizado en CSV.
    nombre_csv_sa = (
        f"horario_{curso}GIFM_{cuatrimestre}cuatri_recocido.csv"
    )

    ruta_csv_sa = RUTA_RESULTADOS / nombre_csv_sa

    df_resultado_sa.to_csv(
        ruta_csv_sa,
        index=False,
        encoding="utf-8-sig"
    )

    # Guardar horario optimizado en PNG.
    nombre_png_sa = (
        f"horario_{curso}GIFM_{cuatrimestre}cuatri_recocido.png"
    )

    ruta_png_sa = RUTA_RESULTADOS / nombre_png_sa

    titulo_sa = (
        f"HORARIO CON RECOCIDO SIMULADO — {curso}º GIFM "
        f"({cuatrimestre}º CUATRIMESTRE)"
    )

    exportar_horario_png(
        df_resultado_sa,
        ruta_salida=str(ruta_png_sa),
        abrir_al_terminar=False,
        titulo=titulo_sa,
        horas_por_dia=horas_por_dia
    )

    # Guardar estadísticas para comparar algoritmos.
    estadisticas = pd.DataFrame([{
        "Curso": curso,
        "Cuatrimestre": cuatrimestre,
        "Algoritmo": "Recocido simulado",
        "Coste_inicial": resultado_sa["coste_inicial"],
        "Mejor_coste": resultado_sa["mejor_coste"],
        "Iteraciones": resultado_sa["iteraciones"],
        "Aceptados": resultado_sa["aceptados"],
        "Mejoras": resultado_sa["mejoras"],
        "Tiempo_segundos": resultado_sa["tiempo"],
        "Horario_valido": resultado_sa["valido"]
    }])

    nombre_estadisticas = (
        f"estadisticas_recocido_{curso}GIFM_"
        f"{cuatrimestre}cuatri.csv"
    )

    estadisticas.to_csv(
        RUTA_RESULTADOS / nombre_estadisticas,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nResultados del recocido simulado guardados.")
    print("Horario CSV:", ruta_csv_sa)
    print("Horario PNG:", ruta_png_sa)

    # -----------------------------------------------------
    # 9. MOSTRAR RESUMEN DE CP-SAT
    # -----------------------------------------------------

    print("\nResumen del horario generado por CP-SAT:")

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

    # -----------------------------------------------------
    # 10. EXPORTAR HORARIO ORIGINAL DE CP-SAT
    # -----------------------------------------------------

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
        titulo=titulo,
        horas_por_dia=horas_por_dia
    )

    return df_resultado


# ---------------------------------------------------------
# GENERAR LOS OCHO HORARIOS
# ---------------------------------------------------------

def generar_todos_los_horarios():
    """Genera los cuatro cursos y sus dos cuatrimestres."""

    resultados = {}

    total = 8
    contador = 0

    for curso in range(1, 5):

        for cuatrimestre in range(1, 3):

            contador += 1

            print(f"\nPROGRESO: {contador}/{total}")

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

                print(f"{type(error).__name__}: {error}")

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
