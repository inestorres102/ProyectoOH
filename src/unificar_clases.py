
from pathlib import Path
import pandas as pd


def unificar_clases():
    """
    Unifica los ocho CSV originales en datos/clases.csv.
    Conserva los datos originales y añade curso, cuatrimestre
    y semanas_activas.
    """

    raiz = Path(__file__).resolve().parent.parent
    carpeta_originales = raiz / "datos" / "originales"
    archivo_salida = raiz / "datos" / "clases.csv"

    archivos = {
        "clases_1er_cuatri.csv": (1, 1),
        "clases_2do_cuatri.csv": (1, 2),
        "clases2_1er_cuatri.csv": (2, 1),
        "clases2_2do_cuatri.csv": (2, 2),
        "clases3_1er_cuatri.csv": (3, 1),
        "clases3_2do_cuatri.csv": (3, 2),
        "clases4_1er_cuatri.csv": (4, 1),
        "clases4_2do_cuatri.csv": (4, 2),
    }

    columnas_obligatorias = [
        "id_sesion",
        "asignatura",
        "tipo",
        "grupo",
        "duracion_horas",
        "num_alumnos",
        "tipo_aula_requerida",
        "profesor",
    ]

    clases_unificadas = []

    for nombre, (curso, cuatrimestre) in archivos.items():
        ruta = carpeta_originales / nombre

        if not ruta.exists():
            raise FileNotFoundError(
                f"No se encuentra el archivo: {ruta}"
            )

        df = pd.read_csv(ruta, encoding="utf-8-sig")
        df.columns = df.columns.str.strip()

        faltantes = [
            columna
            for columna in columnas_obligatorias
            if columna not in df.columns
        ]

        if faltantes:
            raise ValueError(
                f"En {nombre} faltan columnas: {faltantes}"
            )

        df = df[columnas_obligatorias].copy()

        df["curso"] = curso
        df["cuatrimestre"] = cuatrimestre

        # Se completará con el calendario real de cada actividad.
        df["semanas_activas"] = ""

        df["duracion_horas"] = pd.to_numeric(
            df["duracion_horas"], errors="raise"
        )

        df["num_alumnos"] = pd.to_numeric(
            df["num_alumnos"], errors="raise"
        )

        df["grupo"] = df["grupo"].astype(str).str.strip()

        clases_unificadas.append(df)

    resultado = pd.concat(
        clases_unificadas,
        ignore_index=True
    )

    if resultado["id_sesion"].duplicated().any():
        duplicados = resultado.loc[
            resultado["id_sesion"].duplicated(keep=False),
            ["id_sesion", "curso", "cuatrimestre"]
        ]

        print("Aviso: hay identificadores repetidos:")
        print(duplicados.to_string(index=False))

    archivo_salida.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    resultado.to_csv(
        archivo_salida,
        index=False,
        encoding="utf-8-sig"
    )

    print("Clases unificadas correctamente.")
    print(f"Archivo generado: {archivo_salida}")
    print(f"Total de sesiones: {len(resultado)}")
    print("\nSesiones por curso y cuatrimestre:")
    print(
        resultado.groupby(
            ["curso", "cuatrimestre"]
        ).size()
    )


if __name__ == "__main__":
    unificar_clases()
