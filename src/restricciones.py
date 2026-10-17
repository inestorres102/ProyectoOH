"""
Módulo de restricciones para el planificador de horarios
Contiene tanto las restricciones duras (inviolables) como las blandas (a minimizar).
"""
from ortools.sat.python import cp_model
import pandas as pd


# RESTRICCIONES DURAS (Obligatorias)

def obtener_subgrupos_estudiantes(row, df_clases=None):
    """
    Devuelve el conjunto de subgrupos de estudiantes que asisten a la sesión.
    Jerarquía oficial EII:
    1. Si la fila tiene 'subgrupos_alumnos', lo usa explícitamente (ej: '45,46').
    2. Si es Práctica de Aula (Azul):
       - G17 -> {'41', '42'}
       - G18 -> {'43', '44'}
       - G19 -> {'45', '46'}
       - G20 -> {'47', '48'}
    3. Si es Teoría (Amarillo):
       - Todos los subgrupos de prácticas de su mismo (curso, grupo_principal).
    4. Si es Laboratorio (Verde):
       - El subgrupo individual {'41'}, {'42'}, etc.
    """
    if "subgrupos_alumnos" in row and pd.notna(row["subgrupos_alumnos"]):
        val = str(row["subgrupos_alumnos"]).strip()
        if val:
            return set(val.replace(";", ",").split(","))

    tipo_str = str(row.get("tipo", row.get("Tipo", ""))).strip().lower()
    grupo_str = str(row.get("grupo", row.get("Grupo", ""))).strip()

    # Mapeo oficial de prácticas de aula en la EII
    mapeo_aula = {
        "17": {"41", "42"},
        "18": {"43", "44"},
        "19": {"45", "46"},
        "20": {"47", "48"}
    }
    if "prob" in tipo_str or "aula" in tipo_str or "pa" in tipo_str:
        if grupo_str in mapeo_aula:
            return mapeo_aula[grupo_str]

    if "teor" in tipo_str:
        if df_clases is not None:
            c = row.get("curso") if "curso" in row else row.get("Curso")
            gp = row.get("grupo_principal") if "grupo_principal" in row else row.get("GrupoPrincipal")
            
            tipo_col = "tipo" if "tipo" in df_clases.columns else "Tipo"
            grupo_col = "grupo" if "grupo" in df_clases.columns else "Grupo"
            curso_col = "curso" if "curso" in df_clases.columns else "Curso"
            gp_col = "grupo_principal" if "grupo_principal" in df_clases.columns else "GrupoPrincipal"

            sem_col = "semestre" if "semestre" in df_clases.columns else "Semestre"
            s = row.get("semestre") if "semestre" in row else row.get("Semestre")

            filtro = df_clases[~df_clases[tipo_col].astype(str).str.lower().str.contains("teor")].copy()
            if c is not None and curso_col in df_clases.columns:
                filtro = filtro[filtro[curso_col] == c]
            if s is not None and sem_col in df_clases.columns:
                filtro = filtro[filtro[sem_col] == s]
            if gp is not None and gp_col in df_clases.columns:
                filtro = filtro[filtro[gp_col] == gp]

            subgs = set()
            for _, r in filtro.iterrows():
                t = str(r.get(tipo_col, "")).lower()
                if "prob" not in t and "aula" not in t:
                    subgs.add(str(r[grupo_col]).strip())
            if subgs:
                return subgs

        if grupo_str in ["2", "G2", "16", "18"]:
            return {"45", "46", "47", "48"}
        return {"41", "42", "43", "44", "45"}

    # Laboratorio (subgrupo atómico)
    return {grupo_str}


def aplicar_restriccion_estudiantes(model, df_clases, interval_vars):
    """
    DURA: Un alumno no puede tener dos clases al mismo tiempo.
    - Dos sesiones del mismo curso y grupo_principal con alumnos en común no pueden solaparse.
    """
    sesiones = df_clases.to_dict("records")
    n = len(sesiones)
    alumnos_por_sesion = [obtener_subgrupos_estudiantes(s, df_clases) for s in sesiones]

    for i in range(n):
        for j in range(i + 1, n):
            s1 = sesiones[i]
            s2 = sesiones[j]

            # Si pertenecen a cursos o grupos principales distintos, son alumnos totalmente independientes
            c1, c2 = s1.get("curso"), s2.get("curso")
            gp1, gp2 = s1.get("grupo_principal"), s2.get("grupo_principal")
            if c1 is not None and c2 is not None and c1 != c2:
                continue
            if gp1 is not None and gp2 is not None and gp1 != gp2:
                continue

            # Comparten estudiantes si la intersección de sus subgrupos no es vacía
            if alumnos_por_sesion[i].intersection(alumnos_por_sesion[j]):
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



