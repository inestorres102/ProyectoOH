
import ast
import re
import unicodedata

import pandas as pd


# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

AULA_PREFERIDA = "A3-1"

PENALIZACION_VIERNES = 10
PENALIZACION_AULA_TEORIA = 2


# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def normalizar_texto(valor):
    """Normaliza un texto para poder compararlo."""

    if valor is None or pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


def obtener_valor(fila, columna, defecto=None):
    """Obtiene un valor tanto de una Serie como de un diccionario."""

    if isinstance(fila, dict):
        return fila.get(columna, defecto)

    return fila.get(columna, defecto)


def obtener_duracion(fila):
    """
    Obtiene la duración numérica de una actividad.

    Admite:
    - 2
    - 2.0
    - "2"
    - "2h"
    - "1h"
    """

    valor = obtener_valor(fila, "Duracion_horas")

    if valor is not None and pd.notna(valor):
        return int(float(valor))

    valor = obtener_valor(fila, "Duracion")

    if valor is None or pd.isna(valor):
        raise ValueError(
            "La duración de una actividad está vacía."
        )

    try:
        return int(float(valor))
    except (ValueError, TypeError):
        pass

    coincidencia = re.fullmatch(
        r"\s*(\d+(?:[.,]\d+)?)\s*h\s*",
        str(valor).strip().lower()
    )

    if coincidencia:
        return int(
            float(
                coincidencia.group(1).replace(",", ".")
            )
        )

    raise ValueError(f"Duración no válida: {valor}")


def obtener_semanas(valor):
    """
    Convierte las semanas activas en un conjunto de enteros.

    Admite:
    - '1-5,8,10-12'
    - '1,9-15'
    - '[1, 2, 3, 4]'
    - listas y tuplas de números.

    Si no hay información, devuelve None.
    """

    if valor is None:
        return None

    if isinstance(valor, float) and pd.isna(valor):
        return None

    if isinstance(valor, (list, tuple, set)):
        return {int(x) for x in valor}

    texto = str(valor).strip()

    if not texto or texto.lower() in {"nan", "none"}:
        return None

    if texto.startswith("[") and texto.endswith("]"):

        try:
            elementos = ast.literal_eval(texto)

            return {
                int(x)
                for x in elementos
            }

        except (ValueError, SyntaxError, TypeError):
            pass

    resultado = set()

    for parte in texto.split(","):

        parte = parte.strip()

        if not parte:
            continue

        coincidencia = re.fullmatch(
            r"(\d+)\s*-\s*(\d+)",
            parte
        )

        if coincidencia:

            inicio = int(coincidencia.group(1))
            final = int(coincidencia.group(2))

            if final < inicio:
                raise ValueError(
                    f"Rango de semanas no válido: {parte}"
                )

            resultado.update(
                range(inicio, final + 1)
            )

        elif parte.isdigit():

            resultado.add(int(parte))

        else:

            raise ValueError(
                f"Formato de semanas no válido: {parte}"
            )

    return resultado if resultado else None


def semanas_coincidentes(semanas_a, semanas_b):
    """Indica si dos actividades coinciden en alguna semana."""

    if semanas_a is None or semanas_b is None:
        return True

    return bool(
        semanas_a.intersection(semanas_b)
    )


def obtener_profesores(valor):
    """Obtiene los profesores de una actividad."""

    if valor is None or pd.isna(valor):
        return set()

    return {
        normalizar_texto(profesor)
        for profesor in str(valor).split("/")
        if profesor.strip()
    }


def grupos_comparten_estudiantes(grupo_a, grupo_b):
    """
    Comprueba si dos grupos comparten estudiantes.

    17 representa al grupo completo.
    41 representa el subgrupo A.
    42 y 18 representan el subgrupo B.
    """

    a = str(grupo_a).strip()
    b = str(grupo_b).strip()

    if a == b:
        return True

    equivalencias = {
        "17": "TODOS",
        "41": "A",
        "42": "B",
        "18": "B",
    }

    grupo_a_normalizado = equivalencias.get(a, a)
    grupo_b_normalizado = equivalencias.get(b, b)

    if grupo_a_normalizado == "TODOS":
        return True

    if grupo_b_normalizado == "TODOS":
        return True

    return grupo_a_normalizado == grupo_b_normalizado


