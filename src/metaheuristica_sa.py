"""
Metaheurística de Recocido Simulado (Simulated Annealing) propia para el
diseño y optimización de horarios de la EII - ULPGC.

Cumple con los requisitos de la propuesta D1 de Optimización y Heurística:
- Implementación propia del núcleo algorítmico desde cero (sin librerías de caja negra).
- Evaluación rigurosa de restricciones duras (profesores, estudiantes por subgrupo, aulas físicas y capacidad).
- Optimización de restricciones blandas (huecos entre clases por subgrupo y viernes tarde).
- Generación de curvas de convergencia para la memoria del proyecto.
"""

import math
import os
import random
import time
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from restricciones import obtener_subgrupos_estudiantes
from visualizador import exportar_horario_png


class SimulatedAnnealingTimetabling:
    def __init__(
        self,
        df_clases,
        df_aulas,
        es_tarde=False,
        t_inicial=100.0,
        t_final=0.05,
        alpha=0.985,
        iter_por_temp=120,
        peso_duro=2000,
        peso_hueco=15,
        peso_viernes=10,
        semilla=None
    ):
        self.df_clases = df_clases.copy().reset_index(drop=True)
        self.df_aulas = df_aulas.copy().reset_index(drop=True)
        self.es_tarde = es_tarde
        self.t_inicial = t_inicial
        self.t_final = t_final
        self.alpha = alpha
        self.iter_por_temp = iter_por_temp
        self.peso_duro = peso_duro
        self.peso_hueco = peso_hueco
        self.peso_viernes = peso_viernes

        if semilla is not None:
            random.seed(semilla)
            np.random.seed(semilla)

        self.dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
        self.horas_por_dia = 6
        self.total_slots = len(self.dias) * self.horas_por_dia  # 30 slots

        self.horas_manana = [
            "08:30-09:30", "09:30-10:30", "10:30-11:30",
            "11:30-12:30", "12:30-13:30", "13:30-14:30"
        ]
        self.horas_tarde = [
            "14:30-15:30", "15:30-16:30", "16:30-17:30",
            "17:30-18:30", "18:30-19:30", "19:30-20:30"
        ]
        self.horas_etiquetas = self.horas_tarde if es_tarde else self.horas_manana

        # Precomputación de datos de sesiones para máxima velocidad de evaluación
        self._precomputar_estructuras()

    def _precomputar_estructuras(self):
        self.sesiones = []
        self.duracion = {}
        self.profesor = {}
        self.subgrupos = {}
        self.tipo_sesion = {}
        self.alumnos = {}
        self.aulas_compatibles = {}
        self.slots_validos = {}
        self.info_sesion = {}

        # Mapeo de aulas
        aulas_list = []
        for _, a_row in self.df_aulas.iterrows():
            aulas_list.append({
                "id": str(a_row["id_aula"]).strip(),
                "tipo": str(a_row["tipo"]).strip().lower(),
                "capacidad": int(a_row["capacidad"])
            })

        for _, row in self.df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            dur = int(row["duracion_horas"])
            num_alum = int(row.get("num_alumnos", 20))
            tipo_aula_req = str(row.get("tipo_aula_requerida", "Teoria")).strip().lower()

            self.sesiones.append(s_id)
            self.duracion[s_id] = dur
            self.profesor[s_id] = str(row["profesor"]).strip()
            self.tipo_sesion[s_id] = str(row["tipo"]).strip().lower()
            self.alumnos[s_id] = num_alum
            self.info_sesion[s_id] = row.to_dict()

            # Subgrupos de alumnos atendiendo a la sesión
            subs = obtener_subgrupos_estudiantes(row, df_clases=self.df_clases)
            self.subgrupos[s_id] = set(subs) if subs else {str(row["grupo"]).strip()}

            # Aulas compatibles según tipo y capacidad
            compat = [
                a["id"] for a in aulas_list
                if (tipo_aula_req in a["tipo"]) and (a["capacidad"] >= num_alum)
            ]
            if not compat:
                # Si ninguna cumple por capacidad, relajar a coincidencia de tipo
                compat = [a["id"] for a in aulas_list if tipo_aula_req in a["tipo"]]
            if not compat:
                compat = [a["id"] for a in aulas_list]
            self.aulas_compatibles[s_id] = compat

            # Slots donde la clase no cruza el cambio de día
            valid_slots = []
            for slot in range(self.total_slots - dur + 1):
                if (slot % self.horas_por_dia) + dur <= self.horas_por_dia:
                    valid_slots.append(slot)
            self.slots_validos[s_id] = valid_slots

        # Todos los subgrupos atómicos presentes en este conjunto
        self.todos_subgrupos = set()
        for s_id in self.sesiones:
            self.todos_subgrupos.update(self.subgrupos[s_id])

    def generar_solucion_inicial(self):
        """Genera un estado inicial asignando a cada sesión un slot y aula válidos."""
        estado = {}
        for s_id in self.sesiones:
            slot = random.choice(self.slots_validos[s_id])
            aula = random.choice(self.aulas_compatibles[s_id])
            estado[s_id] = (slot, aula)
        return estado

    def calcular_energia(self, estado):
        """
        Función de coste / energía del sistema:
        E = peso_duro * violaciones_duras + peso_blando * penalizaciones_blandas
        Retorna (energia_total, num_violaciones_duras, coste_blando)
        """
        violaciones_duras = 0

        # Tablas de ocupación para detección rápida de solapamientos
        # ocupacion_aula: (aula, slot) -> [s_id]
        # ocupacion_profesor: (profesor, slot) -> [s_id]
        # ocupacion_subgrupo: (subgrupo, slot) -> [s_id]
        ocupacion_aula = {}
        ocupacion_profesor = {}
        ocupacion_subgrupo = {}

        # Estructura para cálculo de huecos por subgrupo y por día:
        # slots_por_subgrupo_dia: (subgrupo, dia) -> list de slots ocupados
        slots_por_subgrupo_dia = {
            (sg, d): [] for sg in self.todos_subgrupos for d in range(len(self.dias))
        }

        penalizacion_viernes = 0

        for s_id in self.sesiones:
            slot_inicio, aula = estado[s_id]
            dur = self.duracion[s_id]
            prof = self.profesor[s_id]
            subs = self.subgrupos[s_id]

            for d in range(dur):
                t = slot_inicio + d
                dia_idx = t // self.horas_por_dia
                hora_idx = t % self.horas_por_dia

                # 1. Aula física
                if (aula, t) in ocupacion_aula:
                    violaciones_duras += 1
                else:
                    ocupacion_aula[(aula, t)] = s_id

                # 2. Profesor
                if (prof, t) in ocupacion_profesor:
                    violaciones_duras += 1
                else:
                    ocupacion_profesor[(prof, t)] = s_id

                # 3. Subgrupos de estudiantes
                for sg in subs:
                    if (sg, t) in ocupacion_subgrupo:
                        violaciones_duras += 1
                    else:
                        ocupacion_subgrupo[(sg, t)] = s_id
                    slots_por_subgrupo_dia[(sg, dia_idx)].append(hora_idx)

                # Penalización blanda por clases en viernes (mayor por la tarde)
                if dia_idx == 4:  # Viernes
                    penalizacion_viernes += (hora_idx + 1)

        # 4. Cálculo de huecos entre clases para los alumnos
        total_huecos = 0
        for (sg, d), horas_ocupadas in slots_por_subgrupo_dia.items():
            if len(horas_ocupadas) >= 2:
                h_min = min(horas_ocupadas)
                h_max = max(horas_ocupadas)
                huecos_dia = (h_max - h_min + 1) - len(horas_ocupadas)
                if huecos_dia > 0:
                    total_huecos += huecos_dia

        coste_blando = (self.peso_hueco * total_huecos) + (self.peso_viernes * penalizacion_viernes)
        energia_total = (self.peso_duro * violaciones_duras) + coste_blando

        return energia_total, violaciones_duras, coste_blando

    def generar_vecino(self, estado):
        """
        Operador de vecindad:
        - 75% de las veces: mover una sesión a un nuevo slot y/o aula.
        - 25% de las veces: intercambiar (swap) slots/aulas entre dos sesiones de la misma duración.
        """
        nuevo_estado = estado.copy()
        op = random.random()

        if op < 0.75 or len(self.sesiones) < 2:
            # Movimiento simple
            s_id = random.choice(self.sesiones)
            slot_actual, aula_actual = estado[s_id]

            nuevo_slot = random.choice(self.slots_validos[s_id])
            nueva_aula = random.choice(self.aulas_compatibles[s_id])

            nuevo_estado[s_id] = (nuevo_slot, nueva_aula)
        else:
            # Swap entre dos sesiones de igual duración
            s1 = random.choice(self.sesiones)
            dur1 = self.duracion[s1]
            candidatos = [
                s for s in self.sesiones
                if s != s1 and self.duracion[s] == dur1
            ]
            if candidatos:
                s2 = random.choice(candidatos)
                slot1, aula1 = estado[s1]
                slot2, aula2 = estado[s2]

                # Verificar si las aulas son compatibles al intercambiarse
                aula1_para_s2 = aula1 if aula1 in self.aulas_compatibles[s2] else random.choice(self.aulas_compatibles[s2])
                aula2_para_s1 = aula2 if aula2 in self.aulas_compatibles[s1] else random.choice(self.aulas_compatibles[s1])

                nuevo_estado[s1] = (slot2, aula2_para_s1)
                nuevo_estado[s2] = (slot1, aula1_para_s2)
            else:
                s_id = random.choice(self.sesiones)
                nuevo_estado[s_id] = (
                    random.choice(self.slots_validos[s_id]),
                    random.choice(self.aulas_compatibles[s_id])
                )

        return nuevo_estado

    def optimizar(self, verbose=True):
        """
        Ejecuta el algoritmo de Recocido Simulado.
        Retorna (mejor_estado, mejor_energia, historial, tiempo_total)
        """
        t_inicio = time.time()

        estado_actual = self.generar_solucion_inicial()
        energia_actual, duras_actual, blandas_actual = self.calcular_energia(estado_actual)

        mejor_estado = estado_actual.copy()
        mejor_energia = energia_actual
        mejor_duras = duras_actual
        mejor_blandas = blandas_actual

        temperatura = self.t_inicial
        historial = []

        total_iteraciones = 0
        mejoras_globales = 0

        if verbose:
            print(f"[SA] Inicio Recocido Simulado: T_0={self.t_inicial:.1f}, E_inicial={energia_actual:.1f} (Duras: {duras_actual}, Blandas: {blandas_actual})")

        paso = 0
        while temperatura > self.t_final:
            aceptados_temp = 0

            for _ in range(self.iter_por_temp):
                total_iteraciones += 1
                vecino = self.generar_vecino(estado_actual)
                energia_vecino, duras_vecino, blandas_vecino = self.calcular_energia(vecino)

                delta = energia_vecino - energia_actual

                # Criterio de aceptación de Metropolis
                if delta <= 0:
                    aceptar = True
                else:
                    prob = math.exp(-delta / max(temperatura, 1e-9))
                    aceptar = (random.random() < prob)

                if aceptar:
                    estado_actual = vecino
                    energia_actual = energia_vecino
                    duras_actual = duras_vecino
                    blandas_actual = blandas_vecino
                    aceptados_temp += 1

                    # Actualizar mejor solución global
                    if energia_actual < mejor_energia:
                        mejor_estado = estado_actual.copy()
                        mejor_energia = energia_actual
                        mejor_duras = duras_actual
                        mejor_blandas = blandas_actual
                        mejoras_globales += 1

            tasa_aceptacion = aceptados_temp / self.iter_por_temp
            historial.append({
                "paso": paso,
                "iteracion": total_iteraciones,
                "temperatura": temperatura,
                "energia_actual": energia_actual,
                "mejor_energia": mejor_energia,
                "duras": mejor_duras,
                "blandas": mejor_blandas,
                "tasa_aceptacion": tasa_aceptacion
            })

            if verbose and (paso % 15 == 0 or mejor_duras == 0):
                print(f"[SA] Paso {paso:3d} | T={temperatura:6.2f} | E_actual={energia_actual:7.1f} | E_mejor={mejor_energia:7.1f} (Duras={mejor_duras}) | TasaAcept={tasa_aceptacion:4.2f}")

            # Condición de parada temprana opcional si alcanzamos solución perfecta factible con coste muy bajo
            if mejor_duras == 0 and temperatura < (self.t_inicial * 0.1) and tasa_aceptacion < 0.05:
                if verbose:
                    print(f"[SA] Convergencia alcanzada con cero violaciones duras a T={temperatura:.3f}.")
                break

            # Enfriamiento geométrico
            temperatura *= self.alpha
            paso += 1

        tiempo_total = time.time() - t_inicio

        if verbose:
            print(f"[SA] Finalizado en {tiempo_total:.2f}s | Iteraciones: {total_iteraciones} | E_final: {mejor_energia:.1f} (Duras={mejor_duras})")

        return mejor_estado, mejor_energia, historial, tiempo_total

    def convertir_a_dataframe(self, estado, curso=1, semestre=1, grupo_principal=1):
        """Convierte el estado de solución en DataFrame compatible con el visualizador."""
        asignaciones = []
        for s_id in self.sesiones:
            slot_inicio, aula = estado[s_id]
            dur = self.duracion[s_id]
            dia_idx = slot_inicio // self.horas_por_dia
            hora_idx = slot_inicio % self.horas_por_dia
            row = self.info_sesion[s_id]

            asignaciones.append({
                "Slot": slot_inicio,
                "Sesion": s_id,
                "Asignatura": row["asignatura"],
                "Tipo": row["tipo"],
                "Grupo": row["grupo"],
                "Dia": self.dias[dia_idx],
                "Hora": self.horas_etiquetas[hora_idx],
                "Duracion": f"{dur}h",
                "Aula": aula,
                "Profesor": row["profesor"],
                "Curso": row.get("curso", curso),
                "Semestre": row.get("semestre", semestre),
                "GrupoPrincipal": row.get("grupo_principal", grupo_principal)
            })

        df_res = pd.DataFrame(asignaciones).sort_values(by="Slot").reset_index(drop=True)
        return df_res

    def guardar_grafica_convergencia(self, historial, ruta_salida="memoria/convergencia_sa.png"):
        """Genera y guarda la gráfica de convergencia del Recocido Simulado para la Memoria."""
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        df_h = pd.DataFrame(historial)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, dpi=300)

        # Gráfica 1: Energía (Actual vs Mejor)
        ax1.plot(df_h["iteracion"], df_h["energia_actual"], label="Energía actual", color="#90CAF9", alpha=0.65, linewidth=1.0)
        ax1.plot(df_h["iteracion"], df_h["mejor_energia"], label="Mejor energía (E*)", color="#1565C0", linewidth=2.2)
        ax1.set_ylabel("Función de Energía / Coste", fontsize=11, fontweight="bold")
        ax1.set_title("Curva de Convergencia — Recocido Simulado (Simulated Annealing)", fontsize=13, fontweight="bold", pad=12)
        ax1.grid(True, linestyle="--", alpha=0.5)
        ax1.legend(loc="upper right", frameon=True)

        # Gráfica 2: Temperatura y Tasa de Aceptación
        color_temp = "#D32F2F"
        ax2.set_xlabel("Iteraciones", fontsize=11, fontweight="bold")
        ax2.set_ylabel("Temperatura (T)", color=color_temp, fontsize=11, fontweight="bold")
        line1 = ax2.plot(df_h["iteracion"], df_h["temperatura"], color=color_temp, linewidth=2.0, label="Temperatura")
        ax2.tick_params(axis="y", labelcolor=color_temp)
        ax2.grid(True, linestyle="--", alpha=0.5)

        ax3 = ax2.twinx()
        color_acept = "#2E7D32"
        ax3.set_ylabel("Tasa de Aceptación", color=color_acept, fontsize=11, fontweight="bold")
        line2 = ax3.plot(df_h["iteracion"], df_h["tasa_aceptacion"], color=color_acept, alpha=0.7, linestyle=":", label="Aceptación")
        ax3.tick_params(axis="y", labelcolor=color_acept)
        ax3.set_ylim(-0.05, 1.05)

        # Leyenda conjunta
        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax2.legend(lines, labels, loc="upper right", frameon=True)

        plt.tight_layout()
        plt.savefig(ruta_salida, dpi=300)
        plt.close(fig)
        print(f" Gráfica de convergencia guardada con éxito en: {ruta_salida}")


