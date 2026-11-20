
from pathlib import Path

import pandas as pd
from ortools.sat.python import cp_model

from restricciones import (
    aplicar_restriccion_estudiantes,
    aplicar_restriccion_cambio_dia,
    aplicar_restriccion_profesores,
    aplicar_restriccion_aulas,
    aplicar_restricciones_blandas
)

from visualizador import exportar_horario_png


def modelo_base(curso=2, cuatrimestre=2):

    # 1. Definir el horizonte temporal semanal
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_por_dia = 6
    total_slots = len(dias) * horas_por_dia

    horas_etiquetas = [
        "08:30-09:30",
        "09:30-10:30",
        "10:30-11:30",
        "11:30-12:30",
        "12:30-13:30",
        "13:30-14:30"
    ]

    # 2. Localizar la carpeta raíz
    raiz = Path(__file__).resolve().parent.parent

    # 3. Leer las clases
    ruta_clases = raiz / "datos" / "clases.csv"

    if not ruta_clases.exists():
        print(f"ERROR: No se encuentra el archivo {ruta_clases}")
        return

    df_todas_clases = pd.read_csv(ruta_clases)

    columnas_necesarias = {
        "id_sesion",
        "asignatura",
        "tipo",
        "grupo",
        "duracion_horas",
        "num_alumnos",
        "tipo_aula_requerida",
        "profesor",
        "curso",
        "cuatrimestre"
    }

    faltan = columnas_necesarias - set(df_todas_clases.columns)

    if faltan:
        print(f"ERROR: Faltan columnas en clases.csv: {sorted(faltan)}")
        return

    # 4. Seleccionar curso y cuatrimestre
    df_clases = df_todas_clases[
        (df_todas_clases["curso"] == curso)
        & (df_todas_clases["cuatrimestre"] == cuatrimestre)
    ].copy()

    if df_clases.empty:
        print("No hay sesiones para el curso y cuatrimestre seleccionados.")
        return

    df_clases["id_sesion"] = (
        df_clases["id_sesion"].astype(str).str.strip()
    )

    if df_clases["id_sesion"].duplicated().any():
        print("ERROR: Hay identificadores de sesión duplicados.")
        return

    # 5. Dividir las horas semanales en bloques de 1 o 2 horas
    df_clases["id_sesion_original"] = df_clases["id_sesion"]

    clases_divididas = []

    for _, row in df_clases.iterrows():

        horas_restantes = int(row["duracion_horas"])
        bloques = []

        while horas_restantes > 0:
            bloque = 2 if horas_restantes >= 2 else 1
            bloques.append(bloque)
            horas_restantes -= bloque

        for i, duracion_bloque in enumerate(bloques, start=1):

            nueva_fila = row.copy()

            nueva_fila["id_sesion"] = (
                f"{row['id_sesion_original']}_B{i}"
            )

            nueva_fila["duracion_horas"] = duracion_bloque

            clases_divididas.append(nueva_fila)

    df_clases = pd.DataFrame(clases_divididas).reset_index(drop=True)

    print(
        f"\nCurso seleccionado: {curso}º GIFM | "
        f"Cuatrimestre: {cuatrimestre}º"
    )
    print(f"Sesiones originales: {len(df_clases['id_sesion_original'].unique())}")
    print(f"Bloques horarios generados: {len(df_clases)}")

    # 6. Leer aulas
    ruta_aulas = raiz / "datos" / "aulas.csv"

    if not ruta_aulas.exists():
        print(f"ERROR: No se encuentra el archivo {ruta_aulas}")
        return

    df_aulas = pd.read_csv(ruta_aulas)

    print(f"Aulas disponibles: {len(df_aulas)}")

    # 7. Crear el modelo
    model = cp_model.CpModel()

    start_vars = {}
    end_vars = {}
    interval_vars = {}

    for _, row in df_clases.iterrows():

        s_id = str(row["id_sesion"]).strip()
        duracion = int(row["duracion_horas"])

        if duracion < 1 or duracion > total_slots:
            print(f"ERROR: Duración no válida en {s_id}")
            return

        start = model.NewIntVar(
            0,
            total_slots - duracion,
            f"start_{s_id}"
        )

        end = model.NewIntVar(
            duracion,
            total_slots,
            f"end_{s_id}"
        )

        interval = model.NewIntervalVar(
            start,
            duracion,
            end,
            f"interval_{s_id}"
        )

        start_vars[s_id] = start
        end_vars[s_id] = end
        interval_vars[s_id] = interval

    # 8. Restricciones duras

    # Alumnos
    aplicar_restriccion_estudiantes(
        model,
        df_clases,
        interval_vars
    )

    # Evitar que los bloques atraviesen dos días
    aplicar_restriccion_cambio_dia(
        model,
        df_clases,
        start_vars,
        end_vars,
        horas_por_dia
    )

    # Profesores
    aplicar_restriccion_profesores(
        model,
        df_clases,
        interval_vars
    )

    # Aulas
    aula_asignada = aplicar_restriccion_aulas(
        model,
        df_clases,
        df_aulas,
        start_vars,
        end_vars
    )

    # Los bloques de una misma sesión deben ir en días distintos
    for _, bloques in df_clases.groupby("id_sesion_original"):

        ids = bloques["id_sesion"].astype(str).tolist()

        dias_bloques = []

        for s_id in ids:

            dia = model.NewIntVar(
                0,
                4,
                f"dia_{s_id}"
            )

            model.AddDivisionEquality(
                dia,
                start_vars[s_id],
                horas_por_dia
            )

            dias_bloques.append(dia)

        if len(dias_bloques) > 1:
            model.AddAllDifferent(dias_bloques)

    # 9. Restricciones blandas
    aplicar_restricciones_blandas(
        model,
        df_clases,
        start_vars,
        aula_asignada,
        total_slots=total_slots,
        aula_preferida="A3-1"
    )

    # 10. Resolver
    solver = cp_model.CpSolver()

    solver.parameters.stop_after_first_solution = True
    solver.parameters.max_time_in_seconds = 10.0

    status = solver.Solve(model)

    # 11. Mostrar resultados
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

        print(
            df_resultado.drop(columns=["Slot"]).to_string(index=False)
        )

        # 12. Exportar horario
        carpeta_resultados = raiz / "resultados"
        carpeta_resultados.mkdir(parents=True, exist_ok=True)

        ruta_salida = carpeta_resultados / (
            f"horario_{curso}GIFM_{cuatrimestre}cuatri_nuevo.png"
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
            "Revisa las restricciones y los datos."
        )


if __name__ == "__main__":
    modelo_base(curso=2, cuatrimestre=2)
