
from pathlib import Path
import re
import unicodedata

import pandas as pd


# =========================================================
# RUTAS
# =========================================================

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_ORIGINALES = RAIZ_PROYECTO / "datos" / "originales"
ARCHIVO_SALIDA = RAIZ_PROYECTO / "datos" / "clases.csv"

ARCHIVOS_ORIGINALES = [
    "clases_1er_cuatri.csv",
    "clases_2do_cuatri.csv",
    "clases2_1er_cuatri.csv",
    "clases2_2do_cuatri.csv",
    "clases3_1er_cuatri.csv",
    "clases3_2do_cuatri.csv",
    "clases4_1er_cuatri.csv",
    "clases4_2do_cuatri.csv",
]

TOTAL_SEMANAS = 15


# =========================================================
# NORMALIZACIÓN
# =========================================================

def normalizar_texto(valor):
    """Normaliza texto para comparar asignaturas y tipos."""

    if pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


def normalizar_asignatura(valor):
    """Unifica denominaciones distintas de una misma asignatura."""

    asignatura = str(valor).strip().upper()

    equivalencias = {
        "FFT": "FFFT",
        "MACT": "MCAT",
    }

    return equivalencias.get(asignatura, asignatura)


def normalizar_tipo(valor):
    """Normaliza el tipo de actividad."""

    tipo = normalizar_texto(valor)

    if "teoria" in tipo:
        return "teoria"

    if "laboratorio" in tipo or tipo == "lab":
        return "laboratorio"

    if "practica" in tipo or "practicas" in tipo:
        return "practica"

    return tipo


def limpiar_columnas(df):
    """Limpia nombres de columnas procedentes de los CSV."""

    nuevas = []

    for columna in df.columns:
        nombre = str(columna).strip()
        nombre = nombre.replace("\ufeff", "")
        nombre = nombre.replace("**", "")
        nombre = nombre.strip()

        nuevas.append(nombre)

    df.columns = nuevas

    return df


# =========================================================
# ASIGNACIÓN DE SEMANAS
# =========================================================

