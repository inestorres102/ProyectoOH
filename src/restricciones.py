
import re
import unicodedata
from itertools import combinations

import pandas as pd


# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def normalizar_texto(valor):
    """Elimina tildes y normaliza un texto para comparaciones."""

    if pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFD", texto)

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def obtener_profesores(valor):
    """Obtiene los profesores de una celda separados por /."""

    if pd.isna(valor):
        return set()

    return {
        normalizar_texto(nombre)
        for nombre in str(valor).split("/")
        if normalizar_texto(nombre)
    }


def obtener_semanas(valor):
    """
    Convierte expresiones como:
        1-5,8,10-12
        1,3,5,7

    en conjuntos de semanas.

    Si no hay semanas definidas, devuelve None.
    """

    if pd.isna(valor) or not str(valor).strip():
        return None

    texto = str(valor).strip()
    semanas = set()

    partes = re.split(r"[,;]", texto)

    for parte in partes:

        parte = parte.strip()

        if not parte:
            continue

        rango = re.fullmatch(
            r"(\d+)\s*-\s*(\d+)",
            parte
        )

        if rango:

            inicio = int(rango.group(1))
            fin = int(rango.group(2))

            if fin < inicio:
                raise ValueError(
                    f"Rango de semanas incorrecto: {parte}"
                )

            if inicio < 1:
                raise ValueError(
                    f"Las semanas deben empezar en 1: {parte}"
                )

            semanas.update(range(inicio, fin + 1))

        else:

            numero = re.fullmatch(r"\d+", parte)

            if not numero:
                raise ValueError(
                    f"Formato de semanas no válido: {valor}"
                )

            semana = int(parte)

            if semana < 1:
                raise ValueError(
                    f"Número de semana incorrecto: {parte}"
                )

            semanas.add(semana)

    return semanas if semanas else None


def coinciden_semanas(semanas_a, semanas_b):
    """
    Comprueba si dos actividades coinciden en alguna semana.

    Si alguna actividad no tiene semanas definidas,
    se considera que puede coincidir con todas.
    """

    if semanas_a is None or semanas_b is None:
        return True

    return bool(semanas_a.intersection(semanas_b))


def obtener_grupos_alumnos(grupo):
    """
    Identifica qué alumnado comparte cada actividad.

    Correspondencias:
        17 -> Toda la clase.
        41 -> Subgrupo A.
        42 -> Subgrupo B.
        18 -> Subgrupo B (si aparece en los datos).

    El grupo 17 comparte alumnado tanto con 41 como con 42.

    Los grupos desconocidos solo coinciden con el mismo
    identificador.
    """

    if pd.isna(grupo):
        return set()

    texto = str(grupo).strip()

    if not texto:
        return set()

    numeros = re.findall(r"\d+", texto)

    if not numeros:
        return {normalizar_texto(texto)}

    correspondencias = {
        "17": "TODOS",
        "41": "A",
        "42": "B",
        "18": "B"
    }

    resultado = set()

    for numero in numeros:

        if numero in correspondencias:
            resultado.add(correspondencias[numero])
        else:
            resultado.add(f"grupo_{numero}")

    return resultado


def misma_clase_alumnos(grupo_a, grupo_b):
    """
    Comprueba si dos actividades comparten alumnado.

    El grupo TODOS coincide con cualquier subgrupo.
    """

    grupos_a = obtener_grupos_alumnos(grupo_a)
    grupos_b = obtener_grupos_alumnos(grupo_b)

    if not grupos_a or not grupos_b:
        return False

    if "TODOS" in grupos_a or "TODOS" in grupos_b:
        return True

    return bool(grupos_a.intersection(grupos_b))


def obtener_columna(df, alternativas):
    """Localiza una columna entre varios nombres posibles."""

    columnas = {
        normalizar_texto(columna): columna
        for columna in df.columns
    }

    for alternativa in alternativas:

        clave = normalizar_texto(alternativa)

        if clave in columnas:
            return columnas[clave]

    return None


def obtener_semanas_dataframe(df_clases):
    """Obtiene las semanas activas de todas las actividades."""

    if "semanas_activas" not in df_clases.columns:
        return [None] * len(df_clases)

    return [
        obtener_semanas(valor)
        for valor in df_clases["semanas_activas"]
    ]


# ---------------------------------------------------------
# RESTRICCIÓN 1: ESTUDIANTES
# ---------------------------------------------------------

