
import random
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

    from .metaheuristica.evaluacion import (
        comprobar_restricciones
    )

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

    from metaheuristica.evaluacion import (
        comprobar_restricciones
    )

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

HORAS_POR_DIA_NORMAL = 6
HORAS_POR_DIA_AMPLIADO = 8

HORARIO_AMPLIABLE = (3, 2)

TIEMPO_MAXIMO_SOLVER = 120
NUM_TRABAJADORES_SOLVER = 8

AULA_PREFERIDA = "A3-1"

SEMILLA_RECOCIDO = 42
MAX_REINICIOS_INICIAL = 100


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

    # Normalizar la columna de semanas.
    if "semanas_activas" not in df_clases.columns:

        if "semanas" in df_clases.columns:
            df_clases.rename(
                columns={"semanas": "semanas_activas"},
                inplace=True
            )

        else:
            raise ValueError(
                "Falta la columna 'semanas_activas' "
                "o su equivalente 'semanas'."
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
    Divide las sesiones en bloques de dos horas y, si sobra,
    un bloque de una hora.
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
# CONSTRUCCIÓN DE UNA SOLUCIÓN INICIAL INDEPENDIENTE
# ---------------------------------------------------------

def generar_solucion_inicial_aleatoria(
    df_bloques,
    df_aulas,
    horas_por_dia=HORAS_POR_DIA_NORMAL,
    semilla=SEMILLA_RECOCIDO,
    max_reinicios=MAX_REINICIOS_INICIAL
):
    """
    Construye un horario inicial sin utilizar CP-SAT.

    Asigna cada bloque a un slot y un aula compatibles.
    Comprueba las restricciones duras antes de aceptar
    cada asignación.

    Si una construcción se atasca, comienza otra.
    """

    generador = random.Random(semilla)

    total_slots = len(DIAS) * horas_por_dia

    aulas_compatibles = {}

    # Preparar las aulas compatibles con cada bloque.
    for indice, bloque in df_bloques.iterrows():

        tipo_requerido = str(
            bloque["tipo_aula_requerida"]
        ).strip().lower()

        num_alumnos = int(bloque["num_alumnos"])

        compatibles = df_aulas[
            (
                df_aulas["tipo"]
                .astype(str)
                .str.strip()
                .str.lower()
                == tipo_requerido
            )
            &
            (df_aulas["capacidad"] >= num_alumnos)
        ]["id_aula"].astype(str).tolist()

        if not compatibles:
            raise ValueError(
                f"No hay aulas compatibles para "
                f"{bloque['id_bloque']}."
            )

        aulas_compatibles[indice] = compatibles

    indices = list(df_bloques.index)

    # Construcciones con distintos órdenes aleatorios.
    for intento in range(1, max_reinicios + 1):

        orden = indices.copy()
        generador.shuffle(orden)

        # Priorizar bloques largos.
        orden.sort(
            key=lambda i: int(
                df_bloques.loc[i, "duracion_horas"]
            ),
            reverse=True
        )

        horario = []
        construccion_completa = True

        for indice in orden:

            bloque = df_bloques.loc[indice]

            duracion = int(bloque["duracion_horas"])

            candidatos = []

            for slot in range(total_slots):

                hora_dia = slot % horas_por_dia

                if hora_dia + duracion > horas_por_dia:
                    continue

                dia = slot // horas_por_dia

                for aula in aulas_compatibles[indice]:
                    candidatos.append((slot, aula, dia))

            generador.shuffle(candidatos)

            colocado = False

            for slot, aula, dia in candidatos:

                # Los bloques de una misma sesión deben
                # impartirse en días diferentes.
                misma_sesion = any(
                    str(fila["Sesion_original"])
                    == str(bloque["id_sesion"])
                    and int(fila["Slot"]) // horas_por_dia == dia
                    for fila in horario
                )

                if misma_sesion:
                    continue

                semanas = bloque["semanas_activas"]

                nueva_fila = {
                    "Slot": slot,
                    "Sesion": bloque["id_bloque"],
                    "Sesion_original": bloque["id_sesion"],
                    "Asignatura": bloque["asignatura"],
                    "Tipo": bloque["tipo"],
                    "Grupo": bloque["grupo"],
                    "Dia": obtener_dia(slot, horas_por_dia),
                    "Hora": obtener_hora(
                        slot,
                        duracion,
                        horas_por_dia
                    ),
                    "Duracion": f"{duracion}h",
                    "Duracion_horas": duracion,
                    "Aula": aula,
                    "Profesor": bloque["profesor"],
                    "Semanas_activas": str(semanas),
                    "tipo_aula_requerida": bloque[
                        "tipo_aula_requerida"
                    ],
                    "num_alumnos": int(bloque["num_alumnos"])
                }

                horario_prueba = pd.DataFrame(
                    horario + [nueva_fila]
                )

                valido, _ = comprobar_restricciones(
                    horario_prueba,
                    horas_por_dia
                )

                if valido:
                    horario.append(nueva_fila)
                    colocado = True
                    break

            if not colocado:
                construccion_completa = False
                break

        if construccion_completa:

            resultado = pd.DataFrame(horario)

            resultado = resultado.sort_values(
                by=["Slot", "Asignatura"]
            ).reset_index(drop=True)

            valido, errores = comprobar_restricciones(
                resultado,
                horas_por_dia
            )

            if not valido:
                continue

            print(
                "Solución inicial independiente construida "
                f"en el intento {intento}."
            )

            return resultado

    raise RuntimeError(
        "No se pudo construir un horario inicial válido "
        f"después de {max_reinicios} intentos."
    )


# ---------------------------------------------------------
# CONSTRUCCIÓN Y RESOLUCIÓN DEL MODELO CP-SAT
# ---------------------------------------------------------

def resolver_modelo(
    df_bloques,
    df_aulas,
    horas_por_dia
):
    """Construye y resuelve el modelo CP-SAT."""

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
                f"{duracion} horas y no cabe en una jornada."
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

        # Impedir que un bloque cruce de día.
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

    # 2. Bloques de una misma sesión en días diferentes.
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

        model.AddAllDifferent(dias_bloques)

    # 3. Restricciones de estudiantes.
    print("Aplicando restricciones de estudiantes...")

    aplicar_restriccion_estudiantes(
        model,
        df_bloques,
        interval_vars
    )

    # 4. Restricciones de jornada.
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

    # 7. Preferencias.
    print("Aplicando preferencias de optimización...")

    aplicar_restricciones_blandas(
        model,
        start_vars,
        df_bloques,
        total_slots,
        aula_asignada,
        aula_preferida=AULA_PREFERIDA,
        horas_por_dia=horas_por_dia
    )

    # 8. Resolver.
    solver = cp_model.CpSolver()

    solver.parameters.max_time_in_seconds = (
        TIEMPO_MAXIMO_SOLVER
    )

    solver.parameters.num_search_workers = (
        NUM_TRABAJADORES_SOLVER
    )

    print("\nBuscando una solución con CP-SAT...")

    estado = solver.Solve(model)

    return (
        solver,
        estado,
        start_vars,
        end_vars,
        aula_asignada
    )


# ---------------------------------------------------------
# EXTRAER RESULTADO DE CP-SAT
# ---------------------------------------------------------

def extraer_horario_cp_sat(
    solver,
    start_vars,
    aula_asignada,
    df_bloques,
    horas_por_dia
):
    """Convierte la solución de CP-SAT en un DataFrame."""

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
            "Semanas_activas": str(semanas),
            "tipo_aula_requerida": fila[
                "tipo_aula_requerida"
            ],
            "num_alumnos": int(fila["num_alumnos"])
        })

    resultado = pd.DataFrame(resultados)

    return resultado.sort_values(
        by=["Slot", "Asignatura"]
    ).reset_index(drop=True)


