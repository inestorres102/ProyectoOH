import os
import pandas as pd
from ortools.sat.python import cp_model

# Importamos las restricciones desde el nuevo fichero 'restricciones.py'
from restricciones import (
    aplicar_restriccion_estudiantes,
    aplicar_restriccion_cambio_dia,
    aplicar_restriccion_profesores,
    aplicar_restriccion_aulas,
    aplicar_restricciones_blandas
)

from visualizador import exportar_horario_png


horas_manana = [
    "08:30-09:30", "09:30-10:30", "10:30-11:30",
    "11:30-12:30", "12:30-13:30", "13:30-14:30"
]

horas_tarde = [
    "14:30-15:30", "15:30-16:30", "16:30-17:30",
    "17:30-18:30", "18:30-19:30", "19:30-20:30"
]

dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
horas_por_dia = 6
total_slots = len(dias) * horas_por_dia


def _resolver_turno(df_sub, df_aulas, es_tarde=False, curso=1, semestre=1):
    """Resuelve un subconjunto de sesiones (mañana o tarde) con CP-SAT."""
    if df_sub.empty:
        return pd.DataFrame()

    horas_etiquetas = horas_tarde if es_tarde else horas_manana

    model = cp_model.CpModel()
    start_vars = {}
    end_vars = {}
    interval_vars = {}

    for _, row in df_sub.iterrows():
        s_id = str(row["id_sesion"]).strip()
        duracion = int(row["duracion_horas"])
        start = model.NewIntVar(0, total_slots - duracion, f"start_{s_id}")
        end = model.NewIntVar(duracion, total_slots, f"end_{s_id}")
        interval = model.NewIntervalVar(start, duracion, end, f"interval_{s_id}")

        start_vars[s_id] = start
        end_vars[s_id] = end
        interval_vars[s_id] = interval

    aplicar_restriccion_estudiantes(model, df_sub, interval_vars)
    aplicar_restriccion_cambio_dia(model, df_sub, start_vars, end_vars, horas_por_dia)
    aplicar_restriccion_profesores(model, df_sub, interval_vars)
    aula_asignada = aplicar_restriccion_aulas(model, df_sub, df_aulas, start_vars, end_vars)
    aplicar_restricciones_blandas(model, df_sub, start_vars, total_slots=total_slots)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        turno_nombre = "TARDE" if es_tarde else "MAÑANA"
        print(f"No se encontró solución factible para el turno de {turno_nombre}.")
        return None

    asignaciones = []
    for _, row in df_sub.iterrows():
        s_id = str(row["id_sesion"]).strip()
        slot_inicio = solver.Value(start_vars[s_id])
        dia_idx = slot_inicio // horas_por_dia
        hora_idx = slot_inicio % horas_por_dia

        aula_elegida = "Sin aula"
        for a_id in df_aulas["id_aula"].astype(str):
            var_aula = aula_asignada.get((s_id, a_id))
            if var_aula is not None:
                try:
                    if solver.Value(var_aula) == 1:
                        aula_elegida = a_id
                        break
                except Exception:
                    pass

        asignaciones.append({
            "Slot": slot_inicio,
            "Sesion": s_id,
            "Asignatura": row["asignatura"],
            "Tipo": row["tipo"],
            "Grupo": row["grupo"],
            "Dia": dias[dia_idx],
            "Hora": horas_etiquetas[hora_idx],
            "Duracion": f"{row['duracion_horas']}h",
            "Aula": aula_elegida,
            "Profesor": row["profesor"],
            "Curso": row.get("curso", curso),
            "Semestre": row.get("semestre", semestre),
            "GrupoPrincipal": row.get("grupo_principal", 3 if es_tarde else 1)
        })

    return pd.DataFrame(asignaciones)


