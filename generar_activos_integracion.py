"""
Generador de activos unificados para la rama de integración:
1. Genera los horarios de Recocido Simulado de GII (GII/horarios_SA/...) para
   igualar la cobertura CP-SAT vs. SA de GCID y GIFM.
2. Exporta `dashboard_data/horarios_unificados.csv` con las asignaciones
   resueltas (CP-SAT y SA) de las 3 titulaciones (GII, GCID y GIFM) para
   alimentar la Vista Interactiva Unificada y las tablas filtrables de `app.py`.

Se ejecuta en subprocesos aislados por titulación para evitar colisiones de
módulos (`modelo_base`, `restricciones`, `visualizador`) y sin modificar ningún
archivo fuente de GCID ni GIFM.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "dashboard_data"


def _normalizar_modalidad(tipo: str) -> str:
    t = str(tipo).strip().lower()
    if "teor" in t:
        return "Teoría"
    if "aula" in t or "problem" in t:
        return "Práctica de Aula"
    return "Laboratorio"


def _worker_gii(out_csv: Path):
    sys.path.insert(0, str(REPO_ROOT / "GII" / "src"))
    import pandas as pd
    from metaheuristica_sa import SimulatedAnnealingTimetabling
    from modelo_base import _resolver_turno
    from visualizador import exportar_horario_png

    df_clases = pd.read_csv(REPO_ROOT / "GII" / "datos" / "clases.csv")
    df_aulas = pd.read_csv(REPO_ROOT / "GII" / "datos" / "aulas.csv")

    registros = []
    for curso in [1, 2, 3, 4]:
        for sem in [1, 2]:
            sub_cs = df_clases[(df_clases["curso"] == curso) & (df_clases["semestre"] == sem)].copy()
            if sub_cs.empty:
                continue

            # --- CP-SAT (mañana acoplado + tarde independiente, igual que GII/src/modelo_base.py) ---
            sub_m = sub_cs[sub_cs["grupo_principal"] != 3].copy()
            sub_t = sub_cs[sub_cs["grupo_principal"] == 3].copy()
            partes_cp = []
            if not sub_m.empty:
                partes_cp.append(_resolver_turno(sub_m, df_aulas, es_tarde=False, curso=curso, semestre=sem))
            if not sub_t.empty:
                partes_cp.append(_resolver_turno(sub_t, df_aulas, es_tarde=True, curso=curso, semestre=sem))
            df_cp = pd.concat([p for p in partes_cp if not p.empty], ignore_index=True)

            for _, r in df_cp.iterrows():
                registros.append({
                    "Titulacion": "GII",
                    "Metodo": "CP-SAT",
                    "Curso": int(curso),
                    "Cuatrimestre": int(sem),
                    "GrupoPrincipal": int(r.get("GrupoPrincipal", 1)),
                    "Sesion": str(r["Sesion"]),
                    "Asignatura": str(r["Asignatura"]),
                    "Modalidad": _normalizar_modalidad(r["Tipo"]),
                    "TipoOriginal": str(r["Tipo"]),
                    "Grupo": str(r["Grupo"]),
                    "Dia": str(r["Dia"]),
                    "Hora": str(r["Hora"]),
                    "Slot": int(r["Slot"]),
                    "DuracionHoras": int(str(r["Duracion"]).replace("h", "")),
                    "Aula": str(r["Aula"]),
                    "Profesor": str(r["Profesor"]),
                    "Semanas": "1-15",
                })

            # --- RECOCIDO SIMULADO (generando PNGs en GII/horarios_SA/...) ---
            partes_sa = []
            # Resolver mañana (grupos 1 y 2 juntos para evitar colisiones de aulas) y tarde (grupo 3)
            for es_tarde, sub_turno in [(False, sub_m), (True, sub_t)]:
                if sub_turno.empty:
                    continue
                mejor_df = None
                mejor_e = float("inf")
                for intento, seed in enumerate([42, 7, 13, 99, 123]):
                    iters = 150 if intento == 0 else 220
                    sa = SimulatedAnnealingTimetabling(
                        df_clases=sub_turno,
                        df_aulas=df_aulas,
                        es_tarde=es_tarde,
                        t_inicial=140.0,
                        t_final=0.01,
                        alpha=0.985,
                        iter_por_temp=iters,
                        semilla=seed,
                    )
                    est, energia, _, _ = sa.optimizar(verbose=False)
                    _, duras, _ = sa.calcular_energia(est)
                    df_cand = sa.convertir_a_dataframe(est, curso=curso, semestre=sem)
                    if duras == 0 and energia < mejor_e:
                        mejor_e = energia
                        mejor_df = df_cand
                        break
                    if energia < mejor_e:
                        mejor_e = energia
                        mejor_df = df_cand
                if mejor_df is not None and not mejor_df.empty:
                    partes_sa.append(mejor_df)

            df_sa = pd.concat(partes_sa, ignore_index=True)

            # Guardar PNGs de SA con la misma estructura de carpetas que CP-SAT
            sem_carpeta = "1er_Semestre" if sem == 1 else "2do_Semestre"
            sem_str = "1er SEMESTRE" if sem == 1 else "2º SEMESTRE"
            carpeta_sa = REPO_ROOT / "GII" / "horarios_SA" / f"{curso}GII" / sem_carpeta
            carpeta_sa.mkdir(parents=True, exist_ok=True)

            gps = sorted(df_sa["GrupoPrincipal"].dropna().unique())
            if len(gps) > 1:
                gps_txt = " y ".join([f"Grupo {int(g)}" if g != 3 else "Grupo 3 (Tarde)" for g in gps])
                exportar_horario_png(
                    df_sa,
                    ruta_salida=str(carpeta_sa / "horario_conjunto.png"),
                    titulo=f"CALENDARIO ACADÉMICO — {curso}º GII ({gps_txt} - {sem_str}) — RECOCIDO SIMULADO",
                    abrir_al_terminar=False,
                )
                for gp in gps:
                    df_gp = df_sa[df_sa["GrupoPrincipal"] == gp].copy()
                    txt_ind = f"Grupo {int(gp)}" if gp != 3 else "Grupo 3 (Tarde)"
                    exportar_horario_png(
                        df_gp,
                        ruta_salida=str(carpeta_sa / f"horario_Grupo_{int(gp)}.png"),
                        titulo=f"CALENDARIO ACADÉMICO — {curso}º GII ({txt_ind} - {sem_str}) — RECOCIDO SIMULADO",
                        abrir_al_terminar=False,
                    )
            else:
                gp_num = int(gps[0])
                txt_ind = f"Grupo {gp_num}" if gp_num != 3 else "Grupo 3 (Tarde)"
                exportar_horario_png(
                    df_sa,
                    ruta_salida=str(carpeta_sa / f"horario_Grupo_{gp_num}.png"),
                    titulo=f"CALENDARIO ACADÉMICO — {curso}º GII ({txt_ind} - {sem_str}) — RECOCIDO SIMULADO",
                    abrir_al_terminar=False,
                )

            for _, r in df_sa.iterrows():
                registros.append({
                    "Titulacion": "GII",
                    "Metodo": "Recocido Simulado",
                    "Curso": int(curso),
                    "Cuatrimestre": int(sem),
                    "GrupoPrincipal": int(r.get("GrupoPrincipal", 1)),
                    "Sesion": str(r["Sesion"]),
                    "Asignatura": str(r["Asignatura"]),
                    "Modalidad": _normalizar_modalidad(r["Tipo"]),
                    "TipoOriginal": str(r["Tipo"]),
                    "Grupo": str(r["Grupo"]),
                    "Dia": str(r["Dia"]),
                    "Hora": str(r["Hora"]),
                    "Slot": int(r["Slot"]),
                    "DuracionHoras": int(str(r["Duracion"]).replace("h", "")),
                    "Aula": str(r["Aula"]),
                    "Profesor": str(r["Profesor"]),
                    "Semanas": "1-15",
                })
            print(f"[GII] {curso}º S{sem} completado (CP-SAT={len(df_cp)}, SA={len(df_sa)})")

    pd.DataFrame(registros).to_csv(out_csv, index=False, encoding="utf-8-sig")


def _worker_gcid(out_csv: Path):
    sys.path.insert(0, str(REPO_ROOT / "GCID" / "src"))
    import math
    import random
    import pandas as pd
    from ortools.sat.python import cp_model
    import metaheuristica as gcid_sa
    import restricciones as gcid_rest

    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_etiquetas = [
        "08:30-09:30", "09:30-10:30", "10:30-11:30",
        "11:30-12:30", "12:30-13:30", "13:30-14:30",
    ]
    registros = []

    for cuatri in [1, 2]:
        df_clases, df_aulas = gcid_sa.cargar_datos(cuatrimestre=cuatri)

        # --- CP-SAT ---
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

        gcid_rest.aplicar_restriccion_estudiantes(model, df_clases, interval_vars)
        gcid_rest.aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, 6)
        gcid_rest.aplicar_restriccion_profesores(model, df_clases, interval_vars)
        aula_asignada = gcid_rest.aplicar_restriccion_aulas(model, df_clases, df_aulas, start_vars, end_vars)
        gcid_rest.aplicar_restriccion_sin_huecos(model, df_clases, start_vars, end_vars, 6)
        gcid_rest.aplicar_distribucion_teoria_primero(model, df_clases, start_vars, 6)
        if cuatri == 2:
            gcid_rest.aplicar_restriccion_dias_libres_practicas(model, df_clases, start_vars)
        gcid_rest.aplicar_restricciones_blandas(model, df_clases, start_vars, aula_asignada, total_slots=30, aula_preferida="A2-5")

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), f"GCID CP-SAT C{cuatri} infactible"

        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            slot = solver.Value(start_vars[s_id])
            aula = "Sin aula"
            for a_id in df_aulas["id_aula"].astype(str):
                v = aula_asignada.get((s_id, a_id))
                if v is not None and solver.Value(v) == 1:
                    aula = a_id
                    break
            registros.append({
                "Titulacion": "GCID",
                "Metodo": "CP-SAT",
                "Curso": int(row["curso"]),
                "Cuatrimestre": int(cuatri),
                "GrupoPrincipal": 1,
                "Sesion": s_id,
                "Asignatura": str(row["asignatura"]).strip(),
                "Modalidad": _normalizar_modalidad(row["tipo"]),
                "TipoOriginal": str(row["tipo"]).strip(),
                "Grupo": str(row["grupo"]).strip(),
                "Dia": dias[slot // 6],
                "Hora": horas_etiquetas[slot % 6],
                "Slot": int(slot),
                "DuracionHoras": int(row["duracion_horas"]),
                "Aula": aula,
                "Profesor": str(row["profesor"]).strip(),
                "Semanas": "1-15",
            })

        # --- RECOCIDO SIMULADO (misma semilla=42 y max_iter=60000 que GCID/src/metaheuristica.py) ---
        random.seed(42)
        sesiones, meta, pares_est, pares_prof, grupos_sesiones = gcid_sa.preparar_estructuras(df_clases, df_aulas, cuatri)
        estado = {s_id: (random.choice(meta[s_id]["slots_validos"]), random.choice(meta[s_id]["aulas_validas"])) for s_id in sesiones}
        coste, vd, hh, cb = gcid_sa.evaluar_estado(estado, sesiones, meta, pares_est, pares_prof, grupos_sesiones)
        mejor_estado, mejor_coste = dict(estado), coste
        max_iter, t0, tf = 60000, 5000.0, 0.1
        ratio = (tf / t0) ** (1.0 / max_iter)
        temp = t0
        for _ in range(1, max_iter + 1):
            vecino = gcid_sa.generar_vecino(estado, sesiones, meta)
            cv, _, _, _ = gcid_sa.evaluar_estado(vecino, sesiones, meta, pares_est, pares_prof, grupos_sesiones)
            d = cv - coste
            if d <= 0 or random.random() < math.exp(-d / temp):
                estado, coste = vecino, cv
                if coste < mejor_coste:
                    mejor_estado, mejor_coste = dict(estado), coste
            temp *= ratio

        for s_id in sesiones:
            slot, aula = mejor_estado[s_id]
            m = meta[s_id]
            registros.append({
                "Titulacion": "GCID",
                "Metodo": "Recocido Simulado",
                "Curso": int(m["curso"]),
                "Cuatrimestre": int(cuatri),
                "GrupoPrincipal": 1,
                "Sesion": s_id,
                "Asignatura": m["asignatura"],
                "Modalidad": _normalizar_modalidad(m["tipo"]),
                "TipoOriginal": m["tipo"],
                "Grupo": m["grupo"],
                "Dia": dias[slot // 6],
                "Hora": horas_etiquetas[slot % 6],
                "Slot": int(slot),
                "DuracionHoras": int(m["dur"]),
                "Aula": aula,
                "Profesor": m["profesor"],
                "Semanas": "1-15",
            })
        print(f"[GCID] C{cuatri} completado (CP-SAT + SA, mejor_coste SA={mejor_coste})")

    pd.DataFrame(registros).to_csv(out_csv, index=False, encoding="utf-8-sig")


def _worker_gifm(out_csv: Path):
    sys.path.insert(0, str(REPO_ROOT / "GIFM" / "src"))
    import pandas as pd
    from ortools.sat.python import cp_model
    import modelo_base as gifm_mb

    df_clases, df_aulas = gifm_mb.cargar_datos()
    registros = []

    for curso in [1, 2, 3, 4]:
        for cuatri in [1, 2]:
            # --- SA ya resuelto y guardado en GIFM/resultados/horario_*_recocido.csv ---
            p_sa_csv = REPO_ROOT / "GIFM" / "resultados" / f"horario_{curso}GIFM_{cuatri}cuatri_recocido.csv"
            if p_sa_csv.exists():
                df_sa = pd.read_csv(p_sa_csv, encoding="utf-8-sig")
                for _, r in df_sa.iterrows():
                    registros.append({
                        "Titulacion": "GIFM",
                        "Metodo": "Recocido Simulado",
                        "Curso": int(curso),
                        "Cuatrimestre": int(cuatri),
                        "GrupoPrincipal": 1,
                        "Sesion": str(r["Sesion"]),
                        "Asignatura": str(r["Asignatura"]),
                        "Modalidad": _normalizar_modalidad(r["Tipo"]),
                        "TipoOriginal": str(r["Tipo"]),
                        "Grupo": str(r["Grupo"]),
                        "Dia": str(r["Dia"]),
                        "Hora": str(r["Hora"]),
                        "Slot": int(r["Slot"]),
                        "DuracionHoras": int(r["Duracion_horas"]),
                        "Aula": str(r["Aula"]),
                        "Profesor": str(r["Profesor"]),
                        "Semanas": str(r.get("Semanas_activas", "1-15")),
                    })

            # --- CP-SAT ---
            df_f = df_clases[(df_clases["curso"] == curso) & (df_clases["cuatrimestre"] == cuatri)].copy().reset_index(drop=True)
            df_b = gifm_mb.dividir_en_bloques(df_f)
            hpd = gifm_mb.HORAS_POR_DIA_NORMAL
            solver, estado, start_vars, end_vars, aula_asignada = gifm_mb.resolver_modelo(df_b, df_aulas, hpd)
            if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE) and (curso, cuatri) == gifm_mb.HORARIO_AMPLIABLE:
                hpd = gifm_mb.HORAS_POR_DIA_AMPLIADO
                solver, estado, start_vars, end_vars, aula_asignada = gifm_mb.resolver_modelo(df_b, df_aulas, hpd)

            if estado in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                for i, fila in df_b.iterrows():
                    slot = solver.Value(start_vars[i])
                    dur = int(fila["duracion_horas"])
                    aula = gifm_mb.obtener_aula_asignada(solver, aula_asignada, i)
                    sem_txt = fila.get("semanas_activas", "1-15")
                    if pd.isna(sem_txt):
                        sem_txt = "1-15"
                    registros.append({
                        "Titulacion": "GIFM",
                        "Metodo": "CP-SAT",
                        "Curso": int(curso),
                        "Cuatrimestre": int(cuatri),
                        "GrupoPrincipal": 1,
                        "Sesion": str(fila["id_bloque"]),
                        "Asignatura": str(fila["asignatura"]),
                        "Modalidad": _normalizar_modalidad(fila["tipo"]),
                        "TipoOriginal": str(fila["tipo"]),
                        "Grupo": str(fila["grupo"]),
                        "Dia": gifm_mb.obtener_dia(slot, hpd),
                        "Hora": gifm_mb.obtener_hora(slot, dur, hpd),
                        "Slot": int(slot),
                        "DuracionHoras": dur,
                        "Aula": aula,
                        "Profesor": str(fila["profesor"]),
                        "Semanas": str(sem_txt),
                    })
            print(f"[GIFM] {curso}º C{cuatri} completado")

    pd.DataFrame(registros).to_csv(out_csv, index=False, encoding="utf-8-sig")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        deg = sys.argv[2]
        out_csv = DATA_DIR / f"_tmp_{deg.lower()}.csv"
        if deg == "GII":
            _worker_gii(out_csv)
        elif deg == "GCID":
            _worker_gcid(out_csv)
        elif deg == "GIFM":
            _worker_gifm(out_csv)
        return

    import pandas as pd
    partes = []
    for deg in ["GII", "GCID", "GIFM"]:
        print(f"\n>>> Ejecutando worker aislado para {deg}...")
        r = subprocess.run([sys.executable, __file__, "--worker", deg], cwd=str(REPO_ROOT), check=True)
        p = DATA_DIR / f"_tmp_{deg.lower()}.csv"
        partes.append(pd.read_csv(p, encoding="utf-8-sig"))
        p.unlink(missing_ok=True)

    df_all = pd.concat(partes, ignore_index=True)
    out_final = DATA_DIR / "horarios_unificados.csv"
    df_all.to_csv(out_final, index=False, encoding="utf-8-sig")
    print(f"\n[OK] Exportado {out_final} con {len(df_all)} filas:")
    print(df_all.groupby(["Titulacion", "Metodo"]).size())


if __name__ == "__main__":
    main()