# ---------------------------------------------------------
# ACTUALIZAR ETIQUETAS DE UN HORARIO
# ---------------------------------------------------------

def actualizar_etiquetas_horario(
    df,
    horas_por_dia
):
    """Actualiza los días y las horas después de los movimientos."""

    resultado = df.copy()

    resultado["Dia"] = resultado["Slot"].apply(
        lambda slot: obtener_dia(slot, horas_por_dia)
    )

    resultado["Hora"] = resultado.apply(
        lambda fila: obtener_hora(
            fila["Slot"],
            fila["Duracion_horas"],
            horas_por_dia
        ),
        axis=1
    )

    return resultado.sort_values(
        by=["Slot", "Asignatura"]
    ).reset_index(drop=True)


# ---------------------------------------------------------
# GUARDAR HORARIO
# ---------------------------------------------------------

def guardar_horario(
    df,
    curso,
    cuatrimestre,
    algoritmo,
    horas_por_dia
):
    """Guarda un horario en CSV y PNG."""

    RUTA_RESULTADOS.mkdir(
        parents=True,
        exist_ok=True
    )

    nombre_base = (
        f"horario_{curso}GIFM_{cuatrimestre}cuatri"
    )

    if algoritmo == "recocido":
        nombre_base += "_recocido"

    ruta_csv = RUTA_RESULTADOS / f"{nombre_base}.csv"
    ruta_png = RUTA_RESULTADOS / f"{nombre_base}.png"

    titulo = (
        f"HORARIO — {curso}º GIFM "
        f"({cuatrimestre}º CUATRIMESTRE)"
    )

    if algoritmo == "recocido":
        titulo += " — RECOCIDO SIMULADO"
    else:
        titulo += " — CP-SAT"

    df.to_csv(
        ruta_csv,
        index=False,
        encoding="utf-8-sig"
    )

    exportar_horario_png(
        df,
        ruta_salida=str(ruta_png),
        abrir_al_terminar=False,
        titulo=titulo,
        horas_por_dia=horas_por_dia
    )

    print("CSV guardado:", ruta_csv)
    print("PNG guardado:", ruta_png)

    return ruta_csv, ruta_png