def modelo_base(semestre=1, curso=3, grupo_principal=1):
    ruta_clases = "datos/clases.csv"
    df_clases = pd.read_csv(ruta_clases)

    if "curso" in df_clases.columns and curso is not None:
        df_clases = df_clases[df_clases["curso"] == curso].copy()
    if "semestre" in df_clases.columns and semestre is not None:
        df_clases = df_clases[df_clases["semestre"] == semestre].copy()
    if "grupo_principal" in df_clases.columns and grupo_principal is not None:
        df_clases = df_clases[df_clases["grupo_principal"] == grupo_principal].copy()

    filtro_info = f"Curso {curso} | Semestre {semestre}" + (f" | Grupo {grupo_principal}" if grupo_principal is not None else "")
    print(f"\nCargadas con éxito {len(df_clases)} sesiones ({filtro_info}) desde '{ruta_clases}'.")

    df_aulas = pd.read_csv("datos/aulas.csv")

    resultados = []

    # Determinar si hay grupos de mañana y/o de tarde
    if grupo_principal is None:
        df_m = df_clases[df_clases["grupo_principal"].isin([1, 2])].copy()
        df_t = df_clases[df_clases["grupo_principal"] == 3].copy()

        if not df_m.empty:
            print(f"--- Resolviendo Turno Mañana ({len(df_m)} sesiones) ---")
            res_m = _resolver_turno(df_m, df_aulas, es_tarde=False, curso=curso, semestre=semestre)
            if res_m is None:
                return None
            resultados.append(res_m)

        if not df_t.empty:
            print(f"--- Resolviendo Turno Tarde ({len(df_t)} sesiones) ---")
            res_t = _resolver_turno(df_t, df_aulas, es_tarde=True, curso=curso, semestre=semestre)
            if res_t is None:
                return None
            resultados.append(res_t)
    else:
        es_tarde = (grupo_principal == 3)
        res = _resolver_turno(df_clases, df_aulas, es_tarde=es_tarde, curso=curso, semestre=semestre)
        if res is None:
            return None
        resultados.append(res)

    if not resultados:
        print("No hay sesiones para resolver.")
        return None

    df_resultado = pd.concat(resultados, ignore_index=True)

    # Imprimir resumen de asignaciones
    cols_mostrar = [c for c in ["Sesion", "Asignatura", "Tipo", "Grupo", "Dia", "Hora", "Duracion", "Aula", "Profesor", "GrupoPrincipal"] if c in df_resultado.columns]
    print(df_resultado[cols_mostrar].to_string(index=False))

    # Generar el PNG con nomenclatura organizada en carpetas por curso y semestre
    sem_carpeta = "1er_Semestre" if semestre == 1 else f"{semestre}do_Semestre"
    carpeta_destino = f"horarios/{curso}GII/{sem_carpeta}"
    sem_str = "1er SEMESTRE" if semestre == 1 else f"{semestre}º SEMESTRE"
    os.makedirs(carpeta_destino, exist_ok=True)

    grupos_en_resultado = sorted(df_resultado["GrupoPrincipal"].dropna().unique()) if "GrupoPrincipal" in df_resultado.columns else [1]

    if len(grupos_en_resultado) > 1:
        gps_txt = " y ".join([f"Grupo {int(g)}" if g != 3 else "Grupo 3 (Tarde)" for g in grupos_en_resultado])
        exportar_horario_png(
            df_resultado,
            ruta_salida=f"{carpeta_destino}/horario_conjunto.png",
            titulo=f"CALENDARIO ACADÉMICO — {curso}º GII ({gps_txt} - {sem_str})",
            abrir_al_terminar=False
        )
        for gp in grupos_en_resultado:
            df_gp = df_resultado[df_resultado["GrupoPrincipal"] == gp].copy()
            txt_ind = f"Grupo {int(gp)}" if gp != 3 else "Grupo 3 (Tarde)"
            exportar_horario_png(
                df_gp,
                ruta_salida=f"{carpeta_destino}/horario_Grupo_{int(gp)}.png",
                titulo=f"CALENDARIO ACADÉMICO — {curso}º GII ({txt_ind} - {sem_str})",
                abrir_al_terminar=False
            )
    else:
        gp_num = int(grupos_en_resultado[0])
        txt_ind = f"Grupo {gp_num}" if gp_num != 3 else "Grupo 3 (Tarde)"
        exportar_horario_png(
            df_resultado,
            ruta_salida=f"{carpeta_destino}/horario_Grupo_{gp_num}.png",
            titulo=f"CALENDARIO ACADÉMICO — {curso}º GII ({txt_ind} - {sem_str})",
            abrir_al_terminar=False
        )

    return df_resultado


if __name__ == "__main__":
    print("\n================== 1º GII - SEMESTRE 1 (GRUPOS 1, 2 Y 3 TARDE) ==================")
    modelo_base(semestre=1, curso=1, grupo_principal=None)
    print("\n================== 1º GII - SEMESTRE 2 (GRUPOS 1, 2 Y 3 TARDE) ==================")
    modelo_base(semestre=2, curso=1, grupo_principal=None)

    print("\n================== 2º GII - SEMESTRE 1 (GRUPOS 1 Y 2) ==================")
    modelo_base(semestre=1, curso=2, grupo_principal=None)
    print("\n================== 2º GII - SEMESTRE 2 (GRUPOS 1 Y 2) ==================")
    modelo_base(semestre=2, curso=2, grupo_principal=None)

    print("\n================== 3º GII - SEMESTRE 1 ==================")
    modelo_base(semestre=1, curso=3, grupo_principal=1)
    print("\n================== 3º GII - SEMESTRE 2 ==================")
    modelo_base(semestre=2, curso=3, grupo_principal=1)

    print("\n================== 4º GII - SEMESTRE 1 ==================")
    modelo_base(semestre=1, curso=4, grupo_principal=1)
    print("\n================== 4º GII - SEMESTRE 2 ==================")
    modelo_base(semestre=2, curso=4, grupo_principal=1)