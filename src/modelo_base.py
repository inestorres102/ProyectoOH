import pandas as pd
from ortools.sat.python import cp_model

def modelo_base():
    # 1. Definir el horizonte temporal semanal (30 franjas horarias)
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_por_dia = 6  # 6 franjas por día: de 08:30 a 14:30
    total_slots = len(dias) * horas_por_dia  # 30 turnos en total (0 a 29)

    horas_etiquetas = [
        "08:30-09:30", "09:30-10:30", "10:30-11:30",
        "11:30-12:30", "12:30-13:30", "13:30-14:30"
    ]



    # 2. Leer las sesiones desde la carpeta datos/
    ruta_clases = "datos/clases.csv"
    df_clases = pd.read_csv(ruta_clases)
    print(f"Cargadas con exito {len(df_clases)} sesiones desde '{ruta_clases}'.")



    # 3. Crear el modelo CP-SAT y definir variables de decisión
    model = cp_model.CpModel()

    start_vars = {}     # Variable entera: slot en el que arranca la sesión (0..29)
    end_vars = {}       # Variable entera: slot en el que termina
    interval_vars = {}  # Intervalo continuo: une inicio, duracion y fin

    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"])
        duracion = int(row["duracion_horas"])

        # Una sesión no puede empezar tan tarde como para salirse de la semana
        start = model.NewIntVar(0, total_slots - duracion, f"start_{s_id}")
        end = model.NewIntVar(duracion, total_slots, f"end_{s_id}")
        
        # NewIntervalVar enlaza matemáticamente: end == start + duracion
        interval = model.NewIntervalVar(start, duracion, end, f"interval_{s_id}")

        start_vars[s_id] = start
        end_vars[s_id] = end
        interval_vars[s_id] = interval



    # 4. Resolver (sin restricciones añadidas todavía)
    solver = cp_model.CpSolver()
    status = solver.Solve(model)



    # 5. Imprimir la asignación temporal básica por consola
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("\n Horario base generado (sin restricciones de solape todavia):\n")
        asignaciones = []
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"])
            slot_inicio = solver.Value(start_vars[s_id])

            dia_idx = slot_inicio // horas_por_dia
            hora_idx = slot_inicio % horas_por_dia

            asignaciones.append({
                "Sesion": s_id,
                "Asignatura": row["asignatura"],
                "Tipo": row["tipo"],
                "Grupo": row["grupo"],
                "Dia": dias[dia_idx],
                "Hora": horas_etiquetas[hora_idx],
                "Duracion": f"{row['duracion_horas']}h",
                "Profesor": row["profesor"]
            })

        df_resultado = pd.DataFrame(asignaciones)
        print(df_resultado.to_string(index=False))
    else:
        print("No se encontro solucion factible.")

if __name__ == "__main__":
    modelo_base()