def obtener_dia(slot, horas_por_dia):
    """Obtiene el día a partir del slot."""

    return int(slot) // horas_por_dia


def intervalos_se_solapan(
    inicio_a,
    duracion_a,
    inicio_b,
    duracion_b
):
    """Comprueba si dos intervalos horarios se solapan."""

    final_a = inicio_a + duracion_a
    final_b = inicio_b + duracion_b

    return (
        inicio_a < final_b
        and inicio_b < final_a
    )


# ---------------------------------------------------------
# PREPROCESAMIENTO
# ---------------------------------------------------------

def preparar_actividades(df):
    """
    Prepara los datos de las actividades para evaluarlas.

    Convierte cada fila en un diccionario con los valores
    necesarios para comprobar las restricciones.
    """

    actividades = []

    for fila in df.to_dict(orient="records"):

        actividad = {
            "Slot": int(float(fila["Slot"])),

            "Duracion": obtener_duracion(fila),

            "Grupo": fila["Grupo"],

            "Profesor": obtener_profesores(
                fila["Profesor"]
            ),

            "Aula": normalizar_texto(
                fila["Aula"]
            ),

            "Semanas": obtener_semanas(
                fila["Semanas_activas"]
            ),

            "Sesion_original": fila.get(
                "Sesion_original"
            ),

            "Tipo": normalizar_texto(
                fila.get("Tipo", "")
            )
        }

        actividades.append(actividad)

    return actividades


# ---------------------------------------------------------
# COMPROBACIÓN DE RESTRICCIONES OBLIGATORIAS
# ---------------------------------------------------------

def comprobar_restricciones(
    df,
    horas_por_dia=6
):
    """
    Comprueba que el horario cumple las restricciones obligatorias.

    Devuelve:
        (True, []) si es válido.
        (False, lista_de_errores) si incumple alguna restricción.
    """

    errores = []

    if df is None or df.empty:
        return False, [
            "El horario está vacío."
        ]

    if horas_por_dia <= 0:
        return False, [
            "El número de horas por día no es válido."
        ]

    columnas_necesarias = [
        "Slot",
        "Grupo",
        "Profesor",
        "Aula",
        "Semanas_activas",
    ]

    for columna in columnas_necesarias:

        if columna not in df.columns:
            errores.append(
                f"Falta la columna obligatoria: {columna}"
            )

    if (
        "Duracion" not in df.columns
        and "Duracion_horas" not in df.columns
    ):
        errores.append(
            "Falta la columna de duración."
        )

    if errores:
        return False, errores

    # -----------------------------------------------------
    # 1. PREPARAR LOS DATOS
    # -----------------------------------------------------

    try:

        actividades = preparar_actividades(df)

    except (ValueError, TypeError, KeyError):

        return False, [
            "Hay valores horarios, duraciones o datos "
            "de actividades no válidos."
        ]

    # -----------------------------------------------------
    # 2. COMPROBACIONES INDIVIDUALES
    # -----------------------------------------------------

    for indice, actividad in enumerate(actividades):

        inicio = actividad["Slot"]
        duracion = actividad["Duracion"]

        if duracion <= 0:
            errores.append(
                f"Actividad {indice}: duración no válida."
            )
            continue

        if inicio < 0:
            errores.append(
                f"Actividad {indice}: slot inicial negativo."
            )
            continue

        hora_inicio_dia = inicio % horas_por_dia

        if hora_inicio_dia + duracion > horas_por_dia:

            errores.append(
                f"Actividad {indice}: supera el horario diario."
            )

        if inicio >= 5 * horas_por_dia:

            errores.append(
                f"Actividad {indice}: está fuera de la semana lectiva."
            )

    if errores:
        return False, errores

    # -----------------------------------------------------
    # 3. COMPROBACIÓN DE CONFLICTOS ENTRE ACTIVIDADES
    # -----------------------------------------------------

    numero_actividades = len(actividades)

    for i in range(numero_actividades):

        actividad_a = actividades[i]

        inicio_a = actividad_a["Slot"]
        duracion_a = actividad_a["Duracion"]

        dia_a = obtener_dia(
            inicio_a,
            horas_por_dia
        )

        semanas_a = actividad_a["Semanas"]
        profesores_a = actividad_a["Profesor"]
        grupo_a = actividad_a["Grupo"]
        aula_a = actividad_a["Aula"]

        for j in range(i + 1, numero_actividades):

            actividad_b = actividades[j]

            inicio_b = actividad_b["Slot"]
            duracion_b = actividad_b["Duracion"]

            dia_b = obtener_dia(
                inicio_b,
                horas_por_dia
            )

            if dia_a != dia_b:
                continue

            if not semanas_coincidentes(
                semanas_a,
                actividad_b["Semanas"]
            ):
                continue

            if not intervalos_se_solapan(
                inicio_a,
                duracion_a,
                inicio_b,
                duracion_b
            ):
                continue

            # Restricción de estudiantes.
            if grupos_comparten_estudiantes(
                grupo_a,
                actividad_b["Grupo"]
            ):

                errores.append(
                    f"Conflicto de estudiantes entre las "
                    f"actividades {i} y {j}."
                )

            # Restricción de profesores.
            if profesores_a.intersection(
                actividad_b["Profesor"]
            ):

                errores.append(
                    f"Conflicto de profesores entre las "
                    f"actividades {i} y {j}."
                )

            # Restricción de aulas.
            aula_b = actividad_b["Aula"]

            if aula_a and aula_a == aula_b:

                errores.append(
                    f"Conflicto de aula entre las "
                    f"actividades {i} y {j}."
                )

    # -----------------------------------------------------
    # 4. BLOQUES DE UNA MISMA SESIÓN
    # -----------------------------------------------------

    if "Sesion_original" in df.columns:

        sesiones = {}

        for actividad in actividades:

            sesion = actividad["Sesion_original"]

            if sesion is None or pd.isna(sesion):
                continue

            dia = obtener_dia(
                actividad["Slot"],
                horas_por_dia
            )

            sesiones.setdefault(
                str(sesion),
                []
            ).append(dia)

        for sesion, dias in sesiones.items():

            if len(dias) != len(set(dias)):

                errores.append(
                    f"La sesión {sesion} tiene bloques "
                    f"en el mismo día."
                )

    return len(errores) == 0, errores


