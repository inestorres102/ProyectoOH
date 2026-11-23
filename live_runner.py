"""
Ejecutor aislado en subproceso para el Simulador en Vivo, Laboratorio What-If,
Replay paso a paso del Recocido Simulado y Carrera de Algoritmos (Aleatorio vs CP-SAT vs SA).

Al ejecutarse como proceso independiente por titulación (GII, GCID, GIFM), evita
colisiones en `sys.modules` y escribe todos los resultados en un directorio temporal
sin modificar los ficheros versionados del repositorio.
"""

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

REPO_ROOT = Path(__file__).resolve().parent
DIAS_NORM = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
DIAS_ASCII = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]


def _norm_modalidad(tipo: str) -> str:
    t = str(tipo).strip().lower()
    if "teor" in t:
        return "Teoría"
    if "aula" in t or "problem" in t:
        return "Práctica de Aula"
    return "Laboratorio"


def _filtrar_aulas_cerradas(df_aulas, aulas_cerradas_str: str):
    if not aulas_cerradas_str:
        return df_aulas
    cerradas = {a.strip() for a in aulas_cerradas_str.split(",") if a.strip()}
    if not cerradas:
        return df_aulas
    col_id = "id_aula" if "id_aula" in df_aulas.columns else df_aulas.columns[0]
    df_out = df_aulas[~df_aulas[col_id].astype(str).str.strip().isin(cerradas)].copy()
    if df_out.empty:
        raise ValueError("Has cerrado demasiadas aulas: no quedan espacios compatibles.")
    return df_out


