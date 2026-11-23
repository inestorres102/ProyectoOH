"""
Ejecutor aislado en subproceso para el Simulador en Vivo del cuadro de mandos.

Al ejecutarse como proceso independiente para cada titulación (GII, GCID, GIFM),
evita colisiones en `sys.modules` (ya que las tres carpetas definen módulos con
los mismos nombres: `modelo_base`, `restricciones`, `visualizador`) y escribe
todos los resultados en un directorio temporal sin modificar los ficheros
versionados del repositorio.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

REPO_ROOT = Path(__file__).resolve().parent


def run_gii(args, out_dir: Path):
    src_dir = REPO_ROOT / "GII" / "src"
    sys.path.insert(0, str(src_dir))

    import pandas as pd
    from metaheuristica_sa import SimulatedAnnealingTimetabling
    from modelo_base import _resolver_turno
    from visualizador import exportar_horario_png

    df_clases = pd.read_csv(REPO_ROOT / "GII" / "datos" / "clases.csv")
    df_aulas = pd.read_csv(REPO_ROOT / "GII" / "datos" / "aulas.csv")

    df_sub = df_clases[
        (df_clases["curso"] == args.curso)
        & (df_clases["semestre"] == args.cuatrimestre)
    ].copy()
    if args.grupo_principal is not None and args.grupo_principal > 0:
        df_sub = df_sub[df_sub["grupo_principal"] == args.grupo_principal].copy()

    if df_sub.empty:
        raise ValueError("No hay sesiones para la combinación seleccionada en GII.")

    es_tarde = (args.grupo_principal == 3)
    sem_str = "1er SEMESTRE" if args.cuatrimestre == 1 else "2º SEMESTRE"
    gp_txt = f"Grupo {args.grupo_principal}" if args.grupo_principal != 3 else "Grupo 3 (Tarde)"

    t0 = time.time()
    historial = []
    if args.metodo == "CP-SAT":
        df_res = _resolver_turno(
            df_sub, df_aulas, es_tarde=es_tarde, curso=args.curso, semestre=args.cuatrimestre
        )
        tiempo = time.time() - t0
        if df_res.empty:
            raise RuntimeError("CP-SAT no encontró solución factible.")

        # Evaluamos la calidad del horario CP-SAT con la misma función de energía del SA
        sa_eval = SimulatedAnnealingTimetabling(df_sub, df_aulas, es_tarde=es_tarde, semilla=args.semilla)
        estado_cp = {str(r["Sesion"]).strip(): (int(r["Slot"]), str(r["Aula"]).strip()) for _, r in df_res.iterrows()}
        energia, duras, blandas = sa_eval.calcular_energia(estado_cp)
        titulo = f"SIMULACIÓN EN VIVO (CP-SAT) — {args.curso}º GII ({gp_txt} - {sem_str})"
    else:
        sa = SimulatedAnnealingTimetabling(
            df_clases=df_sub,
            df_aulas=df_aulas,
            es_tarde=es_tarde,
            t_inicial=args.t_inicial,
            t_final=0.01,
            alpha=args.alpha,
            iter_por_temp=args.iter_por_temp,
            semilla=args.semilla,
        )
        mejor_estado, energia, historial, tiempo = sa.optimizar(verbose=False)
        _, duras, blandas = sa.calcular_energia(mejor_estado)
        df_res = sa.convertir_a_dataframe(
            mejor_estado,
            curso=args.curso,
            semestre=args.cuatrimestre,
            grupo_principal=args.grupo_principal,
        )
        titulo = f"SIMULACIÓN EN VIVO (SA PROPIO) — {args.curso}º GII ({gp_txt} - {sem_str})"

    png_path = out_dir / "horario_live.png"
    exportar_horario_png(df_res, ruta_salida=str(png_path), titulo=titulo, abrir_al_terminar=False)
    csv_path = out_dir / "horario_live.csv"
    df_res.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary = {
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
    }
    return summary


def run_gcid(args, out_dir: Path):
    src_dir = REPO_ROOT / "GCID" / "src"
    sys.path.insert(0, str(src_dir))

    import math
    import random
    import pandas as pd
    from ortools.sat.python import cp_model
    import metaheuristica as gcid_sa
    import restricciones as gcid_rest
    from visualizador import exportar_horario_png

    df_clases, df_aulas = gcid_sa.cargar_datos(cuatrimestre=args.cuatrimestre)
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_etiquetas = [
        "08:30-09:30", "09:30-10:30", "10:30-11:30",
        "11:30-12:30", "12:30-13:30", "13:30-14:30",
    ]
    historial = []

    if args.metodo == "CP-SAT":
        t0 = time.time()
        horas_por_dia = 6
        total_slots = 30
        model = cp_model.CpModel()
        start_vars, end_vars, interval_vars = {}, {}, {}

        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            duracion = int(row["duracion_horas"])
            start = model.NewIntVar(0, total_slots - duracion, f"start_{s_id}")
            end = model.NewIntVar(duracion, total_slots, f"end_{s_id}")
            interval = model.NewIntervalVar(start, duracion, end, f"interval_{s_id}")
            start_vars[s_id] = start
            end_vars[s_id] = end
            interval_vars[s_id] = interval

        gcid_rest.aplicar_restriccion_estudiantes(model, df_clases, interval_vars)
        gcid_rest.aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, horas_por_dia)
        gcid_rest.aplicar_restriccion_profesores(model, df_clases, interval_vars)
        aula_asignada = gcid_rest.aplicar_restriccion_aulas(model, df_clases, df_aulas, start_vars, end_vars)
        gcid_rest.aplicar_restriccion_sin_huecos(model, df_clases, start_vars, end_vars, horas_por_dia)
        gcid_rest.aplicar_distribucion_teoria_primero(model, df_clases, start_vars, horas_por_dia)
        if args.cuatrimestre == 2:
            gcid_rest.aplicar_restriccion_dias_libres_practicas(model, df_clases, start_vars)
        gcid_rest.aplicar_restricciones_blandas(
            model, df_clases, start_vars, aula_asignada, total_slots=total_slots, aula_preferida="A2-5"
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 35.0
        status = solver.Solve(model)
        tiempo = time.time() - t0
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError("CP-SAT no encontró solución factible para GCID.")

        asignaciones = []
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            slot_ini = solver.Value(start_vars[s_id])
            aula_elegida = "Sin aula"
            for a_id in df_aulas["id_aula"].astype(str):
                v = aula_asignada.get((s_id, a_id))
                if v is not None and solver.Value(v) == 1:
                    aula_elegida = a_id
                    break
            asignaciones.append({
                "Slot": slot_ini,
                "Curso": int(row["curso"]),
                "Sesion": s_id,
                "Asignatura": row["asignatura"],
                "Tipo": row["tipo"],
                "Grupo": row["grupo"],
                "Dia": dias[slot_ini // 6],
                "Hora": horas_etiquetas[slot_ini % 6],
                "Duracion": f"{int(row['duracion_horas'])}h",
                "Aula": aula_elegida,
                "Profesor": row["profesor"],
            })

        df_all = pd.DataFrame(asignaciones).sort_values(by="Slot")
        duras, huecos, blandas = 0, 0, int(solver.ObjectiveValue())
        energia = float(blandas)
        etiqueta = "CP-SAT (EN VIVO)"
    else:
        random.seed(args.semilla)
        sesiones, meta, pares_est, pares_prof, grupos_sesiones = gcid_sa.preparar_estructuras(
            df_clases, df_aulas, args.cuatrimestre
        )
        estado_actual = {
            s_id: (
                random.choice(meta[s_id]["slots_validos"]),
                random.choice(meta[s_id]["aulas_validas"]),
            )
            for s_id in sesiones
        }
        coste_actual, vd_a, hh_a, cb_a = gcid_sa.evaluar_estado(
            estado_actual, sesiones, meta, pares_est, pares_prof, grupos_sesiones
        )

        mejor_estado = dict(estado_actual)
        mejor_coste = coste_actual
        mejor_metricas = (vd_a, hh_a, cb_a)

        max_iter = int(args.max_iter)
        temp_inicial = 5000.0
        temp_final = 0.1
        ratio = (temp_final / temp_inicial) ** (1.0 / max(max_iter, 1))
        temperatura = temp_inicial
        paso = max(1, max_iter // 250)

        t0 = time.time()
        historial.append({
            "iteracion": 0,
            "temperatura": temperatura,
            "energia_actual": float(coste_actual),
            "mejor_energia": float(mejor_coste),
        })

        for it in range(1, max_iter + 1):
            vecino = gcid_sa.generar_vecino(estado_actual, sesiones, meta)
            coste_v, vd_v, hh_v, cb_v = gcid_sa.evaluar_estado(
                vecino, sesiones, meta, pares_est, pares_prof, grupos_sesiones
            )
            delta = coste_v - coste_actual
            if delta <= 0 or random.random() < math.exp(-delta / max(temperatura, 1e-9)):
                estado_actual = vecino
                coste_actual = coste_v
                if coste_actual < mejor_coste:
                    mejor_estado = dict(estado_actual)
                    mejor_coste = coste_actual
                    mejor_metricas = (vd_v, hh_v, cb_v)

            if it % paso == 0 or it == max_iter:
                historial.append({
                    "iteracion": it,
                    "temperatura": float(temperatura),
                    "energia_actual": float(coste_actual),
                    "mejor_energia": float(mejor_coste),
                })
            temperatura *= ratio

        tiempo = time.time() - t0
        duras, huecos, blandas = mejor_metricas
        energia = float(mejor_coste)

        asignaciones = []
        for s_id in sesiones:
            slot_ini, aula_elegida = mejor_estado[s_id]
            m = meta[s_id]
            asignaciones.append({
                "Slot": slot_ini,
                "Curso": m["curso"],
                "Sesion": s_id,
                "Asignatura": m["asignatura"],
                "Tipo": m["tipo"],
                "Grupo": m["grupo"],
                "Dia": dias[slot_ini // 6],
                "Hora": horas_etiquetas[slot_ini % 6],
                "Duracion": f"{m['dur']}h",
                "Aula": aula_elegida,
                "Profesor": m["profesor"],
            })
        df_all = pd.DataFrame(asignaciones).sort_values(by="Slot")
        etiqueta = "RECOCIDO SIMULADO (EN VIVO)"

    df_curso = df_all[df_all["Curso"] == args.curso].copy().reset_index(drop=True)
    png_path = out_dir / "horario_live.png"
    exportar_horario_png(
        df_resultado=df_curso,
        ruta_salida=str(png_path),
        curso=args.curso,
        cuatrimestre=args.cuatrimestre,
        abrir_al_terminar=False,
        etiqueta_metodo=etiqueta,
    )
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
    }


def run_gifm(args, out_dir: Path):
    src_dir = REPO_ROOT / "GIFM" / "src"
    sys.path.insert(0, str(src_dir))

    import pandas as pd
    from ortools.sat.python import cp_model
    import modelo_base as gifm_mb
    from metaheuristica.recocido_simulado import ejecutar_recocido_simulado
    from visualizador import exportar_horario_png

    df_clases, df_aulas = gifm_mb.cargar_datos()
    df_filtrado = df_clases[
        (df_clases["curso"] == args.curso)
        & (df_clases["cuatrimestre"] == args.cuatrimestre)
    ].copy().reset_index(drop=True)

    if df_filtrado.empty:
        raise ValueError("No hay sesiones para la combinación seleccionada en GIFM.")

    df_bloques = gifm_mb.dividir_en_bloques(df_filtrado)
    horas_por_dia = gifm_mb.HORAS_POR_DIA_NORMAL

    t0 = time.time()
    solver, estado, start_vars, end_vars, aula_asignada = gifm_mb.resolver_modelo(
        df_bloques, df_aulas, horas_por_dia
    )
    if (
        estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        and (args.curso, args.cuatrimestre) == gifm_mb.HORARIO_AMPLIABLE
    ):
        horas_por_dia = gifm_mb.HORAS_POR_DIA_AMPLIADO
        solver, estado, start_vars, end_vars, aula_asignada = gifm_mb.resolver_modelo(
            df_bloques, df_aulas, horas_por_dia
        )

    if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("CP-SAT no encontró solución factible para GIFM.")
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
            "Slot": slot,
            "Sesion": fila["id_bloque"],
            "Sesion_original": fila["id_sesion"],
            "Asignatura": fila["asignatura"],
            "Tipo": fila["tipo"],
            "Grupo": fila["grupo"],
            "Dia": gifm_mb.obtener_dia(slot, horas_por_dia),
            "Hora": gifm_mb.obtener_hora(slot, dur, horas_por_dia),
            "Duracion": f"{dur}h",
            "Duracion_horas": dur,
            "Aula": aula,
            "Profesor": fila["profesor"],
            "Semanas_activas": str(semanas),
        })
    df_cp = pd.DataFrame(resultados).sort_values(by=["Slot", "Asignatura"]).reset_index(drop=True)

    png_cp = out_dir / "horario_cp.png"
    exportar_horario_png(
        df_cp,
        ruta_salida=str(png_cp),
        abrir_al_terminar=False,
        titulo=f"SIMULACIÓN EN VIVO (CP-SAT) — {args.curso}º GIFM ({args.cuatrimestre}º CUATRIMESTRE)",
        horas_por_dia=horas_por_dia,
    )

    if args.metodo == "CP-SAT":
        csv_path = out_dir / "horario_live.csv"
        df_cp.to_csv(csv_path, index=False, encoding="utf-8-sig")
        return {
            "titulacion": "GIFM",
            "metodo": "CP-SAT",
            "curso": args.curso,
            "cuatrimestre": args.cuatrimestre,
            "sesiones": int(len(df_cp)),
            "tiempo_s": round(float(t_cp), 3),
            "energia": float(solver.ObjectiveValue()),
            "violaciones_duras": 0,
            "coste_blando": float(solver.ObjectiveValue()),
            "factible": True,
            "jornada_ampliada": bool(horas_por_dia == gifm_mb.HORAS_POR_DIA_AMPLIADO),
            "png_principal": str(png_cp),
            "csv_principal": str(csv_path),
            "historial": [],
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
    exportar_horario_png(
        df_sa,
        ruta_salida=str(png_sa),
        abrir_al_terminar=False,
        titulo=f"SIMULACIÓN EN VIVO (SA HÍBRIDO) — {args.curso}º GIFM ({args.cuatrimestre}º CUATRIMESTRE)",
        horas_por_dia=horas_por_dia,
    )
    csv_path = out_dir / "horario_live.csv"
    df_sa.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {
        "titulacion": "GIFM",
        "metodo": "Recocido Simulado (Híbrido CP-SAT -> SA)",
        "curso": args.curso,
        "cuatrimestre": args.cuatrimestre,
        "sesiones": int(len(df_sa)),
        "tiempo_s": round(float(t_cp + res_sa["tiempo"]), 3),
        "tiempo_cp_s": round(float(t_cp), 3),
        "tiempo_sa_s": round(float(res_sa["tiempo"]), 3),
        "energia": float(res_sa["mejor_coste"]),
        "coste_inicial": float(res_sa["coste_inicial"]),
        "violaciones_duras": 0 if res_sa["valido"] else 1,
        "coste_blando": float(res_sa["mejor_coste"]),
        "aceptados": int(res_sa["aceptados"]),
        "mejoras": int(res_sa["mejoras"]),
        "factible": bool(res_sa["valido"]),
        "jornada_ampliada": bool(horas_por_dia == gifm_mb.HORAS_POR_DIA_AMPLIADO),
        "png_principal": str(png_sa),
        "png_comparativa_cp": str(png_cp),
        "csv_principal": str(csv_path),
        "historial": [],
    }


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

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
