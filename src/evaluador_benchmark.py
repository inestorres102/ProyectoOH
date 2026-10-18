"""
Script de evaluación y experimentación comparativa (Benchmark) para la Memoria de OH.

Compara de forma rigurosa y en igualdad de condiciones:
1. Búsqueda Aleatoria (Random Search / Baseline)
2. Metaheurística Propia: Recocido Simulado (Simulated Annealing) con múltiples semillas
3. Método Exacto: Programación con Restricciones (OR-Tools CP-SAT)

Genera tablas de métricas (Media ± Desv. Típica) y gráficas comparativas
para incluir directamente en la Memoria del proyecto.
"""

import os
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from metaheuristica_sa import SimulatedAnnealingTimetabling
from modelo_base import _resolver_turno


def evaluar_busqueda_aleatoria(df_clases, df_aulas, es_tarde=False, num_intentos=5000, semilla=42):
    """Línea base: genera soluciones aleatorias y se queda con la mejor encontrada."""
    sa = SimulatedAnnealingTimetabling(df_clases, df_aulas, es_tarde=es_tarde, semilla=semilla)
    t0 = time.time()
    mejor_estado = None
    mejor_energia = float("inf")
    mejor_duras = float("inf")
    mejor_blandas = float("inf")

    for _ in range(num_intentos):
        st = sa.generar_solucion_inicial()
        e, dur, bla = sa.calcular_energia(st)
        if e < mejor_energia:
            mejor_energia = e
            mejor_duras = dur
            mejor_blandas = bla
            mejor_estado = st

    tiempo = time.time() - t0
    return {
        "metodo": "Búsqueda Aleatoria (Baseline)",
        "tiempo_seg": tiempo,
        "energia": mejor_energia,
        "duras": mejor_duras,
        "blandas": mejor_blandas,
        "factible": (mejor_duras == 0)
    }


def evaluar_simulated_annealing(df_clases, df_aulas, es_tarde=False, semillas=[10, 20, 30, 40, 50]):
    """Ejecuta el Recocido Simulado con múltiples semillas estadísticas."""
    resultados = []
    for sem in semillas:
        sa = SimulatedAnnealingTimetabling(
            df_clases=df_clases,
            df_aulas=df_aulas,
            es_tarde=es_tarde,
            t_inicial=120.0,
            t_final=0.01,
            alpha=0.985,
            iter_por_temp=140,
            semilla=sem
        )
        _, mejor_e, hist, t_calc = sa.optimizar(verbose=False)
        duras = hist[-1]["duras"]
        blandas = hist[-1]["blandas"]

        resultados.append({
            "metodo": "Recocido Simulado (Propio)",
            "semilla": sem,
            "tiempo_seg": t_calc,
            "energia": mejor_e,
            "duras": duras,
            "blandas": blandas,
            "factible": (duras == 0)
        })

    return resultados


def evaluar_cpsat(df_clases, df_aulas, es_tarde=False):
    """Ejecuta el solver exacto Google OR-Tools CP-SAT."""
    t0 = time.time()
    df_res = _resolver_turno(df_clases, df_aulas, es_tarde=es_tarde)
    tiempo = time.time() - t0

    if df_res is None or df_res.empty:
        return {
            "metodo": "OR-Tools CP-SAT (Exacto)",
            "tiempo_seg": tiempo,
            "energia": float("inf"),
            "duras": 1,
            "blandas": float("inf"),
            "factible": False
        }

    # Evaluar la solución de CP-SAT con la misma función de energía de SA para comparar justamente
    sa = SimulatedAnnealingTimetabling(df_clases, df_aulas, es_tarde=es_tarde, semilla=42)
    estado_cpsat = {}
    for _, row in df_res.iterrows():
        s_id = str(row["Sesion"]).strip()
        slot = int(row["Slot"])
        aula = str(row["Aula"]).strip()
        estado_cpsat[s_id] = (slot, aula)

    e, dur, bla = sa.calcular_energia(estado_cpsat)

    return {
        "metodo": "OR-Tools CP-SAT (Exacto)",
        "tiempo_seg": tiempo,
        "energia": e,
        "duras": dur,
        "blandas": bla,
        "factible": (dur == 0)
    }


