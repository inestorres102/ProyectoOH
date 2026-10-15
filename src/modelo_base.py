import pandas as pd
from ortools.sat.python import cp_model

# Importamos las restricciones desde el nuevo fichero 'restricciones.py'
from restricciones import (
    aplicar_restriccion_estudiantes,
    aplicar_restriccion_cambio_dia,
    aplicar_restriccion_profesores
)


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


# APLICAR RESTRICCIONES DURAS
    # 1. Primera restricción dura: Los alumnos no se solapan
    aplicar_restriccion_estudiantes(model, df_clases, interval_vars)
    
    # 2. Control de días: Una clase no cruza de un día a otro
    aplicar_restriccion_cambio_dia(model, df_clases, start_vars, end_vars, horas_por_dia)
    
    # 3. Un profesor no puede impartir dos sesiones al mismo tiempo
    aplicar_restriccion_profesores(model, df_clases, interval_vars)



    # 4. Resolver (con dos restricciones)
    solver = cp_model.CpSolver()
    status = solver.Solve(model)



    # 5. Imprimir la asignación temporal básica por consola
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("\n Horario base generado (con restriccion de solape y de profesor):\n")
        asignaciones = []
        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"])
            slot_inicio = solver.Value(start_vars[s_id])

            dia_idx = slot_inicio // horas_por_dia
            hora_idx = slot_inicio % horas_por_dia

            asignaciones.append({
                "Slot": slot_inicio,
                "Sesion": s_id,
                "Asignatura": row["asignatura"],
                "Tipo": row["tipo"],
                "Grupo": row["grupo"],
                "Dia": dias[dia_idx],
                "Hora": horas_etiquetas[hora_idx],
                "Duracion": f"{row['duracion_horas']}h",
                "Profesor": row["profesor"]
            })

        # Ordenamos numéricamente por slot (de 0 a 29)
        df_resultado = pd.DataFrame(asignaciones).sort_values(by="Slot")
        #Quitamos la columna 'Slot' solo para que la tabla quede limpia
        print(df_resultado.drop(columns=["Slot"]).to_string(index=False))
    else:
        print("No se encontro solucion factible.")

if __name__ == "__main__":
    modelo_base()