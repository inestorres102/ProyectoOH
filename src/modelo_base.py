import glob
import os
import pandas as pd
from ortools.sat.python import cp_model

# Importamos las restricciones desde 'restricciones.py'
from restricciones import (
    aplicar_restriccion_estudiantes,
    aplicar_restriccion_cambio_dia,
    aplicar_restriccion_profesores,
    aplicar_restriccion_aulas,
    aplicar_restricciones_blandas,
    aplicar_restriccion_sin_huecos,
    aplicar_restriccion_dias_libres_practicas
)

from visualizador import exportar_horario_png


def modelo_base(cuatrimestre=1):
    # 1. Definir el horizonte temporal semanal (30 franjas horarias)
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_por_dia = 6  # 6 franjas por día: de 08:30 a 14:30
    total_slots = len(dias) * horas_por_dia  # 30 turnos en total (0 a 29)

    horas_etiquetas = [
        "08:30-09:30", "09:30-10:30", "10:30-11:30",
        "11:30-12:30", "12:30-13:30", "13:30-14:30"
    ]

    # 2. Leer las sesiones desde la carpeta datos/
    archivos_clases = glob.glob("datos/clases_*.csv")
    if archivos_clases:
        df_clases_total = pd.concat([pd.read_csv(f) for f in archivos_clases], ignore_index=True)
    elif os.path.exists("datos/clases.csv"):
        df_clases_total = pd.read_csv("datos/clases.csv")
    else:
        raise FileNotFoundError("No se encontró ningún archivo de clases en 'datos/'")

    # Limpiar espacios en los nombres de las columnas
    df_clases_total.columns = df_clases_total.columns.str.strip()

    # Asegurar tipo numérico en curso y cuatrimestre
    if "curso" in df_clases_total.columns:
        df_clases_total["curso"] = pd.to_numeric(df_clases_total["curso"], errors="coerce").fillna(3).astype(int)

    if "cuatrimestre" in df_clases_total.columns:
        df_clases_total["cuatrimestre"] = pd.to_numeric(df_clases_total["cuatrimestre"], errors="coerce").fillna(1).astype(int)
        df_clases = df_clases_total[df_clases_total["cuatrimestre"] == cuatrimestre].copy()
    else:
        df_clases = df_clases_total.copy()

    df_aulas = pd.read_csv("datos/aulas.csv")
    df_aulas.columns = df_aulas.columns.str.strip()

    print(f"\n=======================================================")
    print(f"      OPTIMIZANDO HORARIO: CUATRIMESTRE {cuatrimestre}")
    print(f"=======================================================")
    print(f"Sesiones cargadas: {len(df_clases)} | Aulas disponibles: {len(df_aulas)}")

    # 3. Crear el modelo CP-SAT y definir variables de decisión
    model = cp_model.CpModel()

    start_vars = {}     # Variable entera: slot en el que arranca la sesión (0..29)
    end_vars = {}       # Variable entera: slot en el que termina
    interval_vars = {}  # Intervalo continuo: une inicio, duracion y fin

    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()
        duracion = int(row["duracion_horas"])

        # Una sesión no puede empezar tan tarde como para salirse de la semana
        start = model.NewIntVar(0, total_slots - duracion, f"start_{s_id}")
        end = model.NewIntVar(duracion, total_slots, f"end_{s_id}")
        
        # Enlace matemático: end == start + duracion
        interval = model.NewIntervalVar(start, duracion, end, f"interval_{s_id}")

        start_vars[s_id] = start
        end_vars[s_id] = end
        interval_vars[s_id] = interval

    # ---------------------------------------------------------
    # APLICAR RESTRICCIONES DURAS
    # ---------------------------------------------------------
    # A. Estudiantes (evitar solapes de un mismo grupo dentro de su curso)
    aplicar_restriccion_estudiantes(model, df_clases, interval_vars)
    
    # B. Coherencia horaria (no partir sesiones entre días distintos)
    aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, horas_por_dia)
    
    # C. Profesores (un profesor no puede estar en dos sitios a la vez)
    aplicar_restriccion_profesores(model, df_clases, interval_vars)
    
    # D. Aulas (capacidad, tipo y evitar solapamiento físico)
    aula_asignada = aplicar_restriccion_aulas(model, df_clases, df_aulas, start_vars, end_vars)
    
    # E. Sin huecos libres para el mismo grupo dentro de cada curso
    aplicar_restriccion_sin_huecos(model, df_clases, start_vars, end_vars, horas_por_dia)
    
    # F. Si estamos optimizando el 2º cuatrimestre, liberamos jueves y viernes para prácticas externas
    if cuatrimestre == 2:
        aplicar_restriccion_dias_libres_practicas(model, df_clases, start_vars)

    # ---------------------------------------------------------
    # RESTRICCIONES BLANDAS (FUNCIÓN OBJETIVO)
    # ---------------------------------------------------------
    aplicar_restricciones_blandas(model, df_clases, start_vars, aula_asignada, total_slots=total_slots, aula_preferida="A2-5")

    # 4. Resolver
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # 5. Imprimir y exportar resultados
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n[OK] Horario encontrado para el Cuatrimestre {cuatrimestre}.\n")
        asignaciones = []

        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            slot_inicio = solver.Value(start_vars[s_id])

            dia_idx = slot_inicio // horas_por_dia
            hora_idx = slot_inicio % horas_por_dia

            # Buscar qué aula se le asignó a esta sesión
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
                "Curso": int(row["curso"]),
                "Asignatura": row["asignatura"],
                "Tipo": row["tipo"],
                "Grupo": row["grupo"],
                "Dia": dias[dia_idx],
                "Hora": horas_etiquetas[hora_idx],
                "Duracion": f"{row['duracion_horas']}h",
                "Aula": aula_elegida,
                "Profesor": row["profesor"]
            })

        df_resultado = pd.DataFrame(asignaciones).sort_values(by="Slot")
        print(df_resultado.drop(columns=["Slot"]).to_string(index=False))

        # SEPARAR Y EXPORTAR UNA IMAGEN POR CADA CURSO RESUELTO
        cursos_disponibles = sorted(df_resultado["Curso"].unique())
        for cur in cursos_disponibles:
            df_curso = df_resultado[df_resultado["Curso"] == cur].copy()
            print(f"\nGenerando imagen para {cur}º GCID (Semestre {cuatrimestre})...")
            
            exportar_horario_png(
                df_resultado=df_curso,
                curso=int(cur),
                cuatrimestre=cuatrimestre,
                abrir_al_terminar=True
            )
    else:
        print(f"No se encontró solución factible para el Cuatrimestre {cuatrimestre}. Comprobar disponibilidad de aulas o solapamientos.")


if __name__ == "__main__":
    print("==================================================")
    print("     GENERACIÓN AUTOMÁTICA DE CALENDARIOS GCID    ")
    print("==================================================")
    # Ejecuta automáticamente ambos cuatrimestres
    for c in [1, 2]:
        modelo_base(cuatrimestre=c)