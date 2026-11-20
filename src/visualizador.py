
import os
import sys
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd


def exportar_horario_png(
    df_resultado,
    ruta_salida="horario_1GIFM_1er.png",
    abrir_al_terminar=True,
    titulo="CALENDARIO ACADÉMICO — 1º GIFM (1er SEMESTRE)"
):
    """
    Exporta el horario a una imagen PNG de alta resolución,
    diferenciando por colores teoría y práctica, y puede abrirlo
    automáticamente al terminar.
    """

    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]

    horas = [
        "08:30-09:30",
        "09:30-10:30",
        "10:30-11:30",
        "11:30-12:30",
        "12:30-13:30",
        "13:30-14:30"
    ]

    # 1. Estilo visual: teoría y práctica
    estilo_tipo = {
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

    # 2. Preparar la figura
    fig, ax = plt.subplots(figsize=(15, 9), dpi=300)

    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    x_offset = 1.8
    col_width = 2.4
    y_offset = 0.5
    row_height = 1.1

    # 3. Cabecera superior: días
    for j, dia in enumerate(dias):
        x = x_offset + j * col_width

        header_box = patches.FancyBboxPatch(
            (
                x + 0.05,
                len(horas) * row_height + y_offset + 0.1
            ),
            col_width - 0.1,
            0.55,
            boxstyle="round,pad=0.03,rounding_size=0.1",
            facecolor="#1A237E",
            edgecolor="none"
        )

        ax.add_patch(header_box)

        ax.text(
            x + col_width / 2,
            len(horas) * row_height + y_offset + 0.38,
            dia.upper(),
            ha="center",
            va="center",
            color="white",
            fontsize=11.5,
            fontweight="bold"
        )

    # 4. Cabecera lateral: horas
    for i, hora in enumerate(horas):
        y = (len(horas) - 1 - i) * row_height + y_offset

        time_box = patches.FancyBboxPatch(
            (0.2, y + 0.05),
            x_offset - 0.3,
            row_height - 0.1,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#E8EAF6",
            edgecolor="#C5CAE9",
            linewidth=1.2
        )

        ax.add_patch(time_box)

        ax.text(
            0.2 + (x_offset - 0.3) / 2,
            y + row_height / 2,
            hora,
            ha="center",
            va="center",
            color="#283593",
            fontsize=9.5,
            fontweight="bold"
        )

    # 5. Cuadrícula de fondo
    for j in range(len(dias)):
        for i in range(len(horas)):
            x = x_offset + j * col_width
            y = (len(horas) - 1 - i) * row_height + y_offset

            bg_slot = patches.FancyBboxPatch(
                (x + 0.04, y + 0.04),
                col_width - 0.08,
                row_height - 0.08,
                boxstyle="round,pad=0.02,rounding_size=0.06",
                facecolor="#FFFFFF",
                edgecolor="#E0E0E0",
                linewidth=0.8,
                linestyle=":"
            )

            ax.add_patch(bg_slot)

    # 6. Contar sesiones que empiezan el mismo día y a la misma hora
    dia_hora_count = {}

    for _, row in df_resultado.iterrows():
        d = row["Dia"]
        h = row["Hora"]

        dia_hora_count[(d, h)] = (
            dia_hora_count.get((d, h), 0) + 1
        )

    dia_hora_tracker = {}

    # 7. Dibujar las sesiones
    for _, row in df_resultado.iterrows():
        dia = row["Dia"]
        hora_str = row["Hora"]

        duracion = int(
            str(row["Duracion"]).replace("h", "")
        )

        asig = row["Asignatura"]

        es_teoria = "teor" in str(row["Tipo"]).lower()

        tipo_clave = "teoria" if es_teoria else "practica"
        tipo_tag = "T" if es_teoria else "P"

        grupo = f"G{row['Grupo']}"
        aula = row["Aula"]

        if dia not in dias:
            print(
                f"AVISO: Día no reconocido en una sesión: {dia}"
            )
            continue

        if hora_str not in horas:
            print(
                f"AVISO: Hora de inicio no reconocida: {hora_str}"
            )
            continue

        col_idx = dias.index(dia)
        row_idx = horas.index(hora_str)

        total_en_slot = dia_hora_count.get(
            (dia, hora_str), 1
        )

        sub_idx = dia_hora_tracker.get(
            (dia, hora_str), 0
        )

        dia_hora_tracker[(dia, hora_str)] = sub_idx + 1

        w_box = (col_width - 0.1) / total_en_slot

        x_box = (
            x_offset
            + col_idx * col_width
            + 0.05
            + sub_idx * w_box
        )

        h_box = duracion * row_height - 0.1

        y_box = (
            (len(horas) - row_idx - duracion)
            * row_height
            + y_offset
            + 0.05
        )

        estilo = estilo_tipo[tipo_clave]

        tarjeta = patches.FancyBboxPatch(
            (x_box + 0.02, y_box + 0.02),
            w_box - 0.04,
            h_box - 0.04,
            boxstyle="round,pad=0.03,rounding_size=0.1",
            facecolor=estilo["bg"],
            edgecolor=estilo["border"],
            linewidth=1.8
        )

        ax.add_patch(tarjeta)

        cx = x_box + w_box / 2
        cy = y_box + h_box / 2

        ax.text(
            cx,
            cy + (0.18 if duracion > 1 else 0.10),
            f"{asig} ({tipo_tag}-{grupo})",
            ha="center",
            va="center",
            color=estilo["text"],
            fontsize=10.5 if total_en_slot == 1 else 8.5,
            fontweight="bold",
            wrap=True
        )

        ax.text(
            cx,
            cy - (0.12 if duracion > 1 else 0.10),
            f"Aula: {aula}",
            ha="center",
            va="center",
            color="#37474F",
            fontsize=9 if total_en_slot == 1 else 7.5,
            fontweight="bold"
        )

    # 8. Leyenda
    leyenda_y = len(horas) * row_height + y_offset + 0.82

    box_t = patches.FancyBboxPatch(
        (
            x_offset + 3.0 * col_width,
            leyenda_y
        ),
        1.25,
        0.38,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=estilo_tipo["teoria"]["bg"],
        edgecolor=estilo_tipo["teoria"]["border"],
        linewidth=1.6
    )

    ax.add_patch(box_t)

    ax.text(
        x_offset + 3.0 * col_width + 0.625,
        leyenda_y + 0.19,
        "TEORÍA",
        ha="center",
        va="center",
        color=estilo_tipo["teoria"]["text"],
        fontsize=9.5,
        fontweight="bold"
    )

    box_p = patches.FancyBboxPatch(
        (
            x_offset + 3.7 * col_width,
            leyenda_y
        ),
        1.35,
        0.38,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=estilo_tipo["practica"]["bg"],
        edgecolor=estilo_tipo["practica"]["border"],
        linewidth=1.6
    )

    ax.add_patch(box_p)

    ax.text(
        x_offset + 3.7 * col_width + 0.675,
        leyenda_y + 0.19,
        "PRÁCTICA",
        ha="center",
        va="center",
        color=estilo_tipo["practica"]["text"],
        fontsize=9.5,
        fontweight="bold"
    )

    # 9. Ajustar los límites y ocultar los ejes
    ax.set_xlim(
        0,
        x_offset + len(dias) * col_width + 0.3
    )

    ax.set_ylim(
        0,
        len(horas) * row_height + y_offset + 1.4
    )

    ax.axis("off")

    # 10. Título dinámico según el curso y cuatrimestre
    ax.set_title(
        titulo,
        fontsize=16,
        fontweight="bold",
        pad=25,
        color="#1A237E"
    )

    plt.tight_layout()

    # 11. Guardar el PNG, creando antes la carpeta si hace falta
    ruta = Path(ruta_salida).resolve()
    ruta.parent.mkdir(parents=True, exist_ok=True)

    try:
        fig.savefig(
            ruta,
            dpi=300,
            bbox_inches="tight"
        )
        print(f"\nImagen guardada con éxito en: {ruta}")

    finally:
        plt.close(fig)

    # 12. Abrir automáticamente la imagen generada
    if abrir_al_terminar:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(ruta))
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", str(ruta)], check=False)
            else:
                subprocess.run(["xdg-open", str(ruta)], check=False)

        except Exception as e:
            print(
                f"No se pudo abrir automáticamente la imagen: {e}"
            )
