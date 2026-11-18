import os
import io
import sys
import time
import math
import random
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from visualizador import exportar_horario_png


def cargar_datos(cuatrimestre=1):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta_clases = os.path.join(base_dir, "datos", "clases_gcid.csv")
    ruta_aulas = os.path.join(base_dir, "datos", "aulas.csv")

    df_clases = pd.read_csv(ruta_clases)
    df_aulas = pd.read_csv(ruta_aulas)

    df_clases.columns = df_clases.columns.str.strip().str.lower()
    df_aulas.columns = df_aulas.columns.str.strip().str.lower()

    df_clases["cuatrimestre"] = pd.to_numeric(df_clases["cuatrimestre"], errors="coerce")
    df_clases = df_clases[df_clases["cuatrimestre"] == cuatrimestre].copy()

    return df_clases, df_aulas


def preparar_estructuras(df_clases, df_aulas, cuatrimestre, horas_por_dia=6, total_slots=30):
    def estandarizar_tipo(texto):
        t = str(texto).strip().lower()
        return "laboratorio" if "lab" in t else "teoria"

    col_tipo_aula = "tipo" if "tipo" in df_aulas.columns else "tipo_aula"
    col_id_aula = "id_aula" if "id_aula" in df_aulas.columns else df_aulas.columns[0]
    df_aulas["tipo_std"] = df_aulas[col_tipo_aula].apply(estandarizar_tipo)

    sesiones = []
    meta = {}

    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()
        dur = int(row["duracion_horas"])
        curso = int(row["curso"])
        grupo = str(row["grupo"]).strip()
        tipo = str(row["tipo"]).strip().lower()
        profesor = str(row["profesor"]).strip()
        num_alumnos = int(row.get("num_alumnos", 0))

        if "tipo_aula_requerida" in row and pd.notna(row["tipo_aula_requerida"]):
            tipo_req = estandarizar_tipo(row["tipo_aula_requerida"])
        else:
            tipo_req = "laboratorio" if "prac" in tipo else "teoria"

        max_slot = 18 if (cuatrimestre == 2 and curso == 3) else total_slots
        slots_validos = [
            t for t in range(max_slot - dur + 1)
            if (t // horas_por_dia) == ((t + dur - 1) // horas_por_dia)
        ]

        aulas_validas = df_aulas[
            (df_aulas["tipo_std"] == tipo_req) &
            (df_aulas["capacidad"] >= num_alumnos)
        ][col_id_aula].astype(str).str.strip().tolist()

        if not slots_validos or not aulas_validas:
            raise ValueError(f"Sin dominio válido (slots o aulas) para la sesión {s_id}")

        sesiones.append(s_id)
        meta[s_id] = {
            "asignatura": str(row["asignatura"]).strip(),
            "tipo": tipo,
            "grupo": grupo,
            "dur": dur,
            "curso": curso,
            "profesor": profesor,
            "slots_validos": slots_validos,
            "aulas_validas": aulas_validas
        }

    pares_estudiantes = []
    pares_profesores = []
    n = len(sesiones)

    for i in range(n):
        for j in range(i + 1, n):
            id1, id2 = sesiones[i], sesiones[j]
            m1, m2 = meta[id1], meta[id2]

            if m1["curso"] == m2["curso"]:
                g1, g2 = m1["grupo"], m2["grupo"]
                t1, t2 = m1["tipo"], m2["tipo"]
                comparten = (
                    (t1 == "teoria" or t2 == "teoria") or
                    (g1 == g2) or
                    (g1 == "17" and g2 in ["41", "42"]) or
                    (g2 == "17" and g1 in ["41", "42"]) or
                    (g1 == "18" and g2 in ["43", "44"]) or
                    (g2 == "18" and g1 in ["43", "44"])
                )
                if comparten:
                    pares_estudiantes.append((id1, id2))

            if m1["profesor"] == m2["profesor"] and m1["profesor"].lower() not in ["", "nan", "none"]:
                pares_profesores.append((id1, id2))

    grupos_sesiones = {}
    for s_id in sesiones:
        clave = (meta[s_id]["curso"], meta[s_id]["grupo"])
        grupos_sesiones.setdefault(clave, []).append(s_id)

    return sesiones, meta, pares_estudiantes, pares_profesores, grupos_sesiones


def evaluar_estado(estado, sesiones, meta, pares_est, pares_prof, grupos_sesiones,
                   horas_por_dia=6, total_slots=30, aula_preferida="A2-5"):
    violaciones_duras = 0

    for id1, id2 in pares_est:
        s1, _ = estado[id1]
        s2, _ = estado[id2]
        if s1 < s2 + meta[id2]["dur"] and s2 < s1 + meta[id1]["dur"]:
            violaciones_duras += 1

    for id1, id2 in pares_prof:
        s1, _ = estado[id1]
        s2, _ = estado[id2]
        if s1 < s2 + meta[id2]["dur"] and s2 < s1 + meta[id1]["dur"]:
            violaciones_duras += 1

    por_aula = {}
    for s_id in sesiones:
        slot_ini, aula = estado[s_id]
        por_aula.setdefault(aula, []).append((slot_ini, slot_ini + meta[s_id]["dur"]))

    for aula, intervalos in por_aula.items():
        if len(intervalos) > 1:
            intervalos.sort()
            for k in range(len(intervalos) - 1):
                if intervalos[k][1] > intervalos[k + 1][0]:
                    violaciones_duras += 1

    horas_hueco = 0
    for _, lista_ids in grupos_sesiones.items():
        if len(lista_ids) <= 1:
            continue
        por_dia = {}
        for s_id in lista_ids:
            slot_ini, _ = estado[s_id]
            dur = meta[s_id]["dur"]
            dia = slot_ini // horas_por_dia
            por_dia.setdefault(dia, []).append((slot_ini, slot_ini + dur, dur))

        for dia, bloques in por_dia.items():
            if len(bloques) > 1:
                min_ini = min(b[0] for b in bloques)
                max_fin = max(b[1] for b in bloques)
                suma_dur = sum(b[2] for b in bloques)
                hueco = (max_fin - min_ini) - suma_dur
                if hueco > 0:
                    horas_hueco += hueco

    coste_blando = 0
    for s_id in sesiones:
        slot_ini, aula = estado[s_id]
        m = meta[s_id]

        if slot_ini >= (total_slots - 2):
            coste_blando += 10

        if "teor" in m["tipo"] and m["grupo"] == "17" and aula != aula_preferida:
            coste_blando += 25

    coste_total = (violaciones_duras * 10000) + (horas_hueco * 2000) + coste_blando
    return coste_total, violaciones_duras, horas_hueco, coste_blando


def generar_vecino(estado, sesiones, meta):
    vecino = dict(estado)
    r = random.random()

    if r < 0.45:
        s_id = random.choice(sesiones)
        _, aula_actual = vecino[s_id]
        nuevo_slot = random.choice(meta[s_id]["slots_validos"])
        vecino[s_id] = (nuevo_slot, aula_actual)

    elif r < 0.80:
        s_id = random.choice(sesiones)
        slot_actual, _ = vecino[s_id]
        nueva_aula = random.choice(meta[s_id]["aulas_validas"])
        vecino[s_id] = (slot_actual, nueva_aula)

    else:
        id1, id2 = random.sample(sesiones, 2)
        s1, a1 = vecino[id1]
        s2, a2 = vecino[id2]
        if s2 in meta[id1]["slots_validos"] and s1 in meta[id2]["slots_validos"]:
            vecino[id1] = (s2, a1)
            vecino[id2] = (s1, a2)
        else:
            nuevo_slot = random.choice(meta[id1]["slots_validos"])
            vecino[id1] = (nuevo_slot, a1)

    return vecino


def exportar_grafica_convergencia(historial, cuatrimestre, ruta_salida):
    """
    Genera una figura con dos paneles:
    - Izquierda: Evolución global desde el estado aleatorio inicial hasta enfriarse.
    - Derecha: Zoom en la región factible (0 choques y 0 huecos) mostrando el ajuste fino de preferencias.
    """
    ruta_salida = os.path.abspath(ruta_salida)
    sufijo_cuatri = "1er" if cuatrimestre == 1 else "2do"

    iters = [h[0] for h in historial]
    actuales = [h[1] for h in historial]
    mejores = [h[2] for h in historial]
    mejor_final = mejores[-1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.2), dpi=300)
    fig.patch.set_facecolor("#F8F9FA")

    # Panel 1: Convergencia Global
    ax1.set_facecolor("#FFFFFF")
    ax1.plot(iters, actuales, color="#90CAF9", alpha=0.65, linewidth=0.9, label="Coste actual (exploración)")
    ax1.plot(iters, mejores, color="#1A237E", linewidth=2.2, label="Mejor coste encontrado")
    ax1.axhline(2000, color="#E53935", linestyle="--", linewidth=1.1, label="Umbral factibilidad (0 choques/huecos)")
    ax1.set_title("Evolución Global (Eliminación de Conflictos)", fontsize=11.5, fontweight="bold", color="#1A237E")
    ax1.set_xlabel("Iteración", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Coste Total (Fitness)", fontsize=10, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper right", fontsize=8.5)

    # Panel 2: Zoom en Región Factible (Penalizaciones Blandas)
    ax2.set_facecolor("#FFFFFF")
    ax2.plot(iters, actuales, color="#A5D6A7", alpha=0.65, linewidth=0.9, label="Coste actual (aceptación térmica)")
    ax2.plot(iters, mejores, color="#1B5E20", linewidth=2.2, label=f"Óptimo SA alcanzado ({mejor_final})")
    ax2.set_ylim(0, max(500, mejor_final * 3.5))
    ax2.set_title("Zoom Región Factible (Optimización de Preferencias)", fontsize=11.5, fontweight="bold", color="#1B5E20")
    ax2.set_xlabel("Iteración", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Penalización Blanda", fontsize=10, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=8.5)

    plt.suptitle(
        f"CONVERGENCIA DEL RECOCIDO SIMULADO — {sufijo_cuatri.upper()} SEMESTRE GCID",
        fontsize=14, fontweight="bold", color="#1A237E", y=1.02
    )
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close("all")

    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    if os.path.exists(ruta_salida):
        try:
            os.remove(ruta_salida)
        except OSError:
            time.sleep(0.3)

    with open(ruta_salida, "wb") as f:
        f.write(buf.getvalue())

    print(f" Gráfica de convergencia guardada en: {ruta_salida}")


def ejecutar_recocido_simulado(cuatrimestre=1, max_iter=60000, t_inicial=5000.0, t_final=0.1, semilla=42):
    random.seed(semilla)
    t0 = time.time()

    df_clases, df_aulas = cargar_datos(cuatrimestre)
    sesiones, meta, pares_est, pares_prof, grupos_sesiones = preparar_estructuras(
        df_clases, df_aulas, cuatrimestre
    )

    estado_actual = {
        s_id: (
            random.choice(meta[s_id]["slots_validos"]),
            random.choice(meta[s_id]["aulas_validas"])
        )
        for s_id in sesiones
    }

    coste_actual, v_duras, h_hueco, c_blando = evaluar_estado(
        estado_actual, sesiones, meta, pares_est, pares_prof, grupos_sesiones
    )

    mejor_estado = dict(estado_actual)
    mejor_coste = coste_actual
    mejor_metricas = (v_duras, h_hueco, c_blando)

    historial = [(0, coste_actual, mejor_coste)]
    paso_registro = max(1, max_iter // 600)

    ratio_enfriamiento = (t_final / t_inicial) ** (1.0 / max_iter)
    temperatura = t_inicial

    for it in range(1, max_iter + 1):
        vecino = generar_vecino(estado_actual, sesiones, meta)
        coste_vecino, vd_v, hh_v, cb_v = evaluar_estado(
            vecino, sesiones, meta, pares_est, pares_prof, grupos_sesiones
        )

        delta = coste_vecino - coste_actual

        if delta <= 0 or random.random() < math.exp(-delta / temperatura):
            estado_actual = vecino
            coste_actual = coste_vecino

            if coste_actual < mejor_coste:
                mejor_estado = dict(estado_actual)
                mejor_coste = coste_actual
                mejor_metricas = (vd_v, hh_v, cb_v)

        if it % paso_registro == 0 or it == max_iter:
            historial.append((it, coste_actual, mejor_coste))

        temperatura *= ratio_enfriamiento

    tiempo_total = time.time() - t0
    vd_final, hh_final, cb_final = mejor_metricas

    print(f"\n=======================================================")
    print(f" RECOCIDO SIMULADO — CUATRIMESTRE {cuatrimestre}")
    print(f"=======================================================")
    print(f"Tiempo de ejecución : {tiempo_total:.2f} s ({max_iter} iteraciones)")
    print(f"Coste total global  : {mejor_coste}")
    print(f"  - Choques duros   : {vd_final}")
    print(f"  - Horas de hueco  : {hh_final}")
    print(f"  - Penaliz. blanda : {cb_final}")

    sufijo = "1er" if cuatrimestre == 1 else "2do"

    # Exportar gráfica de evolución del coste
    exportar_grafica_convergencia(
        historial=historial,
        cuatrimestre=cuatrimestre,
        ruta_salida=f"convergencia_SA_{sufijo}.png"
    )

    # Construir DataFrame compatible con visualizador.py
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_etiquetas = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]

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
            "Profesor": m["profesor"]
        })

    df_resultado = pd.DataFrame(asignaciones).sort_values(by="Slot")

    for curso in sorted(df_resultado["Curso"].unique()):
        df_curso = df_resultado[df_resultado["Curso"] == curso]
        nombre_png = f"horario_SA_{int(curso)}GCID_{sufijo}.png"
        exportar_horario_png(
            df_resultado=df_curso,
            curso=int(curso),
            cuatrimestre=cuatrimestre,
            ruta_salida=nombre_png,
            abrir_al_terminar=False,
            etiqueta_metodo="RECOCIDO SIMULADO"
        )


if __name__ == "__main__":
    print("==================================================")
    print("   OPTIMIZACIÓN METAHEURÍSTICA (SIMULATED ANNEALING)")
    print("==================================================")
    for c in [1, 2]:
        ejecutar_recocido_simulado(cuatrimestre=c, max_iter=60000)