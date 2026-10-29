import os
import sys
import subprocess
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd

def exportar_horario_png(df_resultado, curso=1, cuatrimestre=1, ruta_salida=None, abrir_al_terminar=True):
    sufijo_cuatri = "1er" if cuatrimestre == 1 else "2do"
    if ruta_salida is None:
        ruta_salida = f"horario_{curso}GCID_{sufijo_cuatri}.png"

    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]

    estilos_todos = {
        "teoria": {"bg": "#FFF9C4", "border": "#FBC02D", "text": "#E65100", "tag": "T", "label": "TEORÍA"},
        "practica_aula": {"bg": "#BBDEFB", "border": "#1976D2", "text": "#0D47A1", "tag": "PA", "label": "PRÁCTICA AULA"},
        "practica": {"bg": "#C8E6C9", "border": "#43A047", "text": "#1B5E20", "tag": "PL", "label": "LABORATORIO"}
    }

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
    tipos_presentes = set()
    for _, row in df_resultado.iterrows():
        t_raw = str(row["Tipo"]).strip().lower()
        if "aula" in t_raw:
            tipo_key = "practica_aula"
        elif "teor" in t_raw:
            tipo_key = "teoria"
        else:
            tipo_key = "practica"

        tipos_presentes.add(tipo_key)

        eventos.append({
            "dia_idx": dias.index(row["Dia"]),
            "start": horas.index(row["Hora"]),
            "dur": int(str(row["Duracion"]).replace("h", "")),
            "asig": row["Asignatura"],
            "tipo": tipo_key,
            "grupo": str(row["Grupo"]).strip(),
            "aula": row["Aula"]
        })

    lane_map_1 = {"41": 0, "42": 1, "43": 2, "44": 3}
    lane_map_3 = {"41": 0, "42": 1}

    # 5. Dibujar tarjetas sin solapes de texto
    for ev in eventos:
        d_idx = ev["dia_idx"]
        dur = ev["dur"]
        h_box = dur * row_height - 0.1
        y_box = (len(horas) - ev["start"] - dur) * row_height + y_offset + 0.05

        if ev["tipo"] == "teoria":
            w_box = col_width - 0.1
            x_box = x_offset + d_idx * col_width + 0.05
        elif curso == 1:
            w_single = (col_width - 0.1) / 4
            if ev["tipo"] == "practica_aula":
                w_box = w_single * 2
                start_lane = 0 if ev["grupo"] == "17" else 2
                x_box = x_offset + d_idx * col_width + 0.05 + start_lane * w_single
            else:
                w_box = w_single
                lane = lane_map_1.get(ev["grupo"], 0)
                x_box = x_offset + d_idx * col_width + 0.05 + lane * w_single
        else:
            w_single = (col_width - 0.1) / 2
            w_box = w_single
            lane = lane_map_3.get(ev["grupo"], 0)
            x_box = x_offset + d_idx * col_width + 0.05 + lane * w_single

        estilo = estilos_todos[ev["tipo"]]
        tarjeta = patches.FancyBboxPatch(
            (x_box + 0.015, y_box + 0.02), w_box - 0.03, h_box - 0.04,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=estilo["bg"], edgecolor=estilo["border"], linewidth=1.5
        )
        ax.add_patch(tarjeta)

        cx = x_box + w_box / 2
        cy = y_box + h_box / 2
        tag = estilo["tag"]

        # Formato de texto según duración y ancho de tarjeta
        if dur == 1:
            if w_box > col_width * 0.7:
                # 1 hora en teoría (ancho completo)
                ax.text(cx, cy + 0.18, f"{ev['asig']} ({tag}-G{ev['grupo']})",
                        ha="center", va="center", color=estilo["text"], fontsize=10, fontweight="bold")
                ax.text(cx, cy - 0.18, f"Aula: {ev['aula']}",
                        ha="center", va="center", color="#37474F", fontsize=9, fontweight="bold")
            else:
                # 1 hora estrecha
                ax.text(cx, cy + 0.18, f"{ev['asig']} ({tag}{ev['grupo']})",
                        ha="center", va="center", color=estilo["text"], fontsize=7.5, fontweight="bold")
                ax.text(cx, cy - 0.18, f"{ev['aula']}",
                        ha="center", va="center", color="#37474F", fontsize=7.0, fontweight="bold")
        else:
            # 2 o más horas
            if w_box > col_width * 0.7:
                f_t, f_s = 10.5, 9.5
                desp_t, desp_a = 0.22, 0.20
            elif w_box > col_width * 0.4:
                f_t, f_s = 8.5, 7.5
                desp_t, desp_a = 0.20, 0.18
            else:
                f_t, f_s = 7.0, 6.2
                desp_t, desp_a = 0.18, 0.16

            ax.text(cx, cy + desp_t, f"{ev['asig']}\n({tag}-G{ev['grupo']})",
                    ha="center", va="center", color=estilo["text"], fontsize=f_t, fontweight="bold")
            ax.text(cx, cy - desp_a, f"Aula: {ev['aula']}",
                    ha="center", va="center", color="#37474F", fontsize=f_s, fontweight="bold")

    # 6. Leyenda dinámica (solo tipos realmente presentes)
    orden_claves = ["teoria", "practica_aula", "practica"]
    claves_a_mostrar = [k for k in orden_claves if k in tipos_presentes]

    leyenda_y = len(horas) * row_height + y_offset + 0.82
    total_items = len(claves_a_mostrar)
    ancho_item = 1.3
    x_inicio_leyenda = x_offset + len(dias) * col_width - (total_items * (ancho_item + 0.2))

    for idx, k in enumerate(claves_a_mostrar):
        st = estilos_todos[k]
        bx = x_inicio_leyenda + idx * (ancho_item + 0.2)
        b_box = patches.FancyBboxPatch(
            (bx, leyenda_y), ancho_item, 0.38,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=st["bg"], edgecolor=st["border"], linewidth=1.6
        )
        ax.add_patch(b_box)
        ax.text(bx + ancho_item / 2, leyenda_y + 0.19, st["label"],
                ha="center", va="center", color=st["text"], fontsize=8.5, fontweight="bold")

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