def crear_mapa_semanas():
    """
    Mapa de semanas por curso, cuatrimestre, asignatura y tipo.

    Las prácticas de una misma asignatura pueden reunir varias fases
    del calendario oficial. Como el CSV original contiene una sola fila
    para esas prácticas, se utiliza el periodo conjunto de actividad.
    """

    mapa = {}

    def asignar(curso, cuatri, asignatura, tipo, semanas):
        mapa[
            (
                curso,
                cuatri,
                normalizar_asignatura(asignatura),
                normalizar_tipo(tipo),
            )
        ] = semanas

    # -----------------------------------------------------
    # 1.º GIFM - 1.º CUATRIMESTRE
    # El PDF no indica cambios semanales para estas sesiones.
    # -----------------------------------------------------

    for asignatura in ["FF1", "IFM", "FM1", "AL", "P1"]:
        asignar(1, 1, asignatura, "teoria", "1-15")
        asignar(1, 1, asignatura, "practica", "1-15")

    # -----------------------------------------------------
    # 1.º GIFM - 2.º CUATRIMESTRE
    # -----------------------------------------------------

    for asignatura in ["FF2", "MNF", "G1", "FM2"]:
        asignar(1, 2, asignatura, "teoria", "1-15")

    # MNF tiene actividades señaladas para las primeras 5
    # y las últimas 10 semanas. El CSV agrupa sus prácticas
    # en una sola fila de 4 horas semanales.
    asignar(1, 2, "MNF", "practica", "1-15")

    # FEC1 tiene prácticas diferenciadas por laboratorio
    # y día, pero el CSV las agrupa en una sola actividad.
    asignar(1, 2, "FEC1", "practica", "1-15")

    # -----------------------------------------------------
    # 2.º GIFM - 1.º CUATRIMESTRE
    # -----------------------------------------------------

    for asignatura in ["MAR", "T", "MMA1", "AM1", "P2"]:
        asignar(2, 1, asignatura, "teoria", "1-15")

    # MAR: el PDF distingue primeras 12 y últimas 3 semanas.
    # La fila de prácticas del CSV no separa esas fases.
    asignar(2, 1, "MAR", "practica", "1-15")

    # T y MMA1: prácticas asociadas a las primeras 11 semanas.
    asignar(2, 1, "T", "practica", "1-11")
    asignar(2, 1, "MMA1", "practica", "1-11")
    asignar(2, 1, "P2", "practica", "1-15")

    # -----------------------------------------------------
    # 2.º GIFM - 2.º CUATRIMESTRE
    # -----------------------------------------------------

    for asignatura in ["FEC2", "FE", "EOF1", "AM2", "G2", "P"]:
        asignar(2, 2, asignatura, "teoria", "1-15")

    # FEC2: cambia de laboratorio según las semanas.
    # El CSV no separa las actividades por laboratorio.
    asignar(2, 2, "FEC2", "practica", "1-15")

    # FE: el PDF diferencia actividades de la primera semana
    # y de las primeras 14 semanas. Se conserva el periodo
    # conjunto al estar agrupadas en una sola fila por grupo.
    asignar(2, 2, "FE", "practica", "1-14")

    # EOF1: teoría primeras 12 semanas y prácticas últimas 3.
    asignar(2, 2, "EOF1", "teoria", "1-12")
    asignar(2, 2, "EOF1", "practica", "13-15")

    # -----------------------------------------------------
    # 3.º GIFM - 1.º CUATRIMESTRE
    # -----------------------------------------------------

    # MMA2:
    # Teoría 1-11; prácticas de aula 12-14;
    # laboratorio 15.
    asignar(3, 1, "MMA2", "teoria", "1-11")
    asignar(3, 1, "MMA2", "practica", "12-15")

    # E:
    # Teoría 1-5; prácticas de aula 6-11;
    # laboratorio 12-15.
    asignar(3, 1, "E", "teoria", "1-5")
    asignar(3, 1, "E", "practica", "6-15")

    # AM3:
    # Teoría 1-10; prácticas de aula 11-15.
    asignar(3, 1, "AM3", "teoria", "1-10")
    asignar(3, 1, "AM3", "practica", "11-15")

    # EOF2:
    # Teoría 1-10; semana 11 teoría y práctica;
    # aula 12-13; laboratorio 14-15.
    asignar(3, 1, "EOF2", "teoria", "1-11")
    asignar(3, 1, "EOF2", "practica", "11-15")

    # FMC:
    # Teoría 1-9; laboratorio 13-15.
    asignar(3, 1, "FMC", "teoria", "1-9")
    asignar(3, 1, "FMC", "practica", "13-15")

    # -----------------------------------------------------
    # 3.º GIFM - 2.º CUATRIMESTRE
    # -----------------------------------------------------

    # FFFT:
    # Teoría 1-10; semana 11 teoría y aula;
    # aula 12-13; laboratorio 14-15.
    asignar(3, 2, "FFFT", "teoria", "1-11")
    asignar(3, 2, "FFFT", "practica", "11-15")

    # ESM:
    # Teoría 1-6; semana 7 teoría y aula;
    # aula 8-11; laboratorio 12-15.
    asignar(3, 2, "ESM", "teoria", "1-7")
    asignar(3, 2, "ESM", "practica", "7-15")

    # IM:
    # Teoría 1-13; aula 14-15;
    # práctica especial semana 1; laboratorio 9-15.
    asignar(3, 2, "IM", "teoria", "1-13")
    asignar(3, 2, "IM", "practica", "1,9-15")

    # MMA3:
    # Teoría 1-7; aula 8-13; laboratorio 14-15.
    asignar(3, 2, "MMA3", "teoria", "1-7")
    asignar(3, 2, "MMA3", "practica", "8-15")

    # FPAT:
    # Teoría 1-13; laboratorio 14-15.
    asignar(3, 2, "FPAT", "teoria", "1-13")
    asignar(3, 2, "FPAT", "practica", "14-15")

    # FO:
    # Teoría 1-10; laboratorio 11-15.
    asignar(3, 2, "FO", "teoria", "1-10")
    asignar(3, 2, "FO", "practica", "11-15")

    # AP:
    # Teoría 1-7; semana 8 teoría y laboratorio;
    # laboratorio 9-15.
    asignar(3, 2, "AP", "teoria", "1-8")
    asignar(3, 2, "AP", "practica", "8-15")

    # IE:
    # Teoría 1-10; aula 11-13; laboratorio 14-15.
    asignar(3, 2, "IE", "teoria", "1-10")
    asignar(3, 2, "IE", "practica", "11-15")

    # -----------------------------------------------------
    # 4.º GIFM - 1.º CUATRIMESTRE
    # -----------------------------------------------------

    asignar(4, 1, "MCAT", "teoria", "1-11")
    asignar(4, 1, "MCAT", "practica", "12-15")

    asignar(4, 1, "FESC", "teoria", "1-9")
    asignar(4, 1, "FESC", "practica", "10-15")

    # PI no tiene desglose semanal en las notas del PDF.
    asignar(4, 1, "PI", "teoria", "1-15")
    asignar(4, 1, "PI", "practica", "1-15")

    asignar(4, 1, "AM4", "teoria", "1-10")
    asignar(4, 1, "AM4", "practica", "11-15")

    asignar(4, 1, "DGDM", "teoria", "1-5")
    asignar(4, 1, "DGDM", "practica", "6-15")

    asignar(4, 1, "DF", "teoria", "1-9")
    asignar(4, 1, "DF", "practica", "10-15")

    asignar(4, 1, "FRIAT", "teoria", "1-5")
    asignar(4, 1, "FRIAT", "practica", "6-15")

    asignar(4, 1, "MEM", "teoria", "1-5")
    asignar(4, 1, "MEM", "practica", "6-15")

    # -----------------------------------------------------
    # 4.º GIFM - 2.º CUATRIMESTRE
    # -----------------------------------------------------

    # CC no tiene desglose semanal en las notas del PDF.
    asignar(4, 2, "CC", "teoria", "1-15")
    asignar(4, 2, "CC", "practica", "1-15")

    asignar(4, 2, "EB", "teoria", "1-5")
    asignar(4, 2, "EB", "practica", "6-15")

    asignar(4, 2, "MSFADE", "teoria", "1-5")
    asignar(4, 2, "MSFADE", "practica", "6-15")

    asignar(4, 2, "RC", "teoria", "1-5")
    asignar(4, 2, "RC", "practica", "6-15")

    return mapa