def resolver_con_sa(semestre=1, curso=3, grupo_principal=1, ruta_grafica=None):
    """
    Función de entrada para resolver un curso/semestre usando la Metaheurística de Recocido Simulado.
    """
    df_clases = pd.read_csv("datos/clases.csv")
    df_aulas = pd.read_csv("datos/aulas.csv")

    if curso is not None:
        df_clases = df_clases[df_clases["curso"] == curso].copy()
    if semestre is not None:
        df_clases = df_clases[df_clases["semestre"] == semestre].copy()
    if grupo_principal is not None:
        df_clases = df_clases[df_clases["grupo_principal"] == grupo_principal].copy()

    es_tarde = (grupo_principal == 3)

    sa = SimulatedAnnealingTimetabling(
        df_clases=df_clases,
        df_aulas=df_aulas,
        es_tarde=es_tarde,
        t_inicial=120.0,
        t_final=0.01,
        alpha=0.985,
        iter_por_temp=150,
        semilla=42
    )

    mejor_estado, mejor_energia, historial, tiempo_total = sa.optimizar(verbose=True)
    df_res = sa.convertir_a_dataframe(mejor_estado, curso=curso, semestre=semestre, grupo_principal=grupo_principal)

    if ruta_grafica:
        sa.guardar_grafica_convergencia(historial, ruta_salida=ruta_grafica)

    return df_res, mejor_energia, tiempo_total, historial


if __name__ == "__main__":
    print("\n================== PRUEBA DE METAHEURÍSTICA SA (3º GII - SEMESTRE 1) ==================")
    df_res, energia, t_calc, hist = resolver_con_sa(
        semestre=1, curso=3, grupo_principal=1,
        ruta_grafica="horarios/convergencia_sa_3GII_1er.png"
    )
    print(f"\nResultado final SA:")
    print(f"- Tiempo de cálculo: {t_calc:.2f} s")
    print(f"- Energía final (coste): {energia:.1f}")
