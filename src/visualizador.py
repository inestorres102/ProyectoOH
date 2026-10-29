import os
import sys
import subprocess
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

def exportar_horario_png(df_resultado, curso=1, cuatrimestre=1, ruta_salida=None, abrir_al_terminar=True):
    """
    Exporta el horario a PNG adaptando dinámicamente el ancho de las columnas
    según el número de grupos de prácticas existentes (41, 42, 43, 44...).
    """
    sufijo_cuatri = "1er" if cuatrimestre == 1 else "2do"
    if ruta_salida is None:
        ruta_salida = f"horario_{curso}GCID_{sufijo_cuatri}.png"

    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]

    estilo_tipo = {
        "teoria": {"bg": "#FFF9C4", "border": "#FBC02D", "text": "#E65100"},
        "practica": {"bg": "#C8E6C9", "border": "#43A047", "text": "#1B5E20"}
    }

    # Detectar dinámicamente qué grupos de prácticas existen en este horario
    grupos_teoria = ["17", "11", "18", "10"]
    subgrupos_prac = sorted([
        str(g).strip() for g in df_resultado["Grupo"].unique() 
        if str(g).strip() not in grupos_teoria
    ])
    
    num_carriles = max(len(subgrupos_prac), 1)
    lane_map = {grp: i for i, grp in enumerate(subgrupos_prac)}

    fig, ax = plt.subplots(figsize=(16, 9.5), dpi=300)
    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    x_offset = 1.8
    col_width = 2.5
    y_offset = 0.5
    row_height = 1.1

    # 1. Cabecera Días
    for j, dia in enumerate(dias):
        x = x_offset + j * col_width
        header_box = patches.FancyBboxPatch(
            (x + 0.05, len(horas) * row_height + y_offset + 0.1), col_width - 0.1, 0.55,
            boxstyle="round,pad=0.03,rounding_size=0.1",
            facecolor="#1A237E", edgecolor="none"
        )
        ax.add_patch(header_box)
        ax.text(x + col_width / 2, len(horas) * row_height + y_offset + 0.38, dia.upper(),
                ha="center", va="center", color="white", fontsize=11.5, fontweight="bold")

    # 2. Horas
    for i, hora in enumerate(horas):
        y = (len(horas) - 1 - i) * row_height + y_offset
        time_box = patches.FancyBboxPatch(
            (0.2, y + 0.05), x_offset - 0.3, row_height - 0.1,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#E8EAF6", edgecolor="#C5CAE9", linewidth=1.2
        )
        ax.add_patch(time_box)
        ax.text(0.2 + (x_offset - 0.3) / 2, y + row_height / 2, hora,
                ha="center", va="center", color="#283593", fontsize=9.5, fontweight="bold")

    # 3. Cuadrícula de fondo
    for j in range(len(dias)):
        for i in range(len(horas)):
            x = x_offset + j * col_width
            y = (len(horas) - 1 - i) * row_height + y_offset
            bg_slot = patches.FancyBboxPatch(
                (x + 0.04, y + 0.04), col_width - 0.08, row_height - 0.08,
                boxstyle="round,pad=0.02,rounding_size=0.06",
                facecolor="#FFFFFF", edgecolor="#E0E0E0", linewidth=0.8, linestyle=":"
            )
            ax.add_patch(bg_slot)

    # 4. Estructurar eventos
    eventos = []
    for _, row in df_resultado.iterrows():
        d = row["Dia"]
        h_str = row["Hora"]
        dur = int(str(row["Duracion"]).replace("h", ""))
        eventos.append({
            "dia_idx": dias.index(d),
            "start": horas.index(h_str),
            "end": horas.index(h_str) + dur,
            "dur": dur,
            "asig": row["Asignatura"],
            "tipo": "teoria" if "teor" in str(row["Tipo"]).lower() else "practica",
            "grupo": str(row["Grupo"]).strip(),
            "aula": row["Aula"]
        })

    # 5. Dibujar tarjetas
    for d_idx in range(len(dias)):
        eventos_dia = [e for e in eventos if e["dia_idx"] == d_idx]
        for ev in eventos_dia:
            if ev["tipo"] == "teoria":
                # Teoría ocupa todo el ancho de la columna
                w_box = col_width - 0.1
                x_box = x_offset + d_idx * col_width + 0.05
            else:
                # Cada subgrupo va a su carril correspondiente (0..num_carriles-1)
                w_box = (col_width - 0.1) / num_carriles
                sub_idx = lane_map.get(ev["grupo"], 0)
                x_box = x_offset + d_idx * col_width + 0.05 + sub_idx * w_box

            h_box = ev["dur"] * row_height - 0.1
            y_box = (len(horas) - ev["start"] - ev["dur"]) * row_height + y_offset + 0.05

            estilo = estilo_tipo[ev["tipo"]]
            tarjeta = patches.FancyBboxPatch(
                (x_box + 0.015, y_box + 0.02), w_box - 0.03, h_box - 0.04,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=estilo["bg"], edgecolor=estilo["border"], linewidth=1.5
            )
            ax.add_patch(tarjeta)

            cx = x_box + w_box / 2
            cy = y_box + h_box / 2
            tipo_tag = "T" if ev["tipo"] == "teoria" else "P"

            # Ajuste dinámico de tipografía según la anchura de la tarjeta
            if w_box > col_width * 0.7:
                font_title, font_sub = 10.5, 9.0
            elif w_box > col_width * 0.4:
                font_title, font_sub = 8.5, 7.5
            else:
                font_title, font_sub = 7.0, 6.0

            ax.text(cx, cy + (0.16 if ev["dur"] > 1 else 0.09), f"{ev['asig']}\n({tipo_tag}-G{ev['grupo']})",
                    ha="center", va="center", color=estilo["text"], fontsize=font_title, fontweight="bold")
            ax.text(cx, cy - (0.18 if ev["dur"] > 1 else 0.11), f"Aula:\n{ev['aula']}",
                    ha="center", va="center", color="#37474F", fontsize=font_sub, fontweight="bold")

    # 6. Leyenda
    leyenda_y = len(horas) * row_height + y_offset + 0.82
    box_t = patches.FancyBboxPatch((x_offset + 3.2 * col_width, leyenda_y), 1.25, 0.38,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=estilo_tipo["teoria"]["bg"], edgecolor=estilo_tipo["teoria"]["border"], linewidth=1.6)
    ax.add_patch(box_t)
    ax.text(x_offset + 3.2 * col_width + 0.625, leyenda_y + 0.19, "TEORÍA",
            ha="center", va="center", color=estilo_tipo["teoria"]["text"], fontsize=9.5, fontweight="bold")

    box_p = patches.FancyBboxPatch((x_offset + 3.8 * col_width, leyenda_y), 1.35, 0.38,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=estilo_tipo["practica"]["bg"], edgecolor=estilo_tipo["practica"]["border"], linewidth=1.6)
    ax.add_patch(box_p)
    ax.text(x_offset + 3.8 * col_width + 0.675, leyenda_y + 0.19, "PRÁCTICA",
            ha="center", va="center", color=estilo_tipo["practica"]["text"], fontsize=9.5, fontweight="bold")

    ax.set_xlim(0, x_offset + len(dias) * col_width + 0.3)
    ax.set_ylim(0, len(horas) * row_height + y_offset + 1.4)
    ax.axis("off")

    plt.title(f"CALENDARIO ACADÉMICO — {curso}º GCID ({sufijo_cuatri.upper()} SEMESTRE)", 
              fontsize=16, fontweight="bold", pad=25, color="#1A237E")
    plt.tight_layout()
    plt.savefig(ruta_salida, dpi=300, bbox_inches="tight")
    plt.close()
    print(f" Imagen guardada con éxito en: {os.path.abspath(ruta_salida)}")

    if abrir_al_terminar:
        ruta_abs = os.path.abspath(ruta_salida)
        try:
            if sys.platform.startswith("win"):
                os.system(f'start "" "{ruta_abs}"')
            else:
                subprocess.run(["open" if sys.platform.startswith("darwin") else "xdg-open", ruta_abs])
        except Exception:
            pass