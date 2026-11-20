

"""
Restricciones del modelo de planificación de horarios.

Incluye:
- Restricciones de estudiantes.
- Restricciones de profesores.
- Restricciones de aulas y capacidades.
- Control de semanas activas.
- Prohibición de bloques que atraviesen días.
- Preferencias blandas para mejorar los horarios.
"""

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
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def obtener_profesores(valor):
    """Obtiene los profesores de una celda, separados por /."""
    if pd.isna(valor):
        return set()

    return {
        normalizar_texto(nombre)
        for nombre in str(valor).split("/")
        if normalizar_texto(nombre)
    }


def obtener_semanas(valor):
    """
    Convierte semanas como:
        1-5,8,10-12
        1,3,5,7

    en conjuntos de números.

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

        rango = re.fullmatch(r"(\d+)\s*-\s*(\d+)", parte)

        if rango:
            inicio = int(rango.group(1))
            fin = int(rango.group(2))

            if fin < inicio:
                raise ValueError(
                    f"Rango de semanas incorrecto: {parte}"
                )

            semanas.update(range(inicio, fin + 1))
        else:
            numero = re.fullmatch(r"\d+", parte)

            if not numero:
                raise ValueError(
                    f"Formato de semanas no válido: {valor}"
                )

            semanas.add(int(parte))

    return semanas if semanas else None


def coinciden_semanas(semanas_a, semanas_b):
    """
    Indica si dos actividades coinciden en alguna semana.

    Si alguna actividad no tiene semanas definidas,
    se considera que puede coincidir con todas.
    """

    if semanas_a is None or semanas_b is None:
        return True

    return bool(semanas_a.intersection(semanas_b))


def misma_clase_alumnos(grupo_a, grupo_b):
    """
    Determina si dos actividades comparten estudiantes.

    El grupo 17 se considera el grupo completo.
    """

    a = normalizar_texto(grupo_a)
    b = normalizar_texto(grupo_b)

    if not a or not b:
        return False

    return a == b or a == "17" or b == "17"


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
    """

    semanas = [
        obtener_semanas(valor)
        for valor in df_clases["semanas_activas"]
    ]

    for i, j in combinations(range(len(df_clases)), 2):

        clase_i = df_clases.iloc[i]
        clase_j = df_clases.iloc[j]

        comparten_alumnos = misma_clase_alumnos(
            clase_i["grupo"],
            clase_j["grupo"]
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
    horas_por_dia=12
):
    """
    Impide que un bloque horario empiece un día
    y termine en el siguiente.
    """

    for inicio, fin in zip(start_vars, end_vars):

        dia_inicio = model.NewIntVar(
            0, 4, f"dia_inicio_{inicio.Index()}"
        )

        dia_fin = model.NewIntVar(
            0, 4, f"dia_fin_{inicio.Index()}"
        )

        model.AddDivisionEquality(
            dia_inicio,
            inicio,
            horas_por_dia
        )

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
    """

    semanas = [
        obtener_semanas(valor)
        for valor in df_clases["semanas_activas"]
    ]

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

    Dos actividades no pueden utilizar la misma aula
    simultáneamente si sus semanas coinciden.

    Si sus semanas son diferentes, pueden reutilizar
    el mismo espacio horario y la misma aula.
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

    asignaciones = []

    # Crear variables de asignación.
    for i in range(len(df_clases)):

        clase = df_clases.iloc[i]

        tipo_requerido = normalizar_texto(
            clase["tipo_aula_requerida"]
        )

        alumnos = int(clase["num_alumnos"])

        aulas_compatibles = []

        for _, aula in df_aulas.iterrows():

            tipo_aula = normalizar_texto(
                aula[columna_tipo]
            )

            if tipo_aula != tipo_requerido:
                continue

            if columna_capacidad is not None:
                capacidad = pd.to_numeric(
                    aula[columna_capacidad],
                    errors="coerce"
                )

                if pd.notna(capacidad) and capacidad < alumnos:
                    continue

            aulas_compatibles.append(
                str(aula[columna_id])
            )

        variables_aula = {}

        for aula_id in aulas_compatibles:

            variable = model.NewBoolVar(
                f"aula_{i}_{aula_id}"
            )

            variables_aula[aula_id] = variable

        if not variables_aula:
            raise ValueError(
                f"La sesión {clase['id_sesion']} no tiene "
                f"aulas compatibles. Tipo requerido: "
                f"{tipo_requerido}; alumnos: {alumnos}."
            )

        model.AddExactlyOne(
            list(variables_aula.values())
        )

        asignaciones.append(variables_aula)

    # Evitar que dos sesiones coincidentes utilicen
    # la misma aula en el mismo horario.
    semanas = [
        obtener_semanas(valor)
        for valor in df_clases["semanas_activas"]
    ]

    for i, j in combinations(range(len(df_clases)), 2):

        if not coinciden_semanas(semanas[i], semanas[j]):
            continue

        aulas_compartidas = (
            set(asignaciones[i]).intersection(asignaciones[j])
        )

        for aula_id in aulas_compartidas:

            antes = model.NewBoolVar(
                f"orden_{i}_{j}_{aula_id}"
            )

            asignacion_i = asignaciones[i][aula_id]
            asignacion_j = asignaciones[j][aula_id]

            # Si ambas sesiones usan esta aula,
            # una debe terminar antes de que empiece la otra.
            model.Add(
                end_vars[i] <= start_vars[j]
            ).OnlyEnforceIf([
                asignacion_i,
                asignacion_j,
                antes
            ])

            model.Add(
                end_vars[j] <= start_vars[i]
            ).OnlyEnforceIf([
                asignacion_i,
                asignacion_j,
                antes.Not()
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
    aula_preferida="A3-1"
):
    """
    Preferencias que el modelo intenta cumplir,
    pero que no son obligatorias.

    - Evitar las últimas horas del viernes.
    - Favorecer el aula preferida para teoría.
    """

    penalizaciones = []

    horas_por_dia = 12
    viernes = 4

    # Penalizar actividades que empiezan en las
    # dos últimas franjas del viernes.
    for i, inicio in enumerate(start_vars):

        tarde_viernes = model.NewBoolVar(
            f"penalizacion_viernes_{i}"
        )

        model.Add(
            inicio >= viernes * horas_por_dia + 10
        ).OnlyEnforceIf(tarde_viernes)

        model.Add(
            inicio < viernes * horas_por_dia + 10
        ).OnlyEnforceIf(tarde_viernes.Not())

        penalizaciones.append(tarde_viernes * 10)

    # Favorecer el aula preferida para teoría.
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