SEMANAS_POR_SESION = crear_mapa_semanas()


# =========================================================
# LECTURA DE CSV
# =========================================================

def leer_csv(ruta):
    """Lee un CSV probando varias codificaciones habituales."""

    codificaciones = [
        "utf-8-sig",
        "utf-8",
        "latin-1",
        "cp1252",
    ]

    ultimo_error = None

    for codificacion in codificaciones:
        try:
            return pd.read_csv(
                ruta,
                encoding=codificacion,
                sep=",",
            )
        except UnicodeDecodeError as error:
            ultimo_error = error

    raise ValueError(
        f"No se pudo leer el archivo {ruta.name}: {ultimo_error}"
    )


# =========================================================
# IDENTIFICACIÓN DE CURSO Y CUATRIMESTRE
# =========================================================

def obtener_curso_cuatrimestre(id_sesion):
    """
    Obtiene curso y cuatrimestre del identificador.

    Ejemplo:
    C3Q1_01 -> curso 3, cuatrimestre 1.
    """

    coincidencia = re.match(
        r"^C([1-4])Q([1-2])_",
        str(id_sesion).strip().upper(),
    )

    if not coincidencia:
        raise ValueError(
            f"Identificador de sesión no válido: {id_sesion}"
        )

    return (
        int(coincidencia.group(1)),
        int(coincidencia.group(2)),
    )


# =========================================================
# VALIDACIÓN DE SEMANAS
# =========================================================

def expandir_semanas(valor):
    """Convierte '1-5,8,10-15' en una lista de semanas."""

    resultado = set()

    for parte in str(valor).split(","):
        parte = parte.strip()

        if not parte:
            continue

        if "-" in parte:
            inicio, fin = parte.split("-", maxsplit=1)

            inicio = int(inicio)
            fin = int(fin)

            if inicio > fin:
                raise ValueError(
                    f"Rango de semanas incorrecto: {parte}"
                )

            resultado.update(range(inicio, fin + 1))

        else:
            resultado.add(int(parte))

    return sorted(resultado)


