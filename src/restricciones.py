"""
Módulo de restricciones para el planificador de horarios
Contiene tanto las restricciones duras (inviolables) como las blandas (a minimizar).
"""
from ortools.sat.python import cp_model
import pandas as pd


# RESTRICCIONES DURAS (Obligatorias)

def aplicar_restriccion_estudiantes(model, df_clases, interval_vars):
    """
    DURA: Un alumno no puede tener dos clases al mismo tiempo dentro de su curso.
    Funciona automáticamente para 1º, 2º, 3º y 4º (tengan 2 o 4 subgrupos y practica_aula).
    """
    sesiones = df_clases.to_dict("records")
    n = len(sesiones)

    for i in range(n):
        for j in range(i + 1, n):
            s1, s2 = sesiones[i], sesiones[j]

            # Cursos distintos no colisionan entre sí
            if int(s1["curso"]) != int(s2["curso"]):
                continue

            g1, g2 = str(s1["grupo"]).strip(), str(s2["grupo"]).strip()
            t1, t2 = str(s1["tipo"]).strip().lower(), str(s2["tipo"]).strip().lower()
            comparten = False

            # 1. La teoría general de un curso colisiona con cualquier otra sesión de ese curso
            if t1 == "teoria" or t2 == "teoria":
                comparten = True
            # 2. Mismo subgrupo exacto (ej. 41 con 41, o 17 con 17)
            elif g1 == g2:
                comparten = True
            # 3. Bloque 17 (práctica de aula o grupo base) choca con subgrupos 41 y 42
            elif (g1 == "17" and g2 in ["41", "42"]) or (g2 == "17" and g1 in ["41", "42"]):
                comparten = True
            # 4. Bloque 18 (práctica de aula) choca con subgrupos 43 y 44
            elif (g1 == "18" and g2 in ["43", "44"]) or (g2 == "18" and g1 in ["43", "44"]):
                comparten = True

            if comparten:
                id1 = str(s1["id_sesion"]).strip()
                id2 = str(s2["id_sesion"]).strip()
                model.AddNoOverlap([interval_vars[id1], interval_vars[id2]])


def aplicar_restriccion_profesores(model, df_clases, interval_vars):
    """
    DURA: Un profesor no puede impartir dos sesiones al mismo tiempo.
    """
    df_clases["profesor"] = df_clases["profesor"].astype(str).str.strip()
    for profesor in df_clases["profesor"].dropna().unique():
        if profesor.lower() in ["", "nan", "none"]:
            continue
        sesiones_prof = df_clases[df_clases["profesor"] == profesor]["id_sesion"].astype(str).str.strip().tolist()
        if len(sesiones_prof) > 1:
            model.AddNoOverlap([interval_vars[s_id] for s_id in sesiones_prof])


def aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, horas_por_dia=6):
    """
    DURA: Las sesiones de varias horas no pueden partirse entre dos días distintos.
    """
    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()
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
    """
    def estandarizar_tipo(texto):
        t = str(texto).strip().lower()
        return "teoria" if "teor" in t else "laboratorio"

    df_aulas.columns = df_aulas.columns.str.strip().str.lower()
    df_clases.columns = df_clases.columns.str.strip().str.lower()

    col_tipo = "tipo" if "tipo" in df_aulas.columns else "tipo_aula"
    col_id_aula = "id_aula" if "id_aula" in df_aulas.columns else df_aulas.columns[0]

    tipos_aulas = df_aulas[col_tipo].apply(estandarizar_tipo)
    aula_assign = {}

    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()

        if "tipo_aula_requerida" in row and pd.notna(row["tipo_aula_requerida"]):
            tipo_necesario = estandarizar_tipo(row["tipo_aula_requerida"])
        else:
            tipo_necesario = "laboratorio" if "prac" in str(row["tipo"]).strip().lower() else "teoria"

        num_alumnos = int(row.get("num_alumnos", 0))

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

        model.Add(sum(aula_assign[s_id, a_id] for a_id in aulas_compatibles) == 1)

    for a_id in df_aulas[col_id_aula].astype(str):
        intervalos_aula = []
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
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
    Funciona independientemente de si un grupo tiene 2, 3, 4 o más clases en el mismo día.
    """
    for curso in df_clases["curso"].unique():
        df_curso = df_clases[df_clases["curso"] == curso]
        for grp in df_curso["grupo"].unique():
            df_grp = df_curso[df_curso["grupo"] == grp]
            if len(df_grp) <= 1:
                continue

            sesiones_info = []
            for _, row in df_grp.iterrows():
                s_id = str(row["id_sesion"]).strip()
                dur = int(row["duracion_horas"])
                dia_var = model.NewIntVar(0, 4, f"dia_grp_{curso}_{grp}_{s_id}")
                model.AddDivisionEquality(dia_var, start_vars[s_id], horas_por_dia)
                sesiones_info.append((s_id, dur, dia_var))

            for d in range(5):
                inicio_dia = d * horas_por_dia
                fin_dia = (d + 1) * horas_por_dia

                en_dia_vars = []
                starts_dia = []
                ends_dia = []

                for s_id, dur, dia_var in sesiones_info:
                    en_dia = model.NewBoolVar(f"en_dia_{curso}_{grp}_{s_id}_{d}")
                    model.Add(dia_var == d).OnlyEnforceIf(en_dia)
                    model.Add(dia_var != d).OnlyEnforceIf(en_dia.Not())
                    en_dia_vars.append((en_dia, dur))

                    s_d = model.NewIntVar(inicio_dia, fin_dia, f"sd_{curso}_{grp}_{s_id}_{d}")
                    model.Add(s_d == start_vars[s_id]).OnlyEnforceIf(en_dia)
                    model.Add(s_d == fin_dia).OnlyEnforceIf(en_dia.Not())
                    starts_dia.append(s_d)

                    e_d = model.NewIntVar(inicio_dia, fin_dia, f"ed_{curso}_{grp}_{s_id}_{d}")
                    model.Add(e_d == end_vars[s_id]).OnlyEnforceIf(en_dia)
                    model.Add(e_d == inicio_dia).OnlyEnforceIf(en_dia.Not())
                    ends_dia.append(e_d)

                horas_en_dia = sum(en_dia * dur for en_dia, dur in en_dia_vars)
                hay_clase = model.NewBoolVar(f"hay_clase_{curso}_{grp}_{d}")
                model.Add(horas_en_dia >= 1).OnlyEnforceIf(hay_clase)
                model.Add(horas_en_dia == 0).OnlyEnforceIf(hay_clase.Not())

                min_ini = model.NewIntVar(inicio_dia, fin_dia, f"min_ini_{curso}_{grp}_{d}")
                max_fin = model.NewIntVar(inicio_dia, fin_dia, f"max_fin_{curso}_{grp}_{d}")
                model.AddMinEquality(min_ini, starts_dia)
                model.AddMaxEquality(max_fin, ends_dia)

                # Sin huecos: la amplitud total del bloque diario coincide con las horas lectivas
                model.Add(max_fin - min_ini == horas_en_dia).OnlyEnforceIf(hay_clase)


def aplicar_restriccion_dias_libres_practicas(model, df_clases, start_vars):
    """
    DURA (Solo para 3º de GCID en el 2º Cuatrimestre):
    Concentra la docencia presencial en Lunes, Martes y Miércoles (slots 0 a 17)
    para liberar Jueves y Viernes para las Prácticas Externas.
    """
    df_tercero = df_clases[df_clases["curso"] == 3]
    for _, row in df_tercero.iterrows():
        s_id = str(row["id_sesion"]).strip()
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
        s_str = str(identificador).strip()
        if s_str in start_vars:
            return start_vars[s_str]
        if identificador in start_vars:
            return start_vars[identificador]
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
            var_aula_pref = aula_assign.get((s_id, aula_preferida))
            if var_aula_pref is None:
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