# ---------------------------------------------------------
# EVALUACIÓN DE PREFERENCIAS
# ---------------------------------------------------------

def calcular_coste(
    df,
    horas_por_dia=6
):
    """
    Calcula el coste de las preferencias del horario.

    Cuanto menor sea el coste, mejor será el horario.

    Penalizaciones:
    - Actividades que comienzan durante las dos últimas
      horas del viernes: +10.
    - Actividades teóricas que no utilizan A3-1: +2.
    """

    if df is None or df.empty:
        return float("inf")

    if horas_por_dia <= 0:
        raise ValueError(
            "El número de horas por día no es válido."
        )

    coste = 0

    inicio_ultima_parte_viernes = (
        4 * horas_por_dia
        + (horas_por_dia - 2)
    )

    for fila in df.to_dict(orient="records"):

        slot = int(fila["Slot"])

        # -------------------------------------------------
        # PREFERENCIA 1: EVITAR EL FINAL DEL VIERNES
        # -------------------------------------------------

        if slot >= inicio_ultima_parte_viernes:

            coste += PENALIZACION_VIERNES

        # -------------------------------------------------
        # PREFERENCIA 2: UTILIZAR EL AULA A3-1 EN TEORÍA
        # -------------------------------------------------

        tipo = normalizar_texto(
            fila.get("Tipo", "")
        )

        if "teoria" in tipo:

            aula = str(
                fila.get("Aula", "")
            ).strip()

            if aula != AULA_PREFERIDA:

                coste += PENALIZACION_AULA_TEORIA

    return coste


# ---------------------------------------------------------
# EVALUACIÓN COMPLETA
# ---------------------------------------------------------

def evaluar_horario(
    df,
    horas_por_dia=6
):
    """
    Evalúa un horario completo.

    Devuelve un diccionario con:
    - valido: si cumple las restricciones obligatorias.
    - errores: lista de incumplimientos.
    - coste: puntuación de preferencias.
    """

    valido, errores = comprobar_restricciones(
        df,
        horas_por_dia
    )

    if not valido:

        coste = float("inf")

    else:

        coste = calcular_coste(
            df,
            horas_por_dia
        )

    return {
        "valido": valido,
        "errores": errores,
        "coste": coste,
    }
