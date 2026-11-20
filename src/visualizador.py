
import os
import re
import sys
import subprocess
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd


DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

HORAS = [
    f"{hora:02d}:30-{hora + 1:02d}:30"
    for hora in range(8, 20)
]

HORAS_POR_DIA = 12

ESTILO_TIPO = {
    "teoria": {
        "bg": "#FFF9C4",
        "border": "#FBC02D",
        "text": "#E65100"
    },
    "practica": {
        "bg": "#C8E6C9",
        "border": "#43A047",
        "text": "#1B5E20"
    }
}


def normalizar_texto(valor):
    """Normaliza textos para comparar días y tipos sin tildes."""
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(
        caracter for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def obtener_duracion(row):
    """Obtiene la duración del bloque en horas."""
    if "Duracion_horas" in row.index and pd.notna(row["Duracion_horas"]):
        return int(float(row["Duracion_horas"]))

    valor = row.get("Duracion", 1)

    if pd.isna(valor):
        return 1

    coincidencia = re.search(r"\d+", str(valor))

    if coincidencia:
        return int(coincidencia.group())

    return 1


def obtener_posicion(row):
    """
    Obtiene el día y la hora de inicio.
    Prioriza Slot, que representa la posición absoluta de la semana.
    """
    if "Slot" in row.index and pd.notna(row["Slot"]):
        slot = int(float(row["Slot"]))

        dia_idx = slot // HORAS_POR_DIA
        hora_idx = slot % HORAS_POR_DIA

        if 0 <= dia_idx < len(DIAS):
            return dia_idx, hora_idx

    # Alternativa: calcular la posición usando Dia y Hora.
    dia_texto = normalizar_texto(row.get("Dia", ""))

    nombres_dias = [
        normalizar_texto(dia) for dia in DIAS
    ]

    if dia_texto not in nombres_dias:
        return None, None

    dia_idx = nombres_dias.index(dia_texto)

    hora_texto = str(row.get("Hora", ""))

    coincidencia = re.search(r"(\d{1,2}):(\d{2})", hora_texto)

    if not coincidencia:
        return None, None

    hora = int(coincidencia.group(1))
    minutos = int(coincidencia.group(2))

    hora_idx = hora - 8

    if minutos > 30:
        hora_idx += 1

    if not 0 <= hora_idx < HORAS_POR_DIA:
        return None, None

    return dia_idx, hora_idx


def obtener_semanas(row):
    """Devuelve las semanas activas o indica que están pendientes."""
    valor = row.get("Semanas_activas", "")

    if pd.isna(valor) or not str(valor).strip():
        return "Semanas pendientes"

    return f"Semanas: {str(valor).strip()}"


def preparar_sesiones(df_resultado):
    """Prepara las sesiones y calcula sus posiciones en la cuadrícula."""
    sesiones = []

    for _, row in df_resultado.iterrows():
        dia_idx, hora_idx = obtener_posicion(row)

        if dia_idx is None or hora_idx is None:
            print(
                "AVISO: No se pudo interpretar la posición de esta sesión:",
                row.get("Asignatura", "Sin asignatura")
            )
            continue

        duracion = obtener_duracion(row)

        if duracion <= 0:
            continue

        if hora_idx + duracion > HORAS_POR_DIA:
            print(
                "AVISO: Una sesión supera el horario del día:",
                row.get("Asignatura", "Sin asignatura")
            )
            continue

        tipo = normalizar_texto(row.get("Tipo", ""))

        tipo_clave = (
            "teoria" if "teor" in tipo else "practica"
        )

        sesiones.append({
            "dia": dia_idx,
            "inicio": hora_idx,
            "fin": hora_idx + duracion,
            "duracion": duracion,
            "asignatura": str(row.get("Asignatura", "")),
            "tipo": tipo_clave,
            "grupo": str(row.get("Grupo", "")),
            "aula": str(row.get("Aula", "")),
            "semanas": obtener_semanas(row),
            "profesor": str(row.get("Profesor", "")),
            "lane": 0
        })

    return sesiones


def asignar_columnas_sesiones(sesiones):
    """
    Distribuye horizontalmente las sesiones que coinciden en horario.
    Así pueden visualizarse actividades de semanas diferentes
    que reutilizan el mismo día y hora.
    """
    max_lanes_por_dia = {}

    for dia_idx in range(len(DIAS)):
        sesiones_dia = [
            sesion for sesion in sesiones
            if sesion["dia"] == dia_idx
        ]

        sesiones_dia.sort(
            key=lambda s: (s["inicio"], s["fin"])
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
                finales_lanes.append(sesion["fin"])
            else:
                finales_lanes[lane_asignado] = sesion["fin"]

            sesion["lane"] = lane_asignado

        max_lanes_por_dia[dia_idx] = max(
            1, len(finales_lanes)
        )

    return max_lanes_por_dia


def exportar_horario_png(
    df_resultado,
    ruta_salida="horario.png",
    abrir_al_terminar=True,
    titulo="CALENDARIO ACADÉMICO"
):
    """
    Exporta el horario semanal a PNG.

    - 5 días, de lunes a viernes.
    - 12 franjas horarias, de 08:30 a 20:30.
    - Bloques de 1 o 2 horas.
    - Diferenciación visual entre teoría y práctica.
    - Muestra las semanas activas de cada actividad.
    - Permite visualizar actividades coincidentes en semanas distintas.
    """

    if df_resultado is None or df_resultado.empty:
        print("No hay sesiones para representar.")
        return

    sesiones = preparar_sesiones(df_resultado)

    if not sesiones:
        print("No se encontraron sesiones con posiciones válidas.")
        return

    max_lanes = asignar_columnas_sesiones(sesiones)

    # Crear figura.
    fig, ax = plt.subplots(figsize=(19, 14), dpi=200)

    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    # Cuadrícula de fondo.
    for dia_idx in range(len(DIAS)):
        for hora_idx in range(HORAS_POR_DIA):
            fondo = patches.FancyBboxPatch(
                (dia_idx + 0.015, hora_idx + 0.015),
                0.97,
                0.97,
                boxstyle="round,pad=0.01,rounding_size=0.025",
                facecolor="#FFFFFF",
                edgecolor="#E0E0E0",
                linewidth=0.8
            )

            ax.add_patch(fondo)

    # Etiquetas de días.
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

    # Etiquetas horarias.
    for hora_idx, hora in enumerate(HORAS):
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

    # Dibujar las sesiones.
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
            boxstyle="round,pad=0.015,rounding_size=0.04",
            facecolor=estilo["bg"],
            edgecolor=estilo["border"],
            linewidth=1.5
        )

        ax.add_patch(tarjeta)

        tipo_tag = (
            "TEORÍA"
            if sesion["tipo"] == "teoria"
            else "PRÁCTICA"
        )

        grupo = sesion["grupo"]

        if grupo and grupo.lower() != "nan":
            grupo_texto = f"Grupo {grupo}"
        else:
            grupo_texto = ""

        aula = sesion["aula"]

        if aula.lower() == "nan":
            aula = "Sin asignar"

        # Información de la tarjeta.
        lineas = [
            sesion["asignatura"],
            f"{tipo_tag} {grupo_texto}".strip(),
            f"Aula: {aula}",
            sesion["semanas"]
        ]

        texto = "\n".join(lineas)

        # Adaptar tamaño del texto al espacio disponible.
        if total_lanes >= 4:
            tamano = 5.0
        elif total_lanes == 3:
            tamano = 5.8
        elif total_lanes == 2:
            tamano = 6.8
        elif duracion == 1:
            tamano = 6.8
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

    # Leyenda.
    elementos_leyenda = [
        patches.Patch(
            facecolor=ESTILO_TIPO["teoria"]["bg"],
            edgecolor=ESTILO_TIPO["teoria"]["border"],
            label="TEORÍA"
        ),
        patches.Patch(
            facecolor=ESTILO_TIPO["practica"]["bg"],
            edgecolor=ESTILO_TIPO["practica"]["border"],
            label="PRÁCTICA"
        )
    ]

    ax.legend(
        handles=elementos_leyenda,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.035),
        ncol=2,
        frameon=False,
        fontsize=10
    )

    # Límites y formato.
    ax.set_xlim(-0.85, 5)
    ax.set_ylim(12.3, -0.85)
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

    # Guardar imagen.
    ruta = Path(ruta_salida).resolve()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    try:
        fig.savefig(
            str(ruta),
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor=fig.get_facecolor()
        )

        print(f"\nImagen guardada con éxito en: {ruta}")

    finally:
        plt.close(fig)

    # Abrir imagen automáticamente si se solicita.
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

        except Exception as e:
            print(
                f"No se pudo abrir automáticamente la imagen: {e}"
            )