# ---------------------------------------------------------
# GENERACIÓN DE UN HORARIO
# ---------------------------------------------------------

def generar_horario(
    curso,
    cuatrimestre,
    abrir_imagen=False
):
    """
    Genera un horario mediante dos métodos independientes:

    1. CP-SAT.
    2. Recocido simulado con solución inicial propia.
    """

    print("\n" + "=" * 65)
    print(
        f"GENERANDO HORARIOS: {curso}º GIFM - "
        f"{cuatrimestre}º CUATRIMESTRE"
    )
    print("=" * 65)

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
    ].copy().reset_index(drop=True)

    if df_filtrado.empty:
        print("No hay sesiones para este curso y cuatrimestre.")
        return None

    print("Sesiones originales:", len(df_filtrado))

    # 3. Dividir en bloques.
    df_bloques = dividir_en_bloques(df_filtrado)

    if df_bloques.empty:
        print("No hay bloques que programar.")
        return None

    print("Bloques horarios:", len(df_bloques))

    # -----------------------------------------------------
    # PARTE A: CP-SAT
    # -----------------------------------------------------

    print("\n" + "=" * 65)
    print("PRIMER MÉTODO: CP-SAT")
    print("=" * 65)

    horas_cp = HORAS_POR_DIA_NORMAL
    df_resultado_cp = None
    tiempo_cp = None
    estado_cp_nombre = "No resuelto"

    try:

        resultado_modelo = resolver_modelo(
            df_bloques,
            df_aulas,
            horas_cp
        )

        (
            solver,
            estado,
            start_vars,
            end_vars,
            aula_asignada
        ) = resultado_modelo

        # Ampliación excepcional para 3º GIFM - 2º cuatri.
        if (
            estado not in (
                cp_model.OPTIMAL,
                cp_model.FEASIBLE
            )
            and (curso, cuatrimestre) == HORARIO_AMPLIABLE
        ):

            print(
                "\nNo se encontró solución con jornada normal."
            )

            horas_cp = HORAS_POR_DIA_AMPLIADO

            resultado_modelo = resolver_modelo(
                df_bloques,
                df_aulas,
                horas_cp
            )

            (
                solver,
                estado,
                start_vars,
                end_vars,
                aula_asignada
            ) = resultado_modelo

        estado_cp_nombre = solver.StatusName(estado)
        tiempo_cp = solver.WallTime()

        print("\nEstado CP-SAT:", estado_cp_nombre)
        print("Tiempo:", round(tiempo_cp, 2), "segundos")

        if estado in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE
        ):

            df_resultado_cp = extraer_horario_cp_sat(
                solver,
                start_vars,
                aula_asignada,
                df_bloques,
                horas_cp
            )

            guardar_horario(
                df_resultado_cp,
                curso,
                cuatrimestre,
                "cp",
                horas_cp
            )

            if estado == cp_model.OPTIMAL:
                print("CP-SAT ha encontrado una solución óptima.")
            else:
                print("CP-SAT ha encontrado una solución factible.")

        else:
            print("CP-SAT no ha encontrado una solución factible.")

    except Exception as error:

        print("Error durante CP-SAT:")
        print(f"{type(error).__name__}: {error}")

    # -----------------------------------------------------
    # PARTE B: RECOCIDO SIMULADO INDEPENDIENTE
    # -----------------------------------------------------

    print("\n" + "=" * 65)
    print("SEGUNDO MÉTODO: RECOCIDO SIMULADO")
    print("=" * 65)

    # Elegir jornada para el recocido.
    # Se utiliza la jornada de CP-SAT si se ha encontrado
    # una solución. En caso contrario, se prueba la normal.
    horas_sa = (
        horas_cp
        if df_resultado_cp is not None
        else HORAS_POR_DIA_NORMAL
    )

    df_inicial_sa = None

    try:

        print(
            "\nConstruyendo solución inicial independiente..."
        )

        df_inicial_sa = generar_solucion_inicial_aleatoria(
            df_bloques=df_bloques,
            df_aulas=df_aulas,
            horas_por_dia=horas_sa,
            semilla=SEMILLA_RECOCIDO,
            max_reinicios=MAX_REINICIOS_INICIAL
        )

    except Exception as error:

        print("\nNo se pudo construir la solución inicial:")
        print(f"{type(error).__name__}: {error}")

        # Si la jornada normal no funciona y este es el
        # único curso ampliable, intentar con jornada ampliada.
        if (
            df_inicial_sa is None
            and horas_sa == HORAS_POR_DIA_NORMAL
            and (curso, cuatrimestre) == HORARIO_AMPLIABLE
        ):

            print(
                "\nReintentando la solución inicial "
                "con jornada ampliada..."
            )

            try:

                horas_sa = HORAS_POR_DIA_AMPLIADO

                df_inicial_sa = (
                    generar_solucion_inicial_aleatoria(
                        df_bloques=df_bloques,
                        df_aulas=df_aulas,
                        horas_por_dia=horas_sa,
                        semilla=SEMILLA_RECOCIDO,
                        max_reinicios=MAX_REINICIOS_INICIAL
                    )
                )

            except Exception as segundo_error:

                print(
                    "Tampoco se pudo construir con jornada "
                    "ampliada:"
                )

                print(
                    f"{type(segundo_error).__name__}: "
                    f"{segundo_error}"
                )

    resultado_sa = None
    df_resultado_sa = None

    if df_inicial_sa is not None:

        valido, errores = comprobar_restricciones(
            df_inicial_sa,
            horas_sa
        )

        print("\nComprobación de solución inicial:", valido)

        if not valido:
            print("Errores:", errores)

        else:

            print(
                "\nEjecutando recocido simulado "
                "desde su propia solución inicial..."
            )

            try:

                resultado_sa = ejecutar_recocido_simulado(
                    df_inicial=df_inicial_sa,
                    horas_por_dia=horas_sa,
                    temperatura_inicial=10.0,
                    temperatura_final=0.01,
                    factor_enfriamiento=0.995,
                    iteraciones_maximas=1000,
                    semilla=SEMILLA_RECOCIDO,
                    mostrar_progreso=True,
                    df_aulas=df_aulas
                )

                df_resultado_sa = actualizar_etiquetas_horario(
                    resultado_sa["horario"],
                    horas_sa
                )

                guardar_horario(
                    df_resultado_sa,
                    curso,
                    cuatrimestre,
                    "recocido",
                    horas_sa
                )

                estadisticas = pd.DataFrame([{
                    "Curso": curso,
                    "Cuatrimestre": cuatrimestre,
                    "Algoritmo": "Recocido simulado independiente",
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

                print("\nRecocido simulado finalizado.")
                print("Coste inicial:", resultado_sa["coste_inicial"])
                print("Mejor coste:", resultado_sa["mejor_coste"])
                print("Tiempo:", resultado_sa["tiempo"])
                print("Horario válido:", resultado_sa["valido"])

            except Exception as error:

                print("\nError durante el recocido simulado:")
                print(f"{type(error).__name__}: {error}")

    else:
        print(
            "\nNo se ejecuta el recocido porque no se "
            "ha conseguido una solución inicial."
        )

    # -----------------------------------------------------
    # RESUMEN DEL CURSO
    # -----------------------------------------------------

    print("\n" + "=" * 65)
    print(
        f"RESUMEN: {curso}º GIFM - "
        f"{cuatrimestre}º CUATRIMESTRE"
    )
    print("=" * 65)

    print("CP-SAT:", estado_cp_nombre)

    if df_resultado_cp is not None:
        print("Horario CP-SAT generado correctamente.")
    else:
        print("No se ha generado horario CP-SAT.")

    if resultado_sa is not None:
        print("Recocido simulado:", resultado_sa["valido"])
    else:
        print("No se ha generado horario mediante recocido.")

    if df_resultado_cp is not None:

        print("\nHorario obtenido por CP-SAT:")

        print(
            df_resultado_cp[
                [
                    "Asignatura",
                    "Tipo",
                    "Grupo",
                    "Dia",
                    "Hora",
                    "Aula"
                ]
            ].to_string(index=False)
        )

    if df_resultado_sa is not None:

        print("\nHorario obtenido por recocido simulado:")

        print(
            df_resultado_sa[
                [
                    "Asignatura",
                    "Tipo",
                    "Grupo",
                    "Dia",
                    "Hora",
                    "Aula"
                ]
            ].to_string(index=False)
        )

    # Devolver el resultado de CP-SAT si existe;
    # si no, devolver el del recocido simulado.
    if df_resultado_cp is not None:
        return df_resultado_cp

    return df_resultado_sa


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