def validar_semanas(valor, id_sesion):
    """Comprueba que las semanas estén entre 1 y 15."""

    semanas = expandir_semanas(valor)

    if not semanas:
        raise ValueError(
            f"La sesión {id_sesion} no tiene semanas."
        )

    if min(semanas) < 1 or max(semanas) > TOTAL_SEMANAS:
        raise ValueError(
            f"Semanas fuera del intervalo 1-{TOTAL_SEMANAS} "
            f"en la sesión {id_sesion}: {valor}"
        )

    return semanas


# =========================================================
# PROCESAMIENTO DE CADA ARCHIVO
# =========================================================

def procesar_archivo(nombre_archivo):
    """Procesa un CSV original y devuelve sus sesiones normalizadas."""

    ruta = CARPETA_ORIGINALES / nombre_archivo

    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encuentra el archivo: {ruta}"
        )

    df = leer_csv(ruta)
    df = limpiar_columnas(df)

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

    faltantes = [
        columna
        for columna in columnas_obligatorias
        if columna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"{nombre_archivo}: faltan columnas {faltantes}"
        )

    df = df[columnas_obligatorias].copy()

    # Elimina espacios en campos de texto.
    for columna in [
        "id_sesion",
        "asignatura",
        "tipo",
        "grupo",
        "tipo_aula_requerida",
        "profesor",
    ]:
        df[columna] = df[columna].fillna("").astype(str).str.strip()

    # Comprueba identificadores.
    if (df["id_sesion"] == "").any():
        raise ValueError(
            f"Hay identificadores vacíos en {nombre_archivo}"
        )

    if df["id_sesion"].duplicated().any():
        duplicados = df.loc[
            df["id_sesion"].duplicated(),
            "id_sesion",
        ].tolist()

        raise ValueError(
            f"Identificadores duplicados en {nombre_archivo}: "
            f"{duplicados}"
        )

    # Normaliza asignaturas.
    df["asignatura"] = df["asignatura"].apply(
        normalizar_asignatura
    )

    # Normaliza tipos.
    df["tipo"] = df["tipo"].apply(normalizar_tipo)

    # Comprueba duraciones y alumnado.
    df["duracion_horas"] = pd.to_numeric(
        df["duracion_horas"],
        errors="coerce",
    )

    df["num_alumnos"] = pd.to_numeric(
        df["num_alumnos"],
        errors="coerce",
    )

    if df["duracion_horas"].isna().any():
        raise ValueError(
            f"Hay duraciones no numéricas en {nombre_archivo}"
        )

    if (df["duracion_horas"] <= 0).any():
        raise ValueError(
            f"Hay duraciones menores o iguales a cero "
            f"en {nombre_archivo}"
        )

    if (df["duracion_horas"] % 1 != 0).any():
        raise ValueError(
            f"Hay duraciones no enteras en {nombre_archivo}"
        )

    if df["num_alumnos"].isna().any():
        raise ValueError(
            f"Hay valores de num_alumnos no válidos "
            f"en {nombre_archivo}"
        )

    # Curso y cuatrimestre se obtienen del identificador.
    # Esto corrige automáticamente los C3Q1 que aparecían
    # erróneamente como cuatrimestre 2 en el CSV original.
    cursos = []
    cuatrimestres = []

    for id_sesion in df["id_sesion"]:
        curso, cuatrimestre = obtener_curso_cuatrimestre(
            id_sesion
        )

        cursos.append(curso)
        cuatrimestres.append(cuatrimestre)

    df["curso"] = cursos
    df["cuatrimestre"] = cuatrimestres

    # Asignación de semanas.
    semanas_asignadas = []

    for _, fila in df.iterrows():

        clave = (
            int(fila["curso"]),
            int(fila["cuatrimestre"]),
            normalizar_asignatura(fila["asignatura"]),
            normalizar_tipo(fila["tipo"]),
        )

        semanas = SEMANAS_POR_SESION.get(clave)

        if semanas is None:
            raise ValueError(
                "\nNo existe una asignación de semanas para:\n"
                f"  ID: {fila['id_sesion']}\n"
                f"  Asignatura: {fila['asignatura']}\n"
                f"  Tipo: {fila['tipo']}\n"
                f"  Curso: {fila['curso']}\n"
                f"  Cuatrimestre: {fila['cuatrimestre']}\n"
                "Añade esta combinación al mapa de semanas."
            )

        validar_semanas(semanas, fila["id_sesion"])
        semanas_asignadas.append(semanas)

    df["semanas"] = semanas_asignadas

    return df


