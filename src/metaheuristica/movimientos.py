

import random

from .evaluacion import (
    comprobar_restricciones,
    obtener_duracion,
)


# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

NUM_INTENTOS_MOVIMIENTO = 40


# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def obtener_slot_aleatorio(horas_por_dia, generador=None):
    """
    Genera un slot inicial aleatorio dentro de una semana.
    """

    if generador is None:
        generador = random

    total_slots = 5 * horas_por_dia

    return generador.randrange(total_slots)


def posicion_valida(slot, duracion, horas_por_dia):
    """
    Comprueba que una actividad cabe dentro de un día.
    """

    if slot < 0:
        return False

    if slot + duracion > 5 * horas_por_dia:
        return False

    hora_dentro_del_dia = slot % horas_por_dia

    return hora_dentro_del_dia + duracion <= horas_por_dia


def misma_sesion_original(sesion_a, sesion_b):
    """
    Comprueba si dos bloques pertenecen a la misma sesión.
    """

    if sesion_a is None or sesion_b is None:
        return False

    try:
        return bool(sesion_a == sesion_b)
    except (TypeError, ValueError):
        return False


def preparar_datos_movimientos(df):
    """
    Prepara los datos que se necesitan para generar movimientos.

    Evita consultar repetidamente las filas del DataFrame
    y calcular las duraciones en cada intento.
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


# ---------------------------------------------------------
# MOVIMIENTO 1: CAMBIAR UNA ACTIVIDAD DE POSICIÓN
# ---------------------------------------------------------

def mover_actividad(
    df,
    horas_por_dia=6,
    max_intentos=NUM_INTENTOS_MOVIMIENTO,
    generador=None
):
    """
    Intenta cambiar una actividad a otro slot aleatorio.

    Devuelve:
        Un nuevo DataFrame si encuentra un movimiento válido.
        None si no encuentra ningún movimiento válido.
    """

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

        # Solo copiamos el DataFrame cuando el movimiento
        # ya ha superado las comprobaciones iniciales.
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
    generador=None
):
    """
    Intenta intercambiar las posiciones de dos actividades.

    Solo intercambia actividades con la misma duración,
    para conservar sus intervalos horarios.
    """

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

        # Solo intercambiamos actividades de igual duración.
        if duracion_a != duracion_b:
            continue

        # No intercambiamos bloques de una misma sesión.
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

        # Copiamos únicamente cuando el intercambio
        # ha superado las comprobaciones iniciales.
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
# GENERAR UN HORARIO VECINO
# ---------------------------------------------------------

def generar_vecino(
    df,
    horas_por_dia=6,
    generador=None
):
    """
    Genera un horario vecino utilizando uno de los movimientos
    disponibles.

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

    generador.shuffle(movimientos)

    for movimiento in movimientos:

        nuevo_df = movimiento(
            df,
            horas_por_dia,
            generador=generador
        )

        if nuevo_df is not None:
            return nuevo_df

    return None