def aplicar_restriccion_estudiantes(
    model,
    df_clases,
    interval_vars
):
    """
    Dos actividades que comparten estudiantes no pueden
    coincidir en horario durante semanas coincidentes.

    El grupo 17 representa a toda la clase y, por tanto,
    no puede coincidir con los grupos 41 ni 42.
    """

    semanas = obtener_semanas_dataframe(df_clases)

    grupos = [
        obtener_grupos_alumnos(valor)
        for valor in df_clases["grupo"]
    ]

    for i, j in combinations(range(len(df_clases)), 2):

        comparten_alumnos = (
            "TODOS" in grupos[i]
            or "TODOS" in grupos[j]
            or bool(grupos[i].intersection(grupos[j]))
        )

        coinciden = coinciden_semanas(
            semanas[i],
            semanas[j]
        )

        if comparten_alumnos and coinciden:

            model.AddNoOverlap([
                interval_vars[i],
                interval_vars[j]
            ])


# ---------------------------------------------------------
# RESTRICCIÓN 2: LOS BLOQUES NO PUEDEN CAMBIAR DE DÍA
# ---------------------------------------------------------

def aplicar_restriccion_cambio_dia(
    model,
    start_vars,
    end_vars,
    horas_por_dia=6
):
    """
    Impide que un bloque empiece un día y termine
    en el siguiente.
    """

    if horas_por_dia <= 0:
        raise ValueError(
            "Las horas por día deben ser mayores que cero."
        )

    for indice, (inicio, fin) in enumerate(
        zip(start_vars, end_vars)
    ):

        dia_inicio = model.NewIntVar(
            0,
            4,
            f"dia_inicio_{indice}"
        )

        dia_fin = model.NewIntVar(
            0,
            4,
            f"dia_fin_{indice}"
        )

        model.AddDivisionEquality(
            dia_inicio,
            inicio,
            horas_por_dia
        )

        # Se utiliza fin - 1 para que una clase que termine
        # exactamente al final del día siga perteneciendo
        # al mismo día en el que comenzó.
        model.AddDivisionEquality(
            dia_fin,
            fin - 1,
            horas_por_dia
        )

        model.Add(dia_inicio == dia_fin)


# ---------------------------------------------------------
# RESTRICCIÓN 3: PROFESORES
# ---------------------------------------------------------

def aplicar_restriccion_profesores(
    model,
    df_clases,
    interval_vars
):
    """
    Un profesor no puede impartir dos actividades
    simultáneamente durante semanas coincidentes.

    Admite varios profesores separados por /.
    """

    semanas = obtener_semanas_dataframe(df_clases)

    profesores = [
        obtener_profesores(valor)
        for valor in df_clases["profesor"]
    ]

    for i, j in combinations(range(len(df_clases)), 2):

        comparten_profesor = bool(
            profesores[i].intersection(profesores[j])
        )

        coinciden = coinciden_semanas(
            semanas[i],
            semanas[j]
        )

        if comparten_profesor and coinciden:

            model.AddNoOverlap([
                interval_vars[i],
                interval_vars[j]
            ])


# ---------------------------------------------------------
# RESTRICCIÓN 4: AULAS
# ---------------------------------------------------------