# RESTRICCIONES BLANDAS (Criterios a optimizar en la función objetivo)

def aplicar_restricciones_blandas(model, df_clases, start_vars, aula_assign=None, total_slots=30, aula_preferida=None, horas_por_dia=6):
    """
    RESTRICCIONES BLANDAS (Función Objetivo a minimizar):
    1. Penalizar clases en las dos últimas horas del viernes (slots 28 y 29).
    2. Minimizar horas libres (huecos) entre clases para los alumnos en un mismo día.
    3. Opcional: Penalizar desvíos de aula preferida solo si se especifica explícitamente.
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
            penalizaciones.append(es_viernes_tarde * 20)

    # 2. Minimizar huecos (horas libres) entre clases para cada subgrupo atómico de alumnos
    subgrupos_atomicos = set()
    for _, row in df_clases.iterrows():
        t = str(row.get("tipo", "")).lower()
        if "teor" not in t and "prob" not in t and "aula" not in t:
            subgrupos_atomicos.add(str(row["grupo"]).strip())

    if subgrupos_atomicos:
        start_is = {}
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            dur = int(row["duracion_horas"])
            v_start = obtener_var_inicio(s_id)
            if v_start is not None:
                for t in range(total_slots - dur + 1):
                    b = model.NewBoolVar(f"st_{s_id}_{t}")
                    model.Add(v_start == t).OnlyEnforceIf(b)
                    model.Add(v_start != t).OnlyEnforceIf(b.Not())
                    start_is[s_id, t] = b

        # Precomputamos a qué sesiones asiste cada subgrupo atómico
        sesiones_por_subgrupo = {}
        for g in subgrupos_atomicos:
            ses_g = []
            for _, row in df_clases.iterrows():
                subs = obtener_subgrupos_estudiantes(row, df_clases)
                if g in subs:
                    ses_g.append(row)
            sesiones_por_subgrupo[g] = ses_g

        ocupado = {}
        for g in sorted(subgrupos_atomicos):
            ses_g = sesiones_por_subgrupo[g]
            for t in range(total_slots):
                covering = []
                for row in ses_g:
                    s_id = str(row["id_sesion"]).strip()
                    dur = int(row["duracion_horas"])
                    for k in range(dur):
                        st_slot = t - k
                        if (s_id, st_slot) in start_is:
                            covering.append(start_is[s_id, st_slot])
                oc = model.NewBoolVar(f"oc_{g}_{t}")
                if covering:
                    model.Add(oc == sum(covering))
                else:
                    model.Add(oc == 0)
                ocupado[g, t] = oc

        num_dias = total_slots // horas_por_dia
        for g in sorted(subgrupos_atomicos):
            for d in range(num_dias):
                day_slots = [d * horas_por_dia + h for h in range(horas_por_dia)]
                for h in range(1, horas_por_dia - 1):
                    t = day_slots[h]
                    hay_antes = model.NewBoolVar(f"ha_{g}_{d}_{h}")
                    hay_desp = model.NewBoolVar(f"hd_{g}_{d}_{h}")
                    model.AddMaxEquality(hay_antes, [ocupado[g, day_slots[k]] for k in range(h)])
                    model.AddMaxEquality(hay_desp, [ocupado[g, day_slots[k]] for k in range(h + 1, horas_por_dia)])

                    es_hueco = model.NewBoolVar(f"gap_{g}_{d}_{h}")
                    model.AddBoolAnd([hay_antes, hay_desp, ocupado[g, t].Not()]).OnlyEnforceIf(es_hueco)
                    model.AddBoolOr([hay_antes.Not(), hay_desp.Not(), ocupado[g, t]]).OnlyEnforceIf(es_hueco.Not())
                    penalizaciones.append(es_hueco * 15)

    # 3. Priorizar aula preferida solo si se ha configurado expresamente
    if aula_preferida and aula_assign:
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            tipo = str(row.get("tipo", "")).strip().lower()

            if "teor" in tipo:
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