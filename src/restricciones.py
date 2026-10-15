"""
Módulo de restricciones para el planificador de horarios
Contiene tanto las restricciones duras (inviolables) como las blandas (a minimizar).
"""
from ortools.sat.python import cp_model


# RESTRICCIONES DURAS (Obligatorias)

def aplicar_restriccion_estudiantes(model, df_clases, interval_vars):
    """
    DURA: Un alumno no puede tener dos clases al mismo tiempo.
    - Los subgrupos (41 o 42) no pueden tener dos clases simultáneas.
    - Si hay clase de teoría (grupo 17), ningún subgrupo puede tener clase a esa misma hora.
    """
    sesiones = df_clases.to_dict("records")
    n = len(sesiones)

    for i in range(n):
        for j in range(i + 1, n):
            s1 = sesiones[i]
            s2 = sesiones[j]
            g1, g2 = str(s1["grupo"]), str(s2["grupo"])

            # Hay conflicto si coinciden en subgrupo o si alguno es teoría de curso completo (17)
            comparten_estudiantes = (g1 == g2) or (g1 == "17") or (g2 == "17")
            if comparten_estudiantes:
                id1 = str(s1["id_sesion"])
                id2 = str(s2["id_sesion"])
                model.AddNoOverlap([interval_vars[id1], interval_vars[id2]])


def aplicar_restriccion_profesores(model, df_clases, interval_vars):
    """
    DURA: Un profesor no puede impartir dos sesiones al mismo tiempo.
    """
    for profesor in df_clases["profesor"].dropna().unique():
        sesiones_prof = df_clases[df_clases["profesor"] == profesor]["id_sesion"].astype(str).tolist()
        if len(sesiones_prof) > 1:
            model.AddNoOverlap([interval_vars[s_id] for s_id in sesiones_prof])


def aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, horas_por_dia=6):
    """
    DURA: Las sesiones de varias horas no pueden partirse entre dos días distintos
    (no puede empezar a las 13:30 y terminar a las 09:30 del día siguiente).
    """
    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"])
        duracion = int(row["duracion_horas"])
        if duracion > 1:
            dia_inicio = model.NewIntVar(0, 4, f"dia_ini_{s_id}")
            dia_fin = model.NewIntVar(0, 4, f"dia_fin_{s_id}")

            model.AddDivisionEquality(dia_inicio, start_vars[s_id], horas_por_dia)
            model.AddDivisionEquality(dia_fin, end_vars[s_id] - 1, horas_por_dia)
            model.Add(dia_inicio == dia_fin)


def aplicar_restriccion_aulas(model, df_clases, df_aulas, start_vars, end_vars):
    """
    DURA:
    1. A cada sesión se le asigna un aula que cumpla con el tipo requerido (teoría o laboratorio).
    2. Dos clases no pueden coincidir en el mismo aula y a la misma hora.
    Devuelve el diccionario de asignaciones aula_assign[s_id, a_id].
    """
    aula_assign = {}

    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"])
        tipo_aula_req = row.get("tipo_aula_requerida", "laboratorio" if row["tipo"] == "practica" else "aula_teoria")

        aulas_compatibles = df_aulas[df_aulas["tipo"] == tipo_aula_req]["id_aula"].astype(str).tolist()

        for a_id in df_aulas["id_aula"].astype(str):
            if a_id in aulas_compatibles:
                aula_assign[s_id, a_id] = model.NewBoolVar(f"aula_{s_id}_{a_id}")
            else:
                aula_assign[s_id, a_id] = model.NewConstant(0)

        # Exactamente 1 aula compatible asignada
        model.Add(sum(aula_assign[s_id, a_id] for a_id in aulas_compatibles) == 1)

    # No solapamiento de aulas
    for a_id in df_aulas["id_aula"].astype(str):
        intervalos_aula = []
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"])
            dur = int(row["duracion_horas"])

            # Intervalo condicionado a que la clase se imparta en esta aula
            opt_interval = model.NewOptionalIntervalVar(
                start_vars[s_id], dur, end_vars[s_id],
                aula_assign[s_id, a_id],
                f"opt_int_{s_id}_{a_id}"
            )
            intervalos_aula.append(opt_interval)
        model.AddNoOverlap(intervalos_aula)

    return aula_assign



# RESTRICCIONES BLANDAS (Criterios a optimizar en la función objetivo)

def aplicar_restricciones_blandas(model, df_clases, start_vars, total_slots=30):
    """
    BLANDA:
    - Penaliza ubicar clases en el viernes por la tarde (últimos turnos de la semana).
    Devuelve la suma de penalizaciones a minimizar.
    """
    penalizaciones = []

    # Ejemplo 1: Penalizar clases en las dos últimas horas del viernes (slots 28 y 29)
    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"])
        es_viernes_tarde = model.NewBoolVar(f"vtarde_{s_id}")

        model.Add(start_vars[s_id] >= (total_slots - 2)).OnlyEnforceIf(es_viernes_tarde)
        model.Add(start_vars[s_id] < (total_slots - 2)).OnlyEnforceIf(es_viernes_tarde.Not())

        penalizaciones.append(es_viernes_tarde * 15)  # Peso de penalización: 15

    if penalizaciones:
        model.Minimize(sum(penalizaciones))