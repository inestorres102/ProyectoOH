
from pathlib import Path
import pandas as pd

# Carpeta raíz del proyecto
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_ORIGINALES = RAIZ / "datos" / "originales"
RUTA_SALIDA = RAIZ / "datos" / "clases.csv"

# Archivo: (curso, cuatrimestre)
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

tablas = []

for nombre, (curso, cuatrimestre) in archivos.items():
    ruta = CARPETA_ORIGINALES / nombre

    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encuentra el archivo: {ruta}"
        )

    df = pd.read_csv(ruta, encoding="utf-8-sig")

    # Comprobar que todos los archivos tienen las columnas esperadas
    faltantes = set(columnas_obligatorias) - set(df.columns)

    if faltantes:
        raise ValueError(
            f"{nombre} no contiene estas columnas: {faltantes}"
        )

    # Limpiar espacios sobrantes en los campos de texto
    for columna in df.select_dtypes(include=["object"]).columns:
        df[columna] = df[columna].str.strip()

    # Añadir el contexto de cada sesión
    df["curso"] = curso
    df["cuatrimestre"] = cuatrimestre

    tablas.append(df)

# Unir los ocho archivos
clases = pd.concat(tablas, ignore_index=True)

# Comprobar que no hay filas vacías en los campos esenciales
if clases[columnas_obligatorias].isna().any().any():
    raise ValueError(
        "Hay campos vacíos en las clases. Revisa los CSV originales."
    )

# Guardar un único CSV
clases.to_csv(RUTA_SALIDA, index=False, encoding="utf-8-sig")

print("CSV unificado creado correctamente.")
print(f"Total de sesiones: {len(clases)}")
print("\nSesiones por curso y cuatrimestre:")
print(
    clases.groupby(["curso", "cuatrimestre"])
    .size()
    .to_string()
)
print(f"\nArchivo generado: {RUTA_SALIDA}")
