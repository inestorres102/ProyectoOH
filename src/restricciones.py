"""
Módulo de restricciones para el planificador de horarios
Contiene tanto las restricciones duras (inviolables) como las blandas (a minimizar).
"""
from ortools.sat.python import cp_model
import pandas as pd


# RESTRICCIONES DURAS (Obligatorias)

def aplicar_restriccion_estudiantes(model, df_clases, interval_vars):
    """
    DURA: Un alumno no puede tener dos clases al mismo tiempo.
    - Dos sesiones solo colisionan si pertenecen AL MISMO CURSO.
    - Dentro del mismo curso: coincidencia de subgrupo (41, 42, 43, 44) o teoría de curso completo (17).
    """
    sesiones = df_clases.to_dict("records")
    n = len(sesiones)

    for i in range(n):
        for j in range(i + 1, n):
            s1 = sesiones[i]
            s2 = sesiones[j]

            # Solo hay conflicto entre estudiantes SI SON DEL MISMO CURSO
            if str(s1["curso"]).strip() == str(s2["curso"]).strip():
                g1 = str(s1["grupo"]).strip()
                g2 = str(s2["grupo"]).strip()

                # Teoría (17) choca con todo su curso; prácticas chocan si es el mismo subgrupo
                comparten = (g1 == g2) or (g1 == "17") or (g2 == "17")
                if comparten:
                    id1 = str(s1["id_sesion"]).strip()
                    id2 = str(s2["id_sesion"]).strip()
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
    1. A cada sesión se le asigna un aula que cumpla con el tipo requerido y capacidad suficiente.
    2. Dos clases no pueden coincidir en la misma aula y a la misma hora.
    Devuelve el diccionario de asignaciones aula_assign[s_id, a_id].
    """
    # 1. Definir primero la función auxiliar (ANTES de llamarla)
    def estandarizar_tipo(texto):
        t = str(texto).strip().lower()
        return "teoria" if "teor" in t else "laboratorio"

    # 2. Normalizar cabeceras a minúsculas
    df_aulas.columns = df_aulas.columns.str.strip().str.lower()
    df_clases.columns = df_clases.columns.str.strip().str.lower()

    col_tipo = "tipo" if "tipo" in df_aulas.columns else "tipo_aula"
    col_id_aula = "id_aula" if "id_aula" in df_aulas.columns else df_aulas.columns[0]

    # 3. Aplicar estandarización a las aulas
    tipos_aulas = df_aulas[col_tipo].apply(estandarizar_tipo)
    aula_assign = {}

    # 4. Asignación por sesión considerando TIPO y CAPACIDAD
    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"])

        if "tipo_aula_requerida" in row and pd.notna(row["tipo_aula_requerida"]):
            tipo_necesario = estandarizar_tipo(row["tipo_aula_requerida"])
        else:
            tipo_necesario = "laboratorio" if "prac" in str(row["tipo"]).strip().lower() else "teoria"

        num_alumnos = int(row.get("num_alumnos", 0))

        # Filtro: tipo compatible Y capacidad suficiente
        aulas_compatibles = df_aulas[
            (tipos_aulas == tipo_necesario) & 
            (df_aulas["capacidad"] >= num_alumnos)
        ][col_id_aula].astype(str).tolist()

        if not aulas_compatibles:
            raise ValueError(
                f"Error: No hay aulas de tipo '{tipo_necesario}' con capacidad >= {num_alumnos} para la sesión {s_id}."
            )

        for a_id in df_aulas[col_id_aula].astype(str):
            if a_id in aulas_compatibles:
                aula_assign[s_id, a_id] = model.NewBoolVar(f"aula_{s_id}_{a_id}")
            else:
                aula_assign[s_id, a_id] = model.NewConstant(0)

        # Exactamente 1 aula asignada
        model.Add(sum(aula_assign[s_id, a_id] for a_id in aulas_compatibles) == 1)

    # 5. Restricción de No Solapamiento físico en aulas
    for a_id in df_aulas[col_id_aula].astype(str):
        intervalos_aula = []
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"])
            dur = int(row["duracion_horas"])

            opt_interval = model.NewOptionalIntervalVar(
                start_vars[s_id], dur, end_vars[s_id],
                aula_assign[s_id, a_id],
                f"opt_int_{s_id}_{a_id}"
            )
            intervalos_aula.append(opt_interval)
            
        model.AddNoOverlap(intervalos_aula)

    return aula_assign


def aplicar_restriccion_sin_huecos(model, df_clases, start_vars, end_vars, horas_por_dia=6):
    """
    DURA: Evita horas libres intermedias para un mismo grupo dentro de su curso.
    """
    for curso in df_clases["curso"].unique():
        df_curso = df_clases[df_clases["curso"] == curso]
        for grp in df_curso["grupo"].unique():
            sesiones_grp = df_curso[df_curso["grupo"] == grp]["id_sesion"].astype(str).str.strip().tolist()

            if len(sesiones_grp) <= 1:
                continue

            for i in range(len(sesiones_grp)):
                for j in range(i + 1, len(sesiones_grp)):
                    id1, id2 = sesiones_grp[i], sesiones_grp[j]

                    d1 = model.NewIntVar(0, 4, f"dia_{id1}_{id2}")
                    d2 = model.NewIntVar(0, 4, f"dia2_{id1}_{id2}")
                    model.AddDivisionEquality(d1, start_vars[id1], horas_por_dia)
                    model.AddDivisionEquality(d2, start_vars[id2], horas_por_dia)

                    mismo_dia = model.NewBoolVar(f"same_day_{id1}_{id2}")
                    model.Add(d1 == d2).OnlyEnforceIf(mismo_dia)
                    model.Add(d1 != d2).OnlyEnforceIf(mismo_dia.Not())

                    c1 = model.NewBoolVar(f"c1_{id1}_{id2}")
                    c2 = model.NewBoolVar(f"c2_{id1}_{id2}")
                    model.Add(start_vars[id2] == end_vars[id1]).OnlyEnforceIf(c1)
                    model.Add(start_vars[id2] != end_vars[id1]).OnlyEnforceIf(c1.Not())
                    model.Add(start_vars[id1] == end_vars[id2]).OnlyEnforceIf(c2)
                    model.Add(start_vars[id1] != end_vars[id2]).OnlyEnforceIf(c2.Not())

                    model.AddBoolOr([c1, c2]).OnlyEnforceIf(mismo_dia)


def aplicar_restriccion_dias_libres_practicas(model, df_clases, start_vars):
    """
    DURA (Específica del 2º Cuatrimestr, solo se activa con cuatrimestre=2):
    Concentra la docencia presencial en Lunes, Martes y Miércoles (slots 0 a 17)
    para liberar completamente Jueves y Viernes para las Prácticas Externas.
    """
    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()
        # Prohibir cualquier inicio a partir del jueves a las 08:30 (slot 18)
        model.Add(start_vars[s_id] < 18)


# RESTRICCIONES BLANDAS (Criterios a optimizar en la función objetivo)

def aplicar_restricciones_blandas(model, df_clases, start_vars, aula_assign, total_slots=30, aula_preferida="A2-5"):
    """
    RESTRICCIONES BLANDAS (Función Objetivo a minimizar):
    1. Penalizar clases en las dos últimas horas del viernes (slots 28 y 29).
    2. Penalizar que las clases de teoría del Grupo 17 se impartan fuera del aula preferida (A2-5).
    """
    penalizaciones = []

    def obtener_var_inicio(identificador):
        """Busca la variable de inicio probando formatos comunes (str, strip, int)."""
        s_str = str(identificador).strip()
        if s_str in start_vars:
            return start_vars[s_str]
        if identificador in start_vars:
            return start_vars[identificador]
        # Por si el ID en el CSV es un número entero
        try:
            s_int = int(s_str.replace("S", "").replace("s", ""))
            if s_int in start_vars:
                return start_vars[s_int]
            if str(s_int) in start_vars:
                return start_vars[str(s_int)]
        except ValueError:
            pass
        return None

    # 1. Penalizar viernes por la tarde
    for _, row in df_clases.iterrows():
        s_id = row["id_sesion"]
        var_start = obtener_var_inicio(s_id)

        if var_start is not None:
            es_viernes_tarde = model.NewBoolVar(f"vtarde_{str(s_id).strip()}")
            model.Add(var_start >= (total_slots - 2)).OnlyEnforceIf(es_viernes_tarde)
            model.Add(var_start < (total_slots - 2)).OnlyEnforceIf(es_viernes_tarde.Not())
            penalizaciones.append(es_viernes_tarde * 10)

    # 2. Priorizar el aula preferida (A2-5) para teoría del Grupo 17
    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()
        tipo = str(row.get("tipo", "")).strip().lower()
        grupo = str(row.get("grupo", "")).strip()

        if "teor" in tipo and grupo == "17":
            # Probar clave (s_id, aula_preferida)
            var_aula_pref = aula_assign.get((s_id, aula_preferida))
            if var_aula_pref is None:
                # Probar si s_id estaba guardado de otra forma
                for (s_k, a_k), v in aula_assign.items():
                    if str(s_k).strip() == s_id and str(a_k).strip() == aula_preferida:
                        var_aula_pref = v
                        break

            if var_aula_pref is not None:
                no_es_aula_pref = model.NewBoolVar(f"no_pref_{s_id}")
                model.Add(var_aula_pref == 0).OnlyEnforceIf(no_es_aula_pref)
                model.Add(var_aula_pref == 1).OnlyEnforceIf(no_es_aula_pref.Not())
                penalizaciones.append(no_es_aula_pref * 25)

    if penalizaciones:
        model.Minimize(sum(penalizaciones))