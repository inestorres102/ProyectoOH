
from pathlib import Path

import pandas as pd
from ortools.sat.python import cp_model

# Importamos las restricciones desde el fichero 'restricciones.py'
from restricciones import (
    aplicar_restriccion_estudiantes,
    aplicar_restriccion_cambio_dia,
    aplicar_restriccion_profesores,
    aplicar_restriccion_aulas,
    aplicar_restricciones_blandas
)

from visualizador import exportar_horario_png


def modelo_base(curso=1, cuatrimestre=1):
    # 1. Definir el horizonte temporal semanal (30 franjas horarias)
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_por_dia = 6  # 6 franjas por día: de 08:30 a 14:30
    total_slots = len(dias) * horas_por_dia

    horas_etiquetas = [
        "08:30-09:30", "09:30-10:30", "10:30-11:30",
        "11:30-12:30", "12:30-13:30",
        "13:30-14:30"
    ]

    # 2. Localizar la carpeta raíz del proyecto
    raiz = Path(__file__).resolve().parent.parent

    # 3. Leer las clases del archivo unificado
    ruta_clases = raiz / "datos" / "clases.csv"

    if not ruta_clases.exists():
        print(f"ERROR: No se encuentra el archivo {ruta_clases}")
        print("Comprueba que existe datos/clases.csv en la carpeta del proyecto.")
        return

    df_todas_clases = pd.read_csv(ruta_clases)

    # Comprobar que el archivo contiene las columnas necesarias
    columnas_necesarias = {
        "id_sesion", "asignatura", "tipo", "grupo",
        "duracion_horas", "num_alumnos", "tipo_aula_requerida",
        "profesor", "curso", "cuatrimestre"
    }

    faltan = columnas_necesarias - set(df_todas_clases.columns)

    if faltan:
        print(f"ERROR: Faltan columnas en clases.csv: {sorted(faltan)}")
        return

    # 4. Seleccionar el curso y cuatrimestre solicitados
    df_clases = df_todas_clases[
        (df_todas_clases["curso"] == curso)
        & (df_todas_clases["cuatrimestre"] == cuatrimestre)
    ].copy()

    if df_clases.empty:
        print(
            f"No hay sesiones para el curso {curso}, "
            f"cuatrimestre {cuatrimestre}."
        )
        return

    # Evitar problemas con espacios en los identificadores
    df_clases["id_sesion"] = df_clases["id_sesion"].astype(str).str.strip()

    # Los identificadores deben ser únicos dentro del horario seleccionado
    if df_clases["id_sesion"].duplicated().any():
        duplicados = df_clases.loc[
            df_clases["id_sesion"].duplicated(keep=False), "id_sesion"
        ].tolist()
        print(f"ERROR: Hay identificadores de sesión duplicados: {duplicados}")
        print("Revisa los id_sesion del curso y cuatrimestre seleccionados.")
        return

    print(
        f"\nCurso seleccionado: {curso}º GIFM | "
        f"Cuatrimestre: {cuatrimestre}º"
    )
    print(f"Sesiones cargadas: {len(df_clases)}")

    # 5. Leer las aulas disponibles
    ruta_aulas = raiz / "datos" / "aulas.csv"

    if not ruta_aulas.exists():
        print(f"ERROR: No se encuentra el archivo {ruta_aulas}")
        return

    df_aulas = pd.read_csv(ruta_aulas)
    print(f"Aulas disponibles: {len(df_aulas)}")

    # 6. Crear el modelo CP-SAT y definir variables de decisión
    model = cp_model.CpModel()

    start_vars = {}
    end_vars = {}
    interval_vars = {}

    for _, row in df_clases.iterrows():
        s_id = str(row["id_sesion"]).strip()
        duracion = int(row["duracion_horas"])

        # La sesión debe caber dentro del horizonte semanal
        if duracion < 1 or duracion > total_slots:
            print(
                f"ERROR: La sesión {s_id} tiene una duración no válida: "
                f"{duracion}."
            )
            return

        start = model.NewIntVar(
            0, total_slots - duracion, f"start_{s_id}"
        )
        end = model.NewIntVar(
            duracion, total_slots, f"end_{s_id}"
        )

        # Enlaza matemáticamente: end == start + duracion
        interval = model.NewIntervalVar(
            start, duracion, end, f"interval_{s_id}"
        )

        start_vars[s_id] = start
        end_vars[s_id] = end
        interval_vars[s_id] = interval

    # 7. Aplicar restricciones duras

    # Alumnos
    aplicar_restriccion_estudiantes(
        model, df_clases, interval_vars
    )

    # Coherencia horaria: evitar que una sesión atraviese varios días
    aplicar_restriccion_cambio_dia(
        model, df_clases, start_vars, end_vars, horas_por_dia
    )

    # Profesores
    aplicar_restriccion_profesores(
        model, df_clases, interval_vars
    )

    # Aulas: tipo requerido y no solapamiento físico
    aula_asignada = aplicar_restriccion_aulas(
        model, df_clases, df_aulas, start_vars, end_vars
    )

    # 8. Restricciones blandas (preferencias)
    aplicar_restricciones_blandas(
        model,
        df_clases,
        start_vars,
        aula_asignada,
        total_slots=total_slots,
        aula_preferida="A3-1"
    )

    # 9. Resolver el modelo
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # 10. Mostrar e imprimir el horario
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(
            f"\nHorario del {curso}º curso, "
            f"{cuatrimestre}º cuatrimestre:\n"
        )

        asignaciones = []

        for _, row in df_clases.iterrows():
            s_id = str(row["id_sesion"]).strip()
            slot_inicio = solver.Value(start_vars[s_id])

            dia_idx = slot_inicio // horas_por_dia
            hora_idx = slot_inicio % horas_por_dia

            # Buscar el aula asignada a esta sesión
            aula_elegida = "Sin aula"

            for a_id in df_aulas["id_aula"].astype(str).str.strip():
                var_aula = aula_asignada.get((s_id, a_id))

                if var_aula is not None and solver.Value(var_aula) == 1:
                    aula_elegida = a_id
                    break

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
                "Profesor": row["profesor"]
            })

        df_resultado = pd.DataFrame(asignaciones).sort_values(
            by="Slot"
        )

        print(df_resultado.drop(columns=["Slot"]).to_string(index=False))

        # 11. Guardar el horario en resultados/ sin sobrescribir otros
        carpeta_resultados = raiz / "resultados"
        carpeta_resultados.mkdir(parents=True, exist_ok=True)

        ruta_salida = carpeta_resultados / (
            f"horario_{curso}GIFM_{cuatrimestre}cuatri.png"
        )

        titulo = (
            f"CALENDARIO ACADÉMICO — {curso}º GIFM "
            f"({cuatrimestre}º CUATRIMESTRE)"
        )

        exportar_horario_png(
            df_resultado,
            ruta_salida=str(ruta_salida),
            abrir_al_terminar=True,
            titulo=titulo
        )

        print(f"\nHorario guardado en: {ruta_salida}")

    else:
        print(
            "\nNo se encontró una solución factible. "
            "Comprueba si hay suficientes aulas del tipo requerido "
            "y si las restricciones son compatibles."
        )


if __name__ == "__main__":
    # Cambia estos dos valores para elegir el horario que quieres generar.
    modelo_base(curso=1, cuatrimestre=1)
