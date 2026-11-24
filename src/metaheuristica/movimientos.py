
import random

import pandas as pd

from .evaluacion import (
    comprobar_restricciones,
    obtener_duracion,
    obtener_semanas,
    semanas_coincidentes,
    normalizar_texto,
)


# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

NUM_INTENTOS_MOVIMIENTO = 40


# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def obtener_slot_aleatorio(horas_por_dia, generador=None):
    """Genera un slot inicial aleatorio dentro de una semana."""

    if generador is None:
        generador = random

    total_slots = 5 * horas_por_dia

    return generador.randrange(total_slots)


def posicion_valida(slot, duracion, horas_por_dia):
    """Comprueba que una actividad cabe dentro de un día."""

    if slot < 0:
        return False

    if slot + duracion > 5 * horas_por_dia:
        return False

    hora_dentro_del_dia = slot % horas_por_dia

    return hora_dentro_del_dia + duracion <= horas_por_dia


def misma_sesion_original(sesion_a, sesion_b):
    """Comprueba si dos bloques pertenecen a la misma sesión."""

    if sesion_a is None or sesion_b is None:
        return False

    try:
        return bool(sesion_a == sesion_b)
    except (TypeError, ValueError):
        return False


def preparar_datos_movimientos(df):
    """
    Prepara los datos necesarios para generar movimientos.
    """

    indices = list(df.index)

    duraciones = {}
    sesiones = {}
    slots = {}

    tiene_sesion = "Sesion_original" in df.columns

    for indice in indices:

        fila = df.loc[indice]

        duraciones[indice] = obtener_duracion(fila)
        slots[indice] = int(fila["Slot"])

        if tiene_sesion:
            sesiones[indice] = fila["Sesion_original"]
        else:
            sesiones[indice] = None

    return indices, duraciones, sesiones, slots


def preparar_catalogo_aulas(df_aulas):
    """
    Comprueba y prepara el catálogo de aulas.

    Devuelve un diccionario con identificador, tipo y capacidad.
    """

    if df_aulas is None or df_aulas.empty:
        return {}

    columnas = [
        "id_aula",
        "tipo",
        "capacidad"
    ]

    for columna in columnas:
        if columna not in df_aulas.columns:
            raise ValueError(
                f"Falta la columna {columna} en el catálogo de aulas."
            )

    catalogo = {}

    for _, fila in df_aulas.iterrows():

        aula_id = str(fila["id_aula"]).strip()

        if not aula_id:
            continue

        catalogo[aula_id] = {
            "tipo": normalizar_texto(fila["tipo"]),
            "capacidad": int(fila["capacidad"])
        }

    return catalogo


def obtener_aulas_compatibles(fila, catalogo):
    """Devuelve las aulas que cumplen tipo y capacidad."""

    tipo_requerido = normalizar_texto(
        fila.get("tipo_aula_requerida", "")
    )

    num_alumnos = int(fila.get("num_alumnos", 0))

    compatibles = []

    for aula_id, datos in catalogo.items():

        if datos["tipo"] != tipo_requerido:
            continue

        if datos["capacidad"] < num_alumnos:
            continue

        compatibles.append(aula_id)

    return compatibles


def aula_disponible(
    df,
    indice,
    nueva_aula,
    horas_por_dia=6
):
    """
    Comprueba si el aula está libre para una actividad.

    Tiene en cuenta:
    - Día.
    - Solapamiento horario.
    - Coincidencia de semanas.
    """

    actividad = df.loc[indice]

    inicio_a = int(actividad["Slot"])
    duracion_a = obtener_duracion(actividad)

    dia_a = inicio_a // horas_por_dia

    semanas_a = obtener_semanas(
        actividad["Semanas_activas"]
    )

    for otro_indice, otra in df.iterrows():

        if otro_indice == indice:
            continue

        aula_actual = str(
            otra["Aula"]
        ).strip()

        if aula_actual != nueva_aula:
            continue

        inicio_b = int(otra["Slot"])
        duracion_b = obtener_duracion(otra)

        dia_b = inicio_b // horas_por_dia

        if dia_a != dia_b:
            continue

        semanas_b = obtener_semanas(
            otra["Semanas_activas"]
        )

        if not semanas_coincidentes(
            semanas_a,
            semanas_b
        ):
            continue

        final_a = inicio_a + duracion_a
        final_b = inicio_b + duracion_b

        if (
            inicio_a < final_b
            and inicio_b < final_a
        ):
            return False

    return True


# ---------------------------------------------------------
# MOVIMIENTO 1: CAMBIAR UNA ACTIVIDAD DE POSICIÓN
# ---------------------------------------------------------

