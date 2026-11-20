
import os
import re
import sys
import subprocess
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd


# =========================================================
# CONFIGURACIÓN
# =========================================================

DIAS = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes"
]

HORA_INICIO = 8

# Jornada ordinaria: 08:30-14:30.
HORAS_POR_DIA = 6


# =========================================================
# ESTILOS
# =========================================================

ESTILO_TIPO = {

    "teoria": {
        "bg": "#FFF9C4",
        "border": "#FBC02D",
        "text": "#E65100",
        "etiqueta": "TEORÍA"
    },

    "practica_aula": {
        "bg": "#C8E6C9",
        "border": "#43A047",
        "text": "#1B5E20",
        "etiqueta": "PRÁCTICA AULA"
    },

    "laboratorio": {
        "bg": "#BBDEFB",
        "border": "#1976D2",
        "text": "#0D47A1",
        "etiqueta": "LABORATORIO"
    },

    "practica": {
        "bg": "#D1C4E9",
        "border": "#7E57C2",
        "text": "#4527A0",
        "etiqueta": "PRÁCTICA"
    }
}


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def normalizar_texto(valor):
    """Normaliza textos para comparar sin distinguir tildes."""

    if pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()

    texto = unicodedata.normalize("NFD", texto)

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def limpiar_valor(valor, predeterminado=""):
    """Evita representar valores NaN como texto."""

    if pd.isna(valor):
        return predeterminado

    texto = str(valor).strip()

    if texto.lower() in ("nan", "none", "null"):
        return predeterminado

    return texto


def obtener_duracion(row):
    """Obtiene la duración del bloque en horas."""

    if (
        "Duracion_horas" in row.index
        and pd.notna(row["Duracion_horas"])
    ):

        valor = float(row["Duracion_horas"])

    else:

        valor = row.get("Duracion", 1)

        if pd.isna(valor):
            return 1

        coincidencia = re.search(
            r"\d+(?:[.,]\d+)?",
            str(valor)
        )

        if not coincidencia:
            return 1

        valor = float(
            coincidencia.group().replace(",", ".")
        )

    if valor <= 0 or not valor.is_integer():
        raise ValueError(
            f"Duración no válida: {valor}"
        )

    return int(valor)


def obtener_tipo(row):
    """Identifica el tipo de actividad."""

    tipo = normalizar_texto(
        row.get("Tipo", "")
    )

    if "teor" in tipo:
        return "teoria"

    if "laboratorio" in tipo or "lab" in tipo:
        return "laboratorio"

    if "aula" in tipo:
        return "practica_aula"

    if "pract" in tipo:
        return "practica"

    return "practica"


def obtener_semanas(row):
    """Devuelve las semanas activas."""

    valor = row.get("Semanas_activas", "")

    if pd.isna(valor) or not str(valor).strip():
        return "Semanas pendientes"

    return f"Semanas: {str(valor).strip()}"


def obtener_posicion(
    row,
    horas_por_dia=6,
    hora_inicio=8
):
    """
    Obtiene el día y la hora de inicio.

    Prioriza Slot, que representa la posición absoluta
    de la semana.

    Si no existe Slot, utiliza Dia y Hora.
    """

    if "Slot" in row.index and pd.notna(row["Slot"]):

        slot = int(float(row["Slot"]))

        dia_idx = slot // horas_por_dia
        hora_idx = slot % horas_por_dia

        if 0 <= dia_idx < len(DIAS):
            return dia_idx, hora_idx

        raise ValueError(
            f"Slot fuera del horario semanal: {slot}"
        )

    # Alternativa: utilizar las columnas Dia y Hora.

    dia_texto = normalizar_texto(
        row.get("Dia", "")
    )

    nombres_dias = [
        normalizar_texto(dia)
        for dia in DIAS
    ]

    if dia_texto not in nombres_dias:
        raise ValueError(
            f"Día no reconocido: {dia_texto}"
        )

    dia_idx = nombres_dias.index(dia_texto)

    hora_texto = limpiar_valor(
        row.get("Hora", "")
    )

    coincidencia = re.search(
        r"(\d{1,2}):(\d{2})",
        hora_texto
    )

    if not coincidencia:
        raise ValueError(
            f"Hora no reconocida: {hora_texto}"
        )

    hora = int(coincidencia.group(1))
    minutos = int(coincidencia.group(2))

    minutos_desde_inicio = (
        (hora - hora_inicio) * 60
        + minutos - 30
    )

    if minutos_desde_inicio < 0 or minutos_desde_inicio % 60 != 0:
        raise ValueError(
            f"Hora incompatible con las franjas horarias: "
            f"{hora_texto}"
        )

    hora_idx = minutos_desde_inicio // 60

    if not 0 <= hora_idx < horas_por_dia:
        raise ValueError(
            f"Hora fuera de la jornada: {hora_texto}"
        )

    return dia_idx, hora_idx


def obtener_etiqueta_hora(
    hora_idx,
    hora_inicio=8
):
    """Devuelve la etiqueta de una franja horaria."""

    inicio = hora_inicio + hora_idx

    return (
        f"{inicio:02d}:30-"
        f"{inicio + 1:02d}:30"
    )