def aplicar_restriccion_aulas(
    model,
    df_clases,
    start_vars,
    end_vars,
    df_aulas
):
    """
    Asigna exactamente un aula compatible a cada actividad.

    Comprueba:
    - Tipo de aula.
    - Capacidad del aula.
    - Disponibilidad temporal.
    - Coincidencia de semanas.

    Las actividades que no coinciden en semanas pueden
    reutilizar la misma aula y la misma franja horaria.
    """

    columna_id = obtener_columna(
        df_aulas,
        ["id_aula", "aula", "nombre", "codigo"]
    )

    columna_tipo = obtener_columna(
        df_aulas,
        ["tipo_aula", "tipo"]
    )

    columna_capacidad = obtener_columna(
        df_aulas,
        ["capacidad", "aforo", "num_alumnos"]
    )

    if columna_id is None or columna_tipo is None:

        raise ValueError(
            "No se encuentran las columnas de identificación "
            "y tipo de aula en datos/aulas.csv."
        )

    # Comprobar que los identificadores de aula son únicos.
    identificadores = (
        df_aulas[columna_id]
        .astype(str)
        .str.strip()
    )

    if identificadores.duplicated().any():

        duplicados = identificadores[
            identificadores.duplicated()
        ].tolist()

        raise ValueError(
            "Hay identificadores de aula duplicados: "
            + ", ".join(duplicados)
        )

    semanas = obtener_semanas_dataframe(df_clases)

    asignaciones = []

    intervalos_por_aula = {}

    # Crear asignaciones de aulas e intervalos opcionales.
    for i in range(len(df_clases)):

        clase = df_clases.iloc[i]

        tipo_requerido = normalizar_texto(
            clase["tipo_aula_requerida"]
        )

        alumnos = int(clase["num_alumnos"])

        duracion = int(clase["duracion_horas"])

        aulas_compatibles = []

        for _, aula in df_aulas.iterrows():

            aula_id = str(
                aula[columna_id]
            ).strip()

            tipo_aula = normalizar_texto(
                aula[columna_tipo]
            )

            if tipo_aula != tipo_requerido:
                continue

            # Comprobar capacidad.
            if columna_capacidad is not None:

                capacidad = pd.to_numeric(
                    aula[columna_capacidad],
                    errors="coerce"
                )

                if pd.notna(capacidad):

                    if capacidad < alumnos:
                        continue

            aulas_compatibles.append(aula_id)

        if not aulas_compatibles:

            raise ValueError(
                f"La sesión {clase['id_sesion']} no tiene "
                f"aulas compatibles. Tipo requerido: "
                f"{tipo_requerido}; alumnos: {alumnos}."
            )

        variables_aula = {}

        for aula_id in aulas_compatibles:

            variable = model.NewBoolVar(
                f"aula_{i}_{aula_id}"
            )

            variables_aula[aula_id] = variable

            # Intervalo opcional: solo existe si la actividad
            # tiene asignada esta aula.
            intervalo_aula = model.NewOptionalIntervalVar(
                start_vars[i],
                duracion,
                end_vars[i],
                variable,
                f"intervalo_aula_{i}_{aula_id}"
            )

            if aula_id not in intervalos_por_aula:
                intervalos_por_aula[aula_id] = []

            intervalos_por_aula[aula_id].append(
                (intervalo_aula, semanas[i])
            )

        # Cada actividad debe tener exactamente un aula.
        model.AddExactlyOne(
            list(variables_aula.values())
        )

        asignaciones.append(variables_aula)

    # Evitar solapamientos en cada aula.
    for aula_id, intervalos in intervalos_por_aula.items():

        for i, j in combinations(range(len(intervalos)), 2):

            intervalo_i, semanas_i = intervalos[i]
            intervalo_j, semanas_j = intervalos[j]

            if coinciden_semanas(semanas_i, semanas_j):

                model.AddNoOverlap([
                    intervalo_i,
                    intervalo_j
                ])

    return asignaciones


# ---------------------------------------------------------
# RESTRICCIONES BLANDAS: MEJORA DEL HORARIO
# ---------------------------------------------------------

def aplicar_restricciones_blandas(
    model,
    start_vars,
    df_clases,
    total_slots,
    aula_assign=None,
    aula_preferida="A3-1",
    horas_por_dia=6
):
    """
    Preferencias que el modelo intenta cumplir,
    pero que no son obligatorias.

    - Evitar las dos últimas horas del viernes.
    - Favorecer el aula preferida para teoría.

    Penalizaciones:
    - Comienzo durante las dos últimas horas del viernes: 10.
    - Aula distinta de la preferida en teoría: 2.

    Funciona con jornadas de 6 o de 8 horas.
    """

    if horas_por_dia <= 0:
        raise ValueError(
            "Las horas por día deben ser mayores que cero."
        )

    penalizaciones = []

    viernes = 4

    # El comienzo de las dos últimas horas del viernes.
    inicio_ultima_parte_viernes = (
        viernes * horas_por_dia
        + (horas_por_dia - 2)
    )

    # -----------------------------------------------------
    # Penalizar clases que comienzan en las dos últimas
    # franjas del viernes.
    # -----------------------------------------------------

    for i, inicio in enumerate(start_vars):

        tarde_viernes = model.NewBoolVar(
            f"penalizacion_viernes_{i}"
        )

        model.Add(
            inicio >= inicio_ultima_parte_viernes
        ).OnlyEnforceIf(tarde_viernes)

        model.Add(
            inicio < inicio_ultima_parte_viernes
        ).OnlyEnforceIf(tarde_viernes.Not())

        penalizaciones.append(
            tarde_viernes * 10
        )

    # -----------------------------------------------------
    # Favorecer el aula preferida para las clases teóricas.
    # -----------------------------------------------------

    if aula_assign is not None:

        for i, variables_aula in enumerate(aula_assign):

            tipo = normalizar_texto(
                df_clases.iloc[i]["tipo"]
            )

            if "teor" not in tipo:
                continue

            if aula_preferida in variables_aula:

                penalizacion_aula = (
                    1 - variables_aula[aula_preferida]
                )

                penalizaciones.append(
                    penalizacion_aula * 2
                )

    if penalizaciones:
        model.Minimize(sum(penalizaciones))