def mover_actividad(
    df,
    horas_por_dia=6,
    max_intentos=NUM_INTENTOS_MOVIMIENTO,
    generador=None,
    df_aulas=None
):
    """Intenta cambiar una actividad a otro slot aleatorio."""

    if df is None or len(df) == 0:
        return None

    if generador is None:
        generador = random

    try:
        indices, duraciones, _, slots = preparar_datos_movimientos(df)
    except (ValueError, TypeError, KeyError):
        return None

    for _ in range(max_intentos):

        indice = generador.choice(indices)

        duracion = duraciones[indice]
        slot_actual = slots[indice]

        nuevo_slot = obtener_slot_aleatorio(
            horas_por_dia,
            generador
        )

        if nuevo_slot == slot_actual:
            continue

        if not posicion_valida(
            nuevo_slot,
            duracion,
            horas_por_dia
        ):
            continue

        nuevo_df = df.copy(deep=True)

        nuevo_df.at[indice, "Slot"] = nuevo_slot

        valido, _ = comprobar_restricciones(
            nuevo_df,
            horas_por_dia
        )

        if valido:
            return nuevo_df

    return None


# ---------------------------------------------------------
# MOVIMIENTO 2: INTERCAMBIAR DOS ACTIVIDADES
# ---------------------------------------------------------

def intercambiar_actividades(
    df,
    horas_por_dia=6,
    max_intentos=NUM_INTENTOS_MOVIMIENTO,
    generador=None,
    df_aulas=None
):
    """Intenta intercambiar las posiciones de dos actividades."""

    if df is None or len(df) < 2:
        return None

    if generador is None:
        generador = random

    try:
        indices, duraciones, sesiones, slots = preparar_datos_movimientos(df)
    except (ValueError, TypeError, KeyError):
        return None

    for _ in range(max_intentos):

        indice_a, indice_b = generador.sample(indices, 2)

        duracion_a = duraciones[indice_a]
        duracion_b = duraciones[indice_b]

        if duracion_a != duracion_b:
            continue

        if misma_sesion_original(
            sesiones[indice_a],
            sesiones[indice_b]
        ):
            continue

        slot_a = slots[indice_a]
        slot_b = slots[indice_b]

        if slot_a == slot_b:
            continue

        if not posicion_valida(
            slot_b,
            duracion_a,
            horas_por_dia
        ):
            continue

        if not posicion_valida(
            slot_a,
            duracion_b,
            horas_por_dia
        ):
            continue

        nuevo_df = df.copy(deep=True)

        nuevo_df.at[indice_a, "Slot"] = slot_b
        nuevo_df.at[indice_b, "Slot"] = slot_a

        valido, _ = comprobar_restricciones(
            nuevo_df,
            horas_por_dia
        )

        if valido:
            return nuevo_df

    return None


# ---------------------------------------------------------
# MOVIMIENTO 3: CAMBIAR EL AULA DE UNA ACTIVIDAD
# ---------------------------------------------------------

def cambiar_aula(
    df,
    df_aulas,
    horas_por_dia=6,
    max_intentos=NUM_INTENTOS_MOVIMIENTO,
    generador=None
):
    """
    Intenta asignar otra aula a una actividad.

    Comprueba:
    - Tipo de aula.
    - Capacidad.
    - Disponibilidad horaria.
    - Coincidencia de semanas.
    """

    if df is None or df.empty:
        return None

    if df_aulas is None or df_aulas.empty:
        return None

    if generador is None:
        generador = random

    try:
        catalogo = preparar_catalogo_aulas(df_aulas)
    except (ValueError, TypeError, KeyError):
        return None

    if not catalogo:
        return None

    indices = list(df.index)

    for _ in range(max_intentos):

        indice = generador.choice(indices)

        fila = df.loc[indice]

        aula_actual = str(
            fila["Aula"]
        ).strip()

        compatibles = obtener_aulas_compatibles(
            fila,
            catalogo
        )

        alternativas = [
            aula
            for aula in compatibles
            if aula != aula_actual
        ]

        if not alternativas:
            continue

        generador.shuffle(alternativas)

        for nueva_aula in alternativas:

            if not aula_disponible(
                df,
                indice,
                nueva_aula,
                horas_por_dia
            ):
                continue

            nuevo_df = df.copy(deep=True)

            nuevo_df.at[indice, "Aula"] = nueva_aula

            valido, _ = comprobar_restricciones(
                nuevo_df,
                horas_por_dia
            )

            if valido:
                return nuevo_df

    return None


# ---------------------------------------------------------
# GENERAR UN HORARIO VECINO
# ---------------------------------------------------------

def generar_vecino(
    df,
    horas_por_dia=6,
    generador=None,
    df_aulas=None
):
    """
    Genera un horario vecino utilizando uno de los tres
    movimientos disponibles.

    Los movimientos se eligen aleatoriamente.
    """

    if df is None or len(df) == 0:
        return None

    if generador is None:
        generador = random

    movimientos = [
        mover_actividad,
        intercambiar_actividades,
    ]

    if df_aulas is not None:
        movimientos.append(cambiar_aula)

    generador.shuffle(movimientos)

    for movimiento in movimientos:

        if movimiento == cambiar_aula:

            nuevo_df = movimiento(
                df,
                df_aulas,
                horas_por_dia=horas_por_dia,
                generador=generador
            )

        else:

            nuevo_df = movimiento(
                df,
                horas_por_dia=horas_por_dia,
                generador=generador
            )

        if nuevo_df is not None:
            return nuevo_df

    return None