# =========================================================
# PREPARACIÓN DE SESIONES
# =========================================================

def preparar_sesiones(
    df_resultado,
    horas_por_dia=6,
    hora_inicio=8
):
    """
    Prepara las sesiones para dibujarlas.

    Comprueba que cada sesión se encuentra dentro
    de la jornada y no atraviesa el final del día.
    """

    sesiones = []

    for indice, row in df_resultado.iterrows():

        dia_idx, hora_idx = obtener_posicion(
            row,
            horas_por_dia,
            hora_inicio
        )

        duracion = obtener_duracion(row)

        if hora_idx + duracion > horas_por_dia:

            raise ValueError(
                f"La sesión {row.get('Sesion', indice)} "
                "supera el horario del día."
            )

        tipo = obtener_tipo(row)

        sesiones.append({

            "dia": dia_idx,

            "inicio": hora_idx,

            "fin": hora_idx + duracion,

            "duracion": duracion,

            "asignatura": limpiar_valor(
                row.get("Asignatura", ""),
                "Sin asignatura"
            ),

            "tipo": tipo,

            "grupo": limpiar_valor(
                row.get("Grupo", "")
            ),

            "aula": limpiar_valor(
                row.get("Aula", ""),
                "Sin asignar"
            ),

            "semanas": obtener_semanas(row),

            "profesor": limpiar_valor(
                row.get("Profesor", "")
            ),

            "lane": 0
        })

    return sesiones


# =========================================================
# DISTRIBUCIÓN DE COLUMNAS
# =========================================================

def asignar_columnas_sesiones(sesiones):
    """
    Distribuye horizontalmente las sesiones que coinciden
    en horario.

    Esto permite visualizar actividades que se realizan
    en semanas diferentes y reutilizan la misma franja.
    """

    max_lanes_por_dia = {}

    for dia_idx in range(len(DIAS)):

        sesiones_dia = [
            sesion
            for sesion in sesiones
            if sesion["dia"] == dia_idx
        ]

        sesiones_dia.sort(
            key=lambda sesion: (
                sesion["inicio"],
                sesion["fin"]
            )
        )

        finales_lanes = []

        for sesion in sesiones_dia:

            lane_asignado = None

            for lane, hora_final in enumerate(finales_lanes):

                if hora_final <= sesion["inicio"]:

                    lane_asignado = lane
                    break

            if lane_asignado is None:

                lane_asignado = len(finales_lanes)

                finales_lanes.append(
                    sesion["fin"]
                )

            else:

                finales_lanes[lane_asignado] = (
                    sesion["fin"]
                )

            sesion["lane"] = lane_asignado

        max_lanes_por_dia[dia_idx] = max(
            1,
            len(finales_lanes)
        )

    return max_lanes_por_dia


# =========================================================
# EXPORTACIÓN PNG
# =========================================================