# =========================================================
# UNIFICACIÓN
# =========================================================

def unificar_clases():
    print("\n" + "=" * 65)
    print("UNIFICACIÓN DE LOS HORARIOS")
    print("=" * 65)

    dataframes = []

    for nombre_archivo in ARCHIVOS_ORIGINALES:

        print(f"\nProcesando: {nombre_archivo}")

        df = procesar_archivo(nombre_archivo)

        print(
            f"Curso: {df['curso'].iloc[0]}º GIFM"
            if not df.empty else "Archivo vacío"
        )

        if not df.empty:
            print(
                f"Cuatrimestre: {df['cuatrimestre'].iloc[0]}º"
            )

        print(f"Sesiones procesadas: {len(df)}")

        dataframes.append(df)

    resultado = pd.concat(
        dataframes,
        ignore_index=True,
    )

    # Comprueba identificadores globales.
    if resultado["id_sesion"].duplicated().any():
        duplicados = resultado.loc[
            resultado["id_sesion"].duplicated(),
            "id_sesion",
        ].tolist()

        raise ValueError(
            f"Hay identificadores repetidos entre archivos: "
            f"{duplicados}"
        )

    # Comprueba que todas las sesiones tienen semanas.
    if resultado["semanas"].isna().any():
        raise ValueError(
            "Hay sesiones sin semanas asignadas."
        )

    # Orden de columnas.
    columnas_salida = [
        "id_sesion",
        "asignatura",
        "tipo",
        "grupo",
        "duracion_horas",
        "num_alumnos",
        "tipo_aula_requerida",
        "profesor",
        "curso",
        "cuatrimestre",
        "semanas",
    ]

    resultado = resultado[columnas_salida]

    # Ordena por curso, cuatrimestre e identificador.
    resultado = resultado.sort_values(
        by=[
            "curso",
            "cuatrimestre",
            "id_sesion",
        ]
    ).reset_index(drop=True)

    # Crea carpeta de salida si no existe.
    ARCHIVO_SALIDA.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    resultado.to_csv(
        ARCHIVO_SALIDA,
        index=False,
        encoding="utf-8-sig",
    )

    # -----------------------------------------------------
    # RESUMEN
    # -----------------------------------------------------

    print("\n" + "=" * 65)
    print("RESUMEN DE LA UNIFICACIÓN")
    print("=" * 65)

    print(f"\nTotal de sesiones: {len(resultado)}")

    print(
        "Identificadores únicos: "
        f"{resultado['id_sesion'].nunique()}"
    )

    print(
        "Sesiones con semanas asignadas: "
        f"{resultado['semanas'].notna().sum()}"
    )

    print(
        "Sesiones sin semanas asignadas: "
        f"{resultado['semanas'].isna().sum()}"
    )

    print("\nSesiones por curso y cuatrimestre:")

    print(
        resultado.groupby(
            ["curso", "cuatrimestre"]
        ).size()
    )

    print("\nHoras semanales por curso y cuatrimestre:")

    print(
        resultado.groupby(
            ["curso", "cuatrimestre"]
        )["duracion_horas"].sum()
    )

    print("\nSemanas asignadas por sesión:")

    print(
        resultado[
            ["id_sesion", "asignatura", "tipo", "semanas"]
        ].to_string(index=False)
    )

    print("\nCSV generado:")
    print(ARCHIVO_SALIDA)

    print("\n" + "=" * 65)
    print("UNIFICACIÓN COMPLETADA CORRECTAMENTE")
    print("=" * 65)

    return resultado


# =========================================================
# EJECUCIÓN
# =========================================================

if __name__ == "__main__":
    unificar_clases()