def _aplicar_bloqueo_profesor_sa(slots_validos_dict, prof_dict, prof_bloqueado: str, dia_bloqueado: int, horas_por_dia: int = 6):
    if not prof_bloqueado or dia_bloqueado < 0:
        return
    p_target = prof_bloqueado.strip().lower()
    for s_id, prof_val in prof_dict.items():
        if str(prof_val).strip().lower() == p_target:
            filtrados = [t for t in slots_validos_dict[s_id] if (t // horas_por_dia) != dia_bloqueado]
            if not filtrados:
                raise ValueError(f"El bloqueo de {prof_bloqueado} deja sin franjas válidas la sesión {s_id}.")
            slots_validos_dict[s_id] = filtrados


def _resolver_gii_cpsat_whatif(df_sub, df_aulas, es_tarde, curso, semestre, prof_bloqueado="", dia_bloqueado=-1):
    from ortools.sat.python import cp_model
    import pandas as pd
    import restricciones as gii_rest

    horas_etiquetas = (
        ["14:30-15:30", "15:30-16:30", "16:30-17:30", "17:30-18:30", "18:30-19:30", "19:30-20:30"]
        if es_tarde
        else ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]
    )
    horas_por_dia = 6
    total_slots = 30

    model = cp_model.CpModel()
    start_vars, end_vars, interval_vars = {}, {}, {}

    for _, row in df_sub.iterrows():
        s_id = str(row["id_sesion"]).strip()
        dur = int(row["duracion_horas"])
        start = model.NewIntVar(0, total_slots - dur, f"start_{s_id}")
        end = model.NewIntVar(dur, total_slots, f"end_{s_id}")
        interval = model.NewIntervalVar(start, dur, end, f"interval_{s_id}")
        start_vars[s_id] = start
        end_vars[s_id] = end
        interval_vars[s_id] = interval

        if prof_bloqueado and dia_bloqueado >= 0:
            if str(row["profesor"]).strip().lower() == prof_bloqueado.strip().lower():
                ini_bloq = dia_bloqueado * horas_por_dia
                fin_bloq = ini_bloq + horas_por_dia - 1
                model.AddAllowedAssignments(
                    [start],
                    [[t] for t in range(total_slots - dur + 1) if not (ini_bloq <= t <= fin_bloq)],
                )

    gii_rest.aplicar_restriccion_estudiantes(model, df_sub, interval_vars)
    gii_rest.aplicar_restriccion_cambio_dia(model, df_sub, start_vars, end_vars, horas_por_dia)
    gii_rest.aplicar_restriccion_profesores(model, df_sub, interval_vars)
    aula_asignada = gii_rest.aplicar_restriccion_aulas(model, df_sub, df_aulas, start_vars, end_vars)
    gii_rest.aplicar_restricciones_blandas(model, df_sub, start_vars, total_slots=total_slots)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("CP-SAT no encontró solución factible con las incidencias What-If aplicadas.")

    asignaciones = []
    for _, row in df_sub.iterrows():
        s_id = str(row["id_sesion"]).strip()
        slot = solver.Value(start_vars[s_id])
        aula_elegida = "Sin aula"
        for a_id in df_aulas["id_aula"].astype(str):
            var_a = aula_asignada.get((s_id, a_id))
            if var_a is not None:
                try:
                    if solver.Value(var_a) == 1:
                        aula_elegida = a_id
                        break
                except Exception:
                    pass
        asignaciones.append({
            "Slot": slot,
            "Sesion": s_id,
            "Asignatura": str(row["asignatura"]).strip(),
            "Tipo": str(row["tipo"]).strip(),
            "Modalidad": _norm_modalidad(row["tipo"]),
            "Grupo": str(row["grupo"]).strip(),
            "Dia": DIAS_ASCII[slot // horas_por_dia],
            "Hora": horas_etiquetas[slot % horas_por_dia],
            "Duracion": f"{int(row['duracion_horas'])}h",
            "DuracionHoras": int(row["duracion_horas"]),
            "Aula": aula_elegida,
            "Profesor": str(row["profesor"]).strip(),
            "Curso": int(row.get("curso", curso)),
            "Semestre": int(row.get("semestre", semestre)),
            "GrupoPrincipal": int(row.get("grupo_principal", 1)),
            "Semanas": "1-15",
        })
    return pd.DataFrame(asignaciones).sort_values(by="Slot").reset_index(drop=True)


def _estado_gii_a_bloques(sa, estado, curso, semestre, gp):
    bloques = []
    for s_id in sa.sesiones:
        slot, aula = estado[s_id]
        dur = sa.duracion[s_id]
        row = sa.info_sesion[s_id]
        bloques.append({
            "Slot": int(slot),
            "Sesion": s_id,
            "Asignatura": str(row["asignatura"]).strip(),
            "Modalidad": _norm_modalidad(row["tipo"]),
            "Grupo": str(row["grupo"]).strip(),
            "Dia": DIAS_NORM[slot // sa.horas_por_dia],
            "Hora": sa.horas_etiquetas[slot % sa.horas_por_dia],
            "DuracionHoras": int(dur),
            "Aula": str(aula),
            "Profesor": str(row["profesor"]).strip(),
            "Curso": int(row.get("curso", curso)),
            "GrupoPrincipal": int(row.get("grupo_principal", gp)),
            "Semanas": "1-15",
        })
    return bloques


def _ejecutar_gii_sa_con_replay(sa, curso, semestre, gp, max_snapshots=10):
    """Ejecuta el Recocido Simulado de GII capturando snapshots completos para el Replay interactivo."""
    t0 = time.time()
    estado_actual = sa.generar_solucion_inicial()
    energia_actual, duras_actual, blandas_actual = sa.calcular_energia(estado_actual)
    mejor_estado = estado_actual.copy()
    mejor_energia, mejor_duras, mejor_blandas = energia_actual, duras_actual, blandas_actual

    temperatura = sa.t_inicial
    total_iter = 0
    paso = 0
    historial = []
    snapshots_raw = [{
        "iteracion": 0,
        "temperatura": round(float(temperatura), 2),
        "energia": float(energia_actual),
        "duras": int(duras_actual),
        "blandas": float(blandas_actual),
        "estado": estado_actual.copy(),
    }]

    # Capturas espaciadas logarítmicamente para ver bien la caída de conflictos y la compactación
    pasos_captura = {2, 5, 10, 20, 40, 75, 120, 180}

    while temperatura > sa.t_final:
        aceptados = 0
        for _ in range(sa.iter_por_temp):
            total_iter += 1
            vecino = sa.generar_vecino(estado_actual)
            e_v, d_v, b_v = sa.calcular_energia(vecino)
            delta = e_v - energia_actual
            if delta <= 0 or random.random() < math.exp(-delta / max(temperatura, 1e-9)):
                estado_actual = vecino
                energia_actual, duras_actual, blandas_actual = e_v, d_v, b_v
                aceptados += 1
                if energia_actual < mejor_energia:
                    mejor_estado = estado_actual.copy()
                    mejor_energia, mejor_duras, mejor_blandas = energia_actual, duras_actual, blandas_actual

        tasa = aceptados / sa.iter_por_temp
        historial.append({
            "paso": paso,
            "iteracion": total_iter,
            "temperatura": float(temperatura),
            "energia_actual": float(energia_actual),
            "mejor_energia": float(mejor_energia),
            "duras": int(mejor_duras),
            "blandas": float(mejor_blandas),
            "tasa_aceptacion": float(tasa),
        })

        if paso in pasos_captura and len(snapshots_raw) < max_snapshots - 1:
            snapshots_raw.append({
                "iteracion": total_iter,
                "temperatura": round(float(temperatura), 2),
                "energia": float(energia_actual),
                "duras": int(duras_actual),
                "blandas": float(blandas_actual),
                "estado": estado_actual.copy(),
            })

        if mejor_duras == 0 and temperatura < (sa.t_inicial * 0.1) and tasa < 0.05:
            break
        temperatura *= sa.alpha
        paso += 1

    tiempo = time.time() - t0
    snapshots_raw.append({
        "iteracion": total_iter,
        "temperatura": round(float(temperatura), 2),
        "energia": float(mejor_energia),
        "duras": int(mejor_duras),
        "blandas": float(mejor_blandas),
        "estado": mejor_estado.copy(),
        "es_final": True,
    })

    snapshots = []
    for snap in snapshots_raw:
        snapshots.append({
            "iteracion": snap["iteracion"],
            "temperatura": snap["temperatura"],
            "energia": snap["energia"],
            "duras": snap["duras"],
            "blandas": snap["blandas"],
            "es_final": snap.get("es_final", False),
            "bloques": _estado_gii_a_bloques(sa, snap["estado"], curso, semestre, gp),
        })

    return mejor_estado, mejor_energia, mejor_duras, mejor_blandas, historial, snapshots, tiempo


def run_gii(args, out_dir: Path):
    src_dir = REPO_ROOT / "GII" / "src"
    sys.path.insert(0, str(src_dir))

    import pandas as pd
    from metaheuristica_sa import SimulatedAnnealingTimetabling
    from visualizador import exportar_horario_png

    df_clases = pd.read_csv(REPO_ROOT / "GII" / "datos" / "clases.csv")
    df_aulas = _filtrar_aulas_cerradas(pd.read_csv(REPO_ROOT / "GII" / "datos" / "aulas.csv"), args.aulas_cerradas)

    df_sub = df_clases[(df_clases["curso"] == args.curso) & (df_clases["semestre"] == args.cuatrimestre)].copy()
    if args.grupo_principal is not None and args.grupo_principal > 0:
        df_sub = df_sub[df_sub["grupo_principal"] == args.grupo_principal].copy()
    if df_sub.empty:
        raise ValueError("No hay sesiones para la combinación seleccionada en GII.")

    es_tarde = (args.grupo_principal == 3)
    sem_str = "1er SEMESTRE" if args.cuatrimestre == 1 else "2º SEMESTRE"
    gp_txt = f"Grupo {args.grupo_principal}" if args.grupo_principal != 3 else "Grupo 3 (Tarde)"

    def _crear_sa(semilla_val):
        sa_obj = SimulatedAnnealingTimetabling(
            df_clases=df_sub,
            df_aulas=df_aulas,
            es_tarde=es_tarde,
            t_inicial=args.t_inicial,
            t_final=0.01,
            alpha=args.alpha,
            iter_por_temp=args.iter_por_temp,
            peso_hueco=args.peso_hueco,
            peso_viernes=args.peso_viernes,
            semilla=semilla_val,
        )
        _aplicar_bloqueo_profesor_sa(sa_obj.slots_validos, sa_obj.profesor, args.prof_bloqueado, args.dia_bloqueado, 6)
        return sa_obj

    # ---- MODO CARRERA DE LOS 3 ALGORITMOS ----
    if args.modo_carrera:
        sa_eval = _crear_sa(args.semilla)
        # 1. Búsqueda Aleatoria (2.500 intentos rápidos para demo en directo)
        t0 = time.time()
        e_rand, d_rand, b_rand = float("inf"), 999, 999
        for _ in range(2500):
            st_r = sa_eval.generar_solucion_inicial()
            er, dr, br = sa_eval.calcular_energia(st_r)
            if er < e_rand:
                e_rand, d_rand, b_rand = er, dr, br
        t_rand = time.time() - t0

        # 2. CP-SAT Exacto
        t0 = time.time()
        df_cp = _resolver_gii_cpsat_whatif(
            df_sub, df_aulas, es_tarde, args.curso, args.cuatrimestre, args.prof_bloqueado, args.dia_bloqueado
        )
        t_cp = time.time() - t0
        estado_cp = {str(r["Sesion"]).strip(): (int(r["Slot"]), str(r["Aula"]).strip()) for _, r in df_cp.iterrows()}
        e_cp, d_cp, b_cp = sa_eval.calcular_energia(estado_cp)

        # 3. Recocido Simulado propio (con Replay)
        sa_run = _crear_sa(args.semilla)
        est_sa, e_sa, d_sa, b_sa, historial, snapshots, t_sa = _ejecutar_gii_sa_con_replay(
            sa_run, args.curso, args.cuatrimestre, args.grupo_principal
        )
        df_sa = sa_run.convertir_a_dataframe(est_sa, curso=args.curso, semestre=args.cuatrimestre, grupo_principal=args.grupo_principal)
        df_sa["Modalidad"] = df_sa["Tipo"].apply(_norm_modalidad)
        df_sa["DuracionHoras"] = df_sa["Duracion"].astype(str).str.replace("h", "").astype(int)
        df_sa["Semanas"] = "1-15"

        png_path = out_dir / "horario_live.png"
        exportar_horario_png(df_sa, ruta_salida=str(png_path), titulo=f"CARRERA EN VIVO (SA) — {args.curso}º GII ({gp_txt})", abrir_al_terminar=False)
        csv_path = out_dir / "horario_live.csv"
        df_sa.to_csv(csv_path, index=False, encoding="utf-8-sig")

        return {
            "titulacion": "GII",
            "metodo": "Carrera (Aleatorio vs CP-SAT vs SA)",
            "curso": args.curso,
            "cuatrimestre": args.cuatrimestre,
            "sesiones": int(len(df_sa)),
            "tiempo_s": round(float(t_rand + t_cp + t_sa), 3),
            "energia": float(e_sa),
            "violaciones_duras": int(d_sa),
            "coste_blando": float(b_sa),
            "factible": bool(d_sa == 0),
            "png_principal": str(png_path),
            "csv_principal": str(csv_path),
            "historial": historial,
            "snapshots": snapshots,
            "bloques_cp": _estado_gii_a_bloques(sa_eval, estado_cp, args.curso, args.cuatrimestre, args.grupo_principal),
            "bloques_sa": snapshots[-1]["bloques"],
            "carrera": [
                {"Metodo": "Búsqueda Aleatoria (2.500 iter.)", "Tiempo_s": round(t_rand, 3), "Violaciones_Duras": int(d_rand), "Coste_Blando": float(b_rand), "Energia": float(e_rand), "Factible": bool(d_rand == 0)},
                {"Metodo": "OR-Tools CP-SAT (Exacto)", "Tiempo_s": round(t_cp, 3), "Violaciones_Duras": int(d_cp), "Coste_Blando": float(b_cp), "Energia": float(e_cp), "Factible": bool(d_cp == 0)},
                {"Metodo": "Recocido Simulado (Propio)", "Tiempo_s": round(t_sa, 3), "Violaciones_Duras": int(d_sa), "Coste_Blando": float(b_sa), "Energia": float(e_sa), "Factible": bool(d_sa == 0)},
            ],
        }

    # ---- MODO INDIVIDUAL (CP-SAT o SA con What-If + Replay) ----
    historial, snapshots = [], []
    if args.metodo == "CP-SAT":
        t0 = time.time()
        df_res = _resolver_gii_cpsat_whatif(
            df_sub, df_aulas, es_tarde, args.curso, args.cuatrimestre, args.prof_bloqueado, args.dia_bloqueado
        )
        tiempo = time.time() - t0
        sa_eval = _crear_sa(args.semilla)
        estado_cp = {str(r["Sesion"]).strip(): (int(r["Slot"]), str(r["Aula"]).strip()) for _, r in df_res.iterrows()}
        energia, duras, blandas = sa_eval.calcular_energia(estado_cp)
        titulo = f"SIMULACIÓN EN VIVO (CP-SAT) — {args.curso}º GII ({gp_txt} - {sem_str})"
    else:
        sa = _crear_sa(args.semilla)
        mejor_estado, energia, duras, blandas, historial, snapshots, tiempo = _ejecutar_gii_sa_con_replay(
            sa, args.curso, args.cuatrimestre, args.grupo_principal
        )
        df_res = sa.convertir_a_dataframe(mejor_estado, curso=args.curso, semestre=args.cuatrimestre, grupo_principal=args.grupo_principal)
        titulo = f"SIMULACIÓN EN VIVO (SA PROPIO) — {args.curso}º GII ({gp_txt} - {sem_str})"

    png_path = out_dir / "horario_live.png"
    exportar_horario_png(df_res, ruta_salida=str(png_path), titulo=titulo, abrir_al_terminar=False)
    csv_path = out_dir / "horario_live.csv"
    df_res.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {
        "titulacion": "GII",
        "metodo": args.metodo,
        "curso": args.curso,
        "cuatrimestre": args.cuatrimestre,
        "sesiones": int(len(df_res)),
        "tiempo_s": round(float(tiempo), 3),
        "energia": float(energia),
        "violaciones_duras": int(duras),
        "coste_blando": float(blandas),
        "factible": bool(duras == 0),
        "png_principal": str(png_path),
        "csv_principal": str(csv_path),
        "historial": historial,
        "snapshots": snapshots,
    }


def _estado_gcid_curso_a_bloques(estado, sesiones, meta, curso_filtro):
    horas_etiquetas = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]
    bloques = []
    for s_id in sesiones:
        m = meta[s_id]
        if int(m["curso"]) != int(curso_filtro):
            continue
        slot, aula = estado[s_id]
        bloques.append({
            "Slot": int(slot),
            "Sesion": s_id,
            "Asignatura": m["asignatura"],
            "Modalidad": _norm_modalidad(m["tipo"]),
            "Grupo": str(m["grupo"]),
            "Dia": DIAS_NORM[slot // 6],
            "Hora": horas_etiquetas[slot % 6],
            "DuracionHoras": int(m["dur"]),
            "Aula": str(aula),
            "Profesor": m["profesor"],
            "Curso": int(m["curso"]),
            "GrupoPrincipal": 1,
            "Semanas": "1-15",
        })
    return bloques


def run_gcid(args, out_dir: Path):
    src_dir = REPO_ROOT / "GCID" / "src"
    sys.path.insert(0, str(src_dir))

    import pandas as pd
    from ortools.sat.python import cp_model
    import metaheuristica as gcid_sa
    import restricciones as gcid_rest
    from visualizador import exportar_horario_png

    df_clases, df_aulas_raw = gcid_sa.cargar_datos(cuatrimestre=args.cuatrimestre)
    df_aulas = _filtrar_aulas_cerradas(df_aulas_raw, args.aulas_cerradas)
    horas_etiquetas = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]

    def _run_gcid_cp():
        t0 = time.time()
        model = cp_model.CpModel()
        start_vars, end_vars, interval_vars = {}, {}, {}
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            dur = int(row["duracion_horas"])
            start = model.NewIntVar(0, 30 - dur, f"start_{s_id}")
            end = model.NewIntVar(dur, 30, f"end_{s_id}")
            interval = model.NewIntervalVar(start, dur, end, f"interval_{s_id}")
            start_vars[s_id] = start
            end_vars[s_id] = end
            interval_vars[s_id] = interval
            if args.prof_bloqueado and args.dia_bloqueado >= 0:
                if str(row["profesor"]).strip().lower() == args.prof_bloqueado.strip().lower():
                    ini_b, fin_b = args.dia_bloqueado * 6, args.dia_bloqueado * 6 + 5
                    model.AddAllowedAssignments([start], [[t] for t in range(30 - dur + 1) if not (ini_b <= t <= fin_b)])

        gcid_rest.aplicar_restriccion_estudiantes(model, df_clases, interval_vars)
        gcid_rest.aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, 6)
        gcid_rest.aplicar_restriccion_profesores(model, df_clases, interval_vars)
        aula_asignada = gcid_rest.aplicar_restriccion_aulas(model, df_clases, df_aulas, start_vars, end_vars)
        gcid_rest.aplicar_restriccion_sin_huecos(model, df_clases, start_vars, end_vars, 6)
        gcid_rest.aplicar_distribucion_teoria_primero(model, df_clases, start_vars, 6)
        if args.cuatrimestre == 2:
            gcid_rest.aplicar_restriccion_dias_libres_practicas(model, df_clases, start_vars)
        gcid_rest.aplicar_restricciones_blandas(model, df_clases, start_vars, aula_asignada, total_slots=30, aula_preferida="A2-5")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 35.0
        status = solver.Solve(model)
        t_cp = time.time() - t0
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError("CP-SAT no encontró solución factible para GCID con las incidencias aplicadas.")

        asignaciones, estado_cp = [], {}
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            slot = solver.Value(start_vars[s_id])
            aula = "Sin aula"
            for a_id in df_aulas["id_aula"].astype(str):
                v = aula_asignada.get((s_id, a_id))
                if v is not None and solver.Value(v) == 1:
                    aula = a_id
                    break
            estado_cp[s_id] = (slot, aula)
            asignaciones.append({
                "Slot": slot, "Curso": int(row["curso"]), "Sesion": s_id,
                "Asignatura": row["asignatura"], "Tipo": row["tipo"], "Grupo": row["grupo"],
                "Dia": DIAS_ASCII[slot // 6], "Hora": horas_etiquetas[slot % 6],
                "Duracion": f"{int(row['duracion_horas'])}h", "Aula": aula, "Profesor": row["profesor"],
            })
        return pd.DataFrame(asignaciones).sort_values(by="Slot"), estado_cp, int(solver.ObjectiveValue()), t_cp

    def _run_gcid_sa():
        random.seed(args.semilla)
        sesiones, meta, pares_est, pares_prof, grupos_sesiones = gcid_sa.preparar_estructuras(df_clases, df_aulas, args.cuatrimestre)
        if args.prof_bloqueado and args.dia_bloqueado >= 0:
            _aplicar_bloqueo_profesor_sa(
                {s: meta[s]["slots_validos"] for s in sesiones},
                {s: meta[s]["profesor"] for s in sesiones},
                args.prof_bloqueado,
                args.dia_bloqueado,
                6,
            )
            # Re-asignar lista filtrada dentro de meta
            p_t = args.prof_bloqueado.strip().lower()
            for s in sesiones:
                if str(meta[s]["profesor"]).strip().lower() == p_t:
                    meta[s]["slots_validos"] = [t for t in meta[s]["slots_validos"] if (t // 6) != args.dia_bloqueado]

        estado_actual = {s_id: (random.choice(meta[s_id]["slots_validos"]), random.choice(meta[s_id]["aulas_validas"])) for s_id in sesiones}
        coste_actual, vd_a, hh_a, cb_a = gcid_sa.evaluar_estado(estado_actual, sesiones, meta, pares_est, pares_prof, grupos_sesiones)
        mejor_estado, mejor_coste, mejor_metricas = dict(estado_actual), coste_actual, (vd_a, hh_a, cb_a)

        max_iter = int(args.max_iter)
        t_ini, t_fin = 5000.0, 0.1
        ratio = (t_fin / t_ini) ** (1.0 / max(max_iter, 1))
        temp = t_ini
        paso = max(1, max_iter // 250)
        snap_step = max(1, max_iter // 9)

        t0 = time.time()
        historial = [{"iteracion": 0, "temperatura": temp, "energia_actual": float(coste_actual), "mejor_energia": float(mejor_coste)}]
        snapshots = [{
            "iteracion": 0, "temperatura": round(temp, 1), "energia": float(coste_actual),
            "duras": int(vd_a + hh_a), "blandas": float(cb_a), "es_final": False,
            "bloques": _estado_gcid_curso_a_bloques(estado_actual, sesiones, meta, args.curso),
        }]

        for it in range(1, max_iter + 1):
            vecino = gcid_sa.generar_vecino(estado_actual, sesiones, meta)
            c_v, vd_v, hh_v, cb_v = gcid_sa.evaluar_estado(vecino, sesiones, meta, pares_est, pares_prof, grupos_sesiones)
            delta = c_v - coste_actual
            if delta <= 0 or random.random() < math.exp(-delta / max(temp, 1e-9)):
                estado_actual, coste_actual, vd_a, hh_a, cb_a = vecino, c_v, vd_v, hh_v, cb_v
                if coste_actual < mejor_coste:
                    mejor_estado, mejor_coste, mejor_metricas = dict(estado_actual), coste_actual, (vd_v, hh_v, cb_v)

            if it % paso == 0 or it == max_iter:
                historial.append({"iteracion": it, "temperatura": float(temp), "energia_actual": float(coste_actual), "mejor_energia": float(mejor_coste)})
            if it % snap_step == 0 and len(snapshots) < 9:
                snapshots.append({
                    "iteracion": it, "temperatura": round(temp, 1), "energia": float(coste_actual),
                    "duras": int(vd_a + hh_a), "blandas": float(cb_a), "es_final": False,
                    "bloques": _estado_gcid_curso_a_bloques(estado_actual, sesiones, meta, args.curso),
                })
            temp *= ratio

        tiempo = time.time() - t0
        vd_f, hh_f, cb_f = mejor_metricas
        snapshots.append({
            "iteracion": max_iter, "temperatura": round(temp, 2), "energia": float(mejor_coste),
            "duras": int(vd_f + hh_f), "blandas": float(cb_f), "es_final": True,
            "bloques": _estado_gcid_curso_a_bloques(mejor_estado, sesiones, meta, args.curso),
        })

        asignaciones = []
        for s_id in sesiones:
            slot, aula = mejor_estado[s_id]
            m = meta[s_id]
            asignaciones.append({
                "Slot": slot, "Curso": m["curso"], "Sesion": s_id,
                "Asignatura": m["asignatura"], "Tipo": m["tipo"], "Grupo": m["grupo"],
                "Dia": DIAS_ASCII[slot // 6], "Hora": horas_etiquetas[slot % 6],
                "Duracion": f"{m['dur']}h", "Aula": aula, "Profesor": m["profesor"],
            })
        return pd.DataFrame(asignaciones).sort_values(by="Slot"), sesiones, meta, pares_est, pares_prof, grupos_sesiones, mejor_coste, mejor_metricas, historial, snapshots, tiempo

    if args.modo_carrera:
        df_cp, estado_cp, bl_cp, t_cp = _run_gcid_cp()
        df_sa, sesiones, meta, pares_est, pares_prof, grupos_sesiones, e_sa, (vd_sa, hh_sa, cb_sa), historial, snapshots, t_sa = _run_gcid_sa()

        # Baseline aleatorio (1.500 intentos)
        t0 = time.time()
        e_r, vd_r, hh_r, cb_r = float("inf"), 999, 999, 999
        for _ in range(1500):
            st_r = {s_id: (random.choice(meta[s_id]["slots_validos"]), random.choice(meta[s_id]["aulas_validas"])) for s_id in sesiones}
            cr, vr, hr, br = gcid_sa.evaluar_estado(st_r, sesiones, meta, pares_est, pares_prof, grupos_sesiones)
            if cr < e_r:
                e_r, vd_r, hh_r, cb_r = cr, vr, hr, br
        t_r = time.time() - t0

        df_curso = df_sa[df_sa["Curso"] == args.curso].copy().reset_index(drop=True)
        png_path = out_dir / "horario_live.png"
        exportar_horario_png(df_curso, ruta_salida=str(png_path), curso=args.curso, cuatrimestre=args.cuatrimestre, abrir_al_terminar=False, etiqueta_metodo="RECOCIDO SIMULADO (CARRERA)")
        csv_path = out_dir / "horario_live.csv"
        df_curso.to_csv(csv_path, index=False, encoding="utf-8-sig")

        return {
            "titulacion": "GCID",
            "metodo": "Carrera (Aleatorio vs CP-SAT vs SA)",
            "curso": args.curso,
            "cuatrimestre": args.cuatrimestre,
            "sesiones": int(len(df_sa)),
            "tiempo_s": round(float(t_r + t_cp + t_sa), 3),
            "energia": float(e_sa),
            "violaciones_duras": int(vd_sa),
            "horas_hueco": int(hh_sa),
            "coste_blando": float(cb_sa),
            "factible": bool(vd_sa == 0 and hh_sa == 0),
            "png_principal": str(png_path),
            "csv_principal": str(csv_path),
            "historial": historial,
            "snapshots": snapshots,
            "bloques_cp": _estado_gcid_curso_a_bloques(estado_cp, sesiones, meta, args.curso),
            "bloques_sa": snapshots[-1]["bloques"],
            "carrera": [
                {"Metodo": "Búsqueda Aleatoria (1.500 iter.)", "Tiempo_s": round(t_r, 3), "Violaciones_Duras": int(vd_r + hh_r), "Coste_Blando": float(cb_r), "Energia": float(e_r), "Factible": bool(vd_r == 0 and hh_r == 0)},
                {"Metodo": "OR-Tools CP-SAT (Exacto)", "Tiempo_s": round(t_cp, 3), "Violaciones_Duras": 0, "Coste_Blando": float(bl_cp), "Energia": float(bl_cp), "Factible": True},
                {"Metodo": "Recocido Simulado (Propio)", "Tiempo_s": round(t_sa, 3), "Violaciones_Duras": int(vd_sa + hh_sa), "Coste_Blando": float(cb_sa), "Energia": float(e_sa), "Factible": bool(vd_sa == 0 and hh_sa == 0)},
            ],
        }

    historial, snapshots = [], []
    if args.metodo == "CP-SAT":
        df_all, _, blandas, tiempo = _run_gcid_cp()
        duras, huecos, energia = 0, 0, float(blandas)
        etiqueta = "CP-SAT (EN VIVO)"
    else:
        df_all, _, _, _, _, _, energia, (duras, huecos, blandas), historial, snapshots, tiempo = _run_gcid_sa()
        etiqueta = "RECOCIDO SIMULADO (EN VIVO)"

    df_curso = df_all[df_all["Curso"] == args.curso].copy().reset_index(drop=True)
    png_path = out_dir / "horario_live.png"
    exportar_horario_png(df_curso, ruta_salida=str(png_path), curso=args.curso, cuatrimestre=args.cuatrimestre, abrir_al_terminar=False, etiqueta_metodo=etiqueta)
    csv_path = out_dir / "horario_live.csv"
    df_curso.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {
        "titulacion": "GCID",
        "metodo": args.metodo,
        "curso": args.curso,
        "cuatrimestre": args.cuatrimestre,
        "sesiones": int(len(df_all)),
        "sesiones_curso": int(len(df_curso)),
        "tiempo_s": round(float(tiempo), 3),
        "energia": float(energia),
        "violaciones_duras": int(duras),
        "horas_hueco": int(huecos),
        "coste_blando": float(blandas),
        "factible": bool(duras == 0 and huecos == 0),
        "png_principal": str(png_path),
        "csv_principal": str(csv_path),
        "historial": historial,
        "snapshots": snapshots,
    }


def run_gifm(args, out_dir: Path):
    src_dir = REPO_ROOT / "GIFM" / "src"
    sys.path.insert(0, str(src_dir))

    import pandas as pd
    from ortools.sat.python import cp_model
    import modelo_base as gifm_mb
    from metaheuristica.recocido_simulado import ejecutar_recocido_simulado
    from visualizador import exportar_horario_png

    df_clases, df_aulas_raw = gifm_mb.cargar_datos()
    df_aulas = _filtrar_aulas_cerradas(df_aulas_raw, args.aulas_cerradas)

    df_filtrado = df_clases[(df_clases["curso"] == args.curso) & (df_clases["cuatrimestre"] == args.cuatrimestre)].copy().reset_index(drop=True)
    if df_filtrado.empty:
        raise ValueError("No hay sesiones para la combinación seleccionada en GIFM.")

    df_bloques = gifm_mb.dividir_en_bloques(df_filtrado)
    horas_por_dia = gifm_mb.HORAS_POR_DIA_NORMAL

    t0 = time.time()
    solver, estado, start_vars, end_vars, aula_asignada = gifm_mb.resolver_modelo(df_bloques, df_aulas, horas_por_dia)
    if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE) and (args.curso, args.cuatrimestre) == gifm_mb.HORARIO_AMPLIABLE:
        horas_por_dia = gifm_mb.HORAS_POR_DIA_AMPLIADO
        solver, estado, start_vars, end_vars, aula_asignada = gifm_mb.resolver_modelo(df_bloques, df_aulas, horas_por_dia)
    if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("CP-SAT no encontró solución factible para GIFM con las aulas seleccionadas.")
    t_cp = time.time() - t0

    resultados = []
    for i, fila in df_bloques.iterrows():
        slot = solver.Value(start_vars[i])
        dur = int(fila["duracion_horas"])
        aula = gifm_mb.obtener_aula_asignada(solver, aula_asignada, i)
        semanas = fila.get("semanas_activas", "")
        if pd.isna(semanas):
            semanas = ""
        resultados.append({
            "Slot": slot, "Sesion": fila["id_bloque"], "Sesion_original": fila["id_sesion"],
            "Asignatura": fila["asignatura"], "Tipo": fila["tipo"], "Grupo": fila["grupo"],
            "Dia": gifm_mb.obtener_dia(slot, horas_por_dia),
            "Hora": gifm_mb.obtener_hora(slot, dur, horas_por_dia),
            "Duracion": f"{dur}h", "Duracion_horas": dur, "Aula": aula,
            "Profesor": fila["profesor"], "Semanas_activas": str(semanas),
        })
    df_cp = pd.DataFrame(resultados).sort_values(by=["Slot", "Asignatura"]).reset_index(drop=True)

    png_cp = out_dir / "horario_cp.png"
    exportar_horario_png(df_cp, ruta_salida=str(png_cp), abrir_al_terminar=False, titulo=f"SIMULACIÓN EN VIVO (CP-SAT) — {args.curso}º GIFM ({args.cuatrimestre}º C)", horas_por_dia=horas_por_dia)

    if args.metodo == "CP-SAT" and not args.modo_carrera:
        csv_path = out_dir / "horario_live.csv"
        df_cp.to_csv(csv_path, index=False, encoding="utf-8-sig")
        return {
            "titulacion": "GIFM", "metodo": "CP-SAT", "curso": args.curso, "cuatrimestre": args.cuatrimestre,
            "sesiones": int(len(df_cp)), "tiempo_s": round(float(t_cp), 3),
            "energia": float(solver.ObjectiveValue()), "violaciones_duras": 0,
            "coste_blando": float(solver.ObjectiveValue()), "factible": True,
            "png_principal": str(png_cp), "csv_principal": str(csv_path), "historial": [], "snapshots": [],
        }

    res_sa = ejecutar_recocido_simulado(
        df_inicial=df_cp,
        horas_por_dia=horas_por_dia,
        temperatura_inicial=args.t_inicial,
        temperatura_final=0.01,
        factor_enfriamiento=args.alpha,
        iteraciones_maximas=args.max_iter,
        semilla=args.semilla,
        mostrar_progreso=False,
    )
    df_sa = res_sa["horario"].copy()
    df_sa["Dia"] = df_sa["Slot"].apply(lambda s: gifm_mb.obtener_dia(s, horas_por_dia))
    df_sa["Hora"] = df_sa.apply(lambda f: gifm_mb.obtener_hora(f["Slot"], f["Duracion_horas"], horas_por_dia), axis=1)
    df_sa = df_sa.sort_values(by=["Slot", "Asignatura"]).reset_index(drop=True)

    png_sa = out_dir / "horario_sa.png"
    exportar_horario_png(df_sa, ruta_salida=str(png_sa), abrir_al_terminar=False, titulo=f"SIMULACIÓN EN VIVO (SA HÍBRIDO) — {args.curso}º GIFM ({args.cuatrimestre}º C)", horas_por_dia=horas_por_dia)
    csv_path = out_dir / "horario_live.csv"
    df_sa.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary = {
        "titulacion": "GIFM",
        "metodo": "Carrera (CP-SAT vs SA Híbrido)" if args.modo_carrera else "Recocido Simulado (Híbrido CP-SAT -> SA)",
        "curso": args.curso, "cuatrimestre": args.cuatrimestre,
        "sesiones": int(len(df_sa)),
        "tiempo_s": round(float(t_cp + res_sa["tiempo"]), 3),
        "energia": float(res_sa["mejor_coste"]),
        "violaciones_duras": 0 if res_sa["valido"] else 1,
        "coste_blando": float(res_sa["mejor_coste"]),
        "factible": bool(res_sa["valido"]),
        "png_principal": str(png_sa),
        "png_comparativa_cp": str(png_cp),
        "csv_principal": str(csv_path),
        "historial": [],
        "snapshots": [],
    }
    if args.modo_carrera:
        summary["carrera"] = [
            {"Metodo": "OR-Tools CP-SAT (Exacto)", "Tiempo_s": round(t_cp, 3), "Violaciones_Duras": 0, "Coste_Blando": float(res_sa["coste_inicial"]), "Energia": float(res_sa["coste_inicial"]), "Factible": True},
            {"Metodo": "Recocido Simulado (Híbrido)", "Tiempo_s": round(float(res_sa["tiempo"]), 3), "Violaciones_Duras": 0 if res_sa["valido"] else 1, "Coste_Blando": float(res_sa["mejor_coste"]), "Energia": float(res_sa["mejor_coste"]), "Factible": bool(res_sa["valido"])},
        ]
    return summary


def main():
    parser = argparse.ArgumentParser(description="Ejecutor en vivo aislado para EII-ULPGC")
    parser.add_argument("--titulacion", required=True, choices=["GII", "GCID", "GIFM"])
    parser.add_argument("--metodo", required=True, choices=["CP-SAT", "SA"])
    parser.add_argument("--curso", type=int, required=True)
    parser.add_argument("--cuatrimestre", type=int, required=True)
    parser.add_argument("--grupo_principal", type=int, default=1)
    parser.add_argument("--t_inicial", type=float, default=120.0)
    parser.add_argument("--alpha", type=float, default=0.985)
    parser.add_argument("--iter_por_temp", type=int, default=140)
    parser.add_argument("--max_iter", type=int, default=20000)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--aulas_cerradas", default="")
    parser.add_argument("--prof_bloqueado", default="")
    parser.add_argument("--dia_bloqueado", type=int, default=-1)
    parser.add_argument("--peso_hueco", type=int, default=15)
    parser.add_argument("--peso_viernes", type=int, default=10)
    parser.add_argument("--modo_carrera", action="store_true")
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.titulacion == "GII":
        summary = run_gii(args, out_dir)
    elif args.titulacion == "GCID":
        summary = run_gcid(args, out_dir)
    else:
        summary = run_gifm(args, out_dir)

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