def exportar_horario_png(
    df_resultado,
    ruta_salida="horario.png",
    abrir_al_terminar=True,
    titulo="CALENDARIO ACADÉMICO",
    horas_por_dia=6,
    hora_inicio=8
):
    """
    Exporta el horario semanal a PNG.

    Parámetros:
        df_resultado:
            DataFrame con las sesiones generadas.

        ruta_salida:
            Ruta donde se guardará el PNG.

        abrir_al_terminar:
            Abre automáticamente la imagen.

        titulo:
            Título del horario.

        horas_por_dia:
            Número de horas lectivas diarias.
            Por defecto, 6.

        hora_inicio:
            Hora de inicio de la jornada.
            Por defecto, 8 (08:30).
    """

    if df_resultado is None or df_resultado.empty:

        print(
            "No hay sesiones para representar."
        )

        return None

    if horas_por_dia <= 0:

        raise ValueError(
            "La jornada debe tener al menos una hora."
        )

    sesiones = preparar_sesiones(
        df_resultado,
        horas_por_dia,
        hora_inicio
    )

    if not sesiones:

        print(
            "No se encontraron sesiones con posiciones válidas."
        )

        return None

    max_lanes = asignar_columnas_sesiones(
        sesiones
    )

    # -----------------------------------------------------
    # CREAR FIGURA
    # -----------------------------------------------------

    altura_figura = max(
        10,
        horas_por_dia * 1.6 + 3
    )

    fig, ax = plt.subplots(
        figsize=(19, altura_figura),
        dpi=200
    )

    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    # -----------------------------------------------------
    # CUADRÍCULA DE FONDO
    # -----------------------------------------------------

    for dia_idx in range(len(DIAS)):

        for hora_idx in range(horas_por_dia):

            fondo = patches.FancyBboxPatch(

                (dia_idx + 0.015, hora_idx + 0.015),

                0.97,

                0.97,

                boxstyle=(
                    "round,pad=0.01,"
                    "rounding_size=0.025"
                ),

                facecolor="#FFFFFF",

                edgecolor="#E0E0E0",

                linewidth=0.8
            )

            ax.add_patch(fondo)

    # -----------------------------------------------------
    # ETIQUETAS DE DÍAS
    # -----------------------------------------------------

    for dia_idx, dia in enumerate(DIAS):

        ax.text(

            dia_idx + 0.5,

            -0.45,

            dia.upper(),

            ha="center",

            va="center",

            fontsize=11,

            fontweight="bold",

            color="#1A237E"
        )

    # -----------------------------------------------------
    # ETIQUETAS HORARIAS
    # -----------------------------------------------------

    for hora_idx in range(horas_por_dia):

        hora = obtener_etiqueta_hora(
            hora_idx,
            hora_inicio
        )

        ax.text(

            -0.08,

            hora_idx + 0.5,

            hora,

            ha="right",

            va="center",

            fontsize=8.5,

            fontweight="bold",

            color="#283593"
        )

    # -----------------------------------------------------
    # DIBUJAR SESIONES
    # -----------------------------------------------------

    for sesion in sesiones:

        dia_idx = sesion["dia"]

        inicio = sesion["inicio"]

        duracion = sesion["duracion"]

        lane = sesion["lane"]

        total_lanes = max_lanes[dia_idx]

        ancho_dia = 0.97

        ancho_lane = ancho_dia / total_lanes

        x = (
            dia_idx
            + 0.015
            + lane * ancho_lane
        )

        y = inicio + 0.015

        ancho = ancho_lane - 0.015

        alto = duracion - 0.03

        estilo = ESTILO_TIPO[sesion["tipo"]]

        tarjeta = patches.FancyBboxPatch(

            (x, y),

            ancho,

            alto,

            boxstyle=(
                "round,pad=0.015,"
                "rounding_size=0.04"
            ),

            facecolor=estilo["bg"],

            edgecolor=estilo["border"],

            linewidth=1.5
        )

        ax.add_patch(tarjeta)

        grupo = sesion["grupo"]

        grupo_texto = (
            f"Grupo {grupo}"
            if grupo
            else ""
        )

        aula = sesion["aula"]

        profesor = sesion["profesor"]

        # Información de la tarjeta.
        lineas = [
            sesion["asignatura"],
            f"{estilo['etiqueta']} {grupo_texto}".strip(),
            f"Aula: {aula}",
            sesion["semanas"]
        ]

        if profesor:
            lineas.append(
                f"Prof.: {profesor}"
            )

        texto = "\n".join(lineas)

        # Adaptar el tamaño del texto.
        if total_lanes >= 4:

            tamano = 4.5

        elif total_lanes == 3:

            tamano = 5.3

        elif total_lanes == 2:

            tamano = 6.2

        elif duracion == 1:

            tamano = 6.5

        else:

            tamano = 8.0

        ax.text(

            x + ancho / 2,

            y + alto / 2,

            texto,

            ha="center",

            va="center",

            color=estilo["text"],

            fontsize=tamano,

            fontweight="bold",

            wrap=True,

            clip_on=True
        )

    # -----------------------------------------------------
    # LEYENDA
    # -----------------------------------------------------

    elementos_leyenda = []

    for clave, estilo in ESTILO_TIPO.items():

        elementos_leyenda.append(
            patches.Patch(
                facecolor=estilo["bg"],
                edgecolor=estilo["border"],
                label=estilo["etiqueta"]
            )
        )

    ax.legend(

        handles=elementos_leyenda,

        loc="upper center",

        bbox_to_anchor=(0.5, 1.035),

        ncol=4,

        frameon=False,

        fontsize=9
    )

    # -----------------------------------------------------
    # LÍMITES Y FORMATO
    # -----------------------------------------------------

    ax.set_xlim(
        -0.85,
        5
    )

    ax.set_ylim(
        horas_por_dia + 0.3,
        -0.85
    )

    ax.axis("off")

    fig.suptitle(

        titulo,

        fontsize=16,

        fontweight="bold",

        color="#1A237E",

        y=0.985
    )

    fig.subplots_adjust(

        left=0.09,

        right=0.99,

        top=0.91,

        bottom=0.04
    )

    # -----------------------------------------------------
    # GUARDAR IMAGEN
    # -----------------------------------------------------

    ruta = Path(ruta_salida).resolve()

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    try:

        fig.savefig(

            str(ruta),

            format="png",

            dpi=300,

            bbox_inches="tight",

            facecolor=fig.get_facecolor()
        )

        print(
            f"\nImagen guardada correctamente en: {ruta}"
        )

    finally:

        plt.close(fig)

    # -----------------------------------------------------
    # ABRIR IMAGEN
    # -----------------------------------------------------

    if abrir_al_terminar:

        try:

            if sys.platform.startswith("win"):

                os.startfile(str(ruta))

            elif sys.platform.startswith("darwin"):

                subprocess.run(
                    ["open", str(ruta)],
                    check=False
                )

            else:

                subprocess.run(
                    ["xdg-open", str(ruta)],
                    check=False
                )

        except Exception as error:

            print(
                "No se pudo abrir automáticamente "
                f"la imagen: {error}"
            )

    return ruta