def ejecutar_benchmark_completo(instancias=[(3, 1, 1), (2, 1, 1), (1, 1, 1)], ruta_salida="memoria/benchmark_resultados.csv"):
    """
    Ejecuta el benchmark comparativo sobre varias instancias reales de la EII.
    """
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    df_clases_totales = pd.read_csv("datos/clases.csv")
    df_aulas = pd.read_csv("datos/aulas.csv")

    res_filas = []

    for curso, sem, gp in instancias:
        nombre_instancia = f"{curso}º GII - Semestre {sem} (Grupo {gp})"
        print(f"\n==================== Evaluando: {nombre_instancia} ====================")

        df_sub = df_clases_totales[
            (df_clases_totales["curso"] == curso) &
            (df_clases_totales["semestre"] == sem) &
            (df_clases_totales["grupo_principal"] == gp)
        ].copy()

        es_tarde = (gp == 3)

        # 1. Baseline: Búsqueda Aleatoria
        print("  -> Ejecutando Búsqueda Aleatoria (5.000 muestras)...")
        r_random = evaluar_busqueda_aleatoria(df_sub, df_aulas, es_tarde=es_tarde)
        r_random["instancia"] = nombre_instancia
        r_random["num_sesiones"] = len(df_sub)
        res_filas.append(r_random)

        # 2. Metaheurística Propia: Simulated Annealing (5 ejecuciones independientes)
        print("  -> Ejecutando Recocido Simulado (5 semillas)...")
        r_sa_list = evaluar_simulated_annealing(df_sub, df_aulas, es_tarde=es_tarde, semillas=[1, 2, 3, 4, 5])
        for r in r_sa_list:
            r["instancia"] = nombre_instancia
            r["num_sesiones"] = len(df_sub)
            res_filas.append(r)

        # 3. Solver Exacto: CP-SAT
        print("  -> Ejecutando OR-Tools CP-SAT...")
        r_cpsat = evaluar_cpsat(df_sub, df_aulas, es_tarde=es_tarde)
        r_cpsat["instancia"] = nombre_instancia
        r_cpsat["num_sesiones"] = len(df_sub)
        res_filas.append(r_cpsat)

    df_benchmark = pd.DataFrame(res_filas)
    df_benchmark.to_csv(ruta_salida, index=False)
    print(f"\n Benchmark guardado en: {ruta_salida}")

    # Generar tabla agregada con Media ± Desv. Típica
    resumen = df_benchmark.groupby(["instancia", "metodo"]).agg(
        Num_Sesiones=("num_sesiones", "first"),
        Tiempo_Medio_s=("tiempo_seg", "mean"),
        Tiempo_Std=("tiempo_seg", "std"),
        Energia_Media=("energia", "mean"),
        Energia_Std=("energia", "std"),
        Duras_Medias=("duras", "mean"),
        Blandas_Medias=("blandas", "mean"),
        Pct_Factible=("factible", lambda x: np.mean(x) * 100)
    ).reset_index()

    print("\nRESUMEN COMPARATIVO:")
    print(resumen.to_string(index=False))

    # Guardar resumen en Markdown sin dependencia externa
    cols = list(resumen.columns)
    header = "| " + " | ".join(cols) + " |\n"
    separator = "| " + " | ".join(["---"] * len(cols)) + " |\n"
    rows = []
    for _, r in resumen.iterrows():
        fila = [f"{r[c]:.2f}" if isinstance(r[c], float) else str(r[c]) for c in cols]
        rows.append("| " + " | ".join(fila) + " |\n")
    resumen_md = header + separator + "".join(rows)
    
    with open("memoria/tabla_comparativa.md", "w", encoding="utf-8") as f:
        f.write("# Tabla Comparativa Experimental: Métodos de Optimización\n\n")
        f.write(resumen_md + "\n")

    # Generar gráfica comparativa de barras para la memoria
    generar_grafica_comparativa(resumen, "memoria/grafica_comparativa_benchmark.png")

    return df_benchmark, resumen


def generar_grafica_comparativa(df_resumen, ruta_guardado="memoria/grafica_comparativa_benchmark.png"):
    """Crea una figura comparativa de Tiempo de Cómputo y Coste de Huecos."""
    instancias = df_resumen["instancia"].unique()
    metodos = ["Búsqueda Aleatoria (Baseline)", "Recocido Simulado (Propio)", "OR-Tools CP-SAT (Exacto)"]
    colores = {"Búsqueda Aleatoria (Baseline)": "#EF5350", "Recocido Simulado (Propio)": "#42A5F5", "OR-Tools CP-SAT (Exacto)": "#66BB6A"}

    x = np.arange(len(instancias))
    width = 0.26

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

    # 1. Coste / Energía
    for i, m in enumerate(metodos):
        sub = df_resumen[df_resumen["metodo"] == m]
        valores = [sub[sub["instancia"] == inst]["Energia_Media"].values[0] if len(sub[sub["instancia"] == inst]) > 0 else 0 for inst in instancias]
        errores = [sub[sub["instancia"] == inst]["Energia_Std"].fillna(0).values[0] if len(sub[sub["instancia"] == inst]) > 0 else 0 for inst in instancias]
        ax1.bar(x + (i - 1) * width, valores, width, yerr=errores, capsize=4, label=m, color=colores[m], alpha=0.9, edgecolor="#333333")

    ax1.set_ylabel("Energía / Coste (Menor es mejor)", fontsize=11, fontweight="bold")
    ax1.set_title("Calidad de la Solución (Coste de Huecos y Penalizaciones)", fontsize=11.5, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels([inst.split(" - ")[0] for inst in instancias], fontsize=10)
    ax1.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax1.legend(loc="upper right", fontsize=9)

    # 2. Tiempo de Cómputo (Escala logarítmica para ver diferencias claras)
    for i, m in enumerate(metodos):
        sub = df_resumen[df_resumen["metodo"] == m]
        tiempos = [sub[sub["instancia"] == inst]["Tiempo_Medio_s"].values[0] if len(sub[sub["instancia"] == inst]) > 0 else 0 for inst in instancias]
        ax2.bar(x + (i - 1) * width, tiempos, width, label=m, color=colores[m], alpha=0.9, edgecolor="#333333")

    ax2.set_ylabel("Tiempo de Ejecución en segundos (s)", fontsize=11, fontweight="bold")
    ax2.set_title("Eficiencia Computacional", fontsize=11.5, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels([inst.split(" - ")[0] for inst in instancias], fontsize=10)
    ax2.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax2.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    plt.savefig(ruta_guardado, dpi=300)
    plt.close(fig)
    print(f" Gráfica comparativa guardada con éxito en: {ruta_guardado}")


if __name__ == "__main__":
    ejecutar_benchmark_completo()
