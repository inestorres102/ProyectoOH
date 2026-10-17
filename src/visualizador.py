import os
import sys
import subprocess
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from restricciones import obtener_subgrupos_estudiantes

def exportar_horario_png(df_resultado, ruta_salida="horario_3GII_1er.png", titulo=None, abrir_al_terminar=True):
    """
    Exporta el horario a una imagen PNG de alta resolución diferenciando por colores
    Teoría (amarillo/cálido) vs Práctica (verde/esmeralda), y lo abre automáticamente.
    """
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]

    # Diferenciación visual: Teoría (Amarillo), Práctica de Aula (Azul), Laboratorio (Verde)
    estilo_tipo = {
        "teoria": {
            "bg": "#FFF9C4",      # Amarillo pastel
            "border": "#FBC02D",  # Dorado
            "text": "#E65100"     # Ámbar / naranja
        },
        "problemas": {
            "bg": "#E1F5FE",      # Azul pastel
            "border": "#0288D1",  # Azul medio
            "text": "#01579B"     # Azul marino oscuro
        },
        "practica": {
            "bg": "#C8E6C9",      # Verde pastel
            "border": "#43A047",  # Verde bosque
            "text": "#1B5E20"     # Verde oscuro
        }
    }

    fig, ax = plt.subplots(figsize=(19, 10), dpi=300)
    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    x_offset = 1.9
    col_width = 3.2
    y_offset = 0.5
    row_height = 1.2

    # Identificar subgrupos atómicos presentes en este horario
    subgrupos_atomicos = set()
    for _, r in df_resultado.iterrows():
        t = str(r.get("Tipo", r.get("tipo", ""))).lower()
        if "teor" not in t and "prob" not in t and "aula" not in t:
            subgrupos_atomicos.add(str(r.get("Grupo", r.get("grupo", ""))).strip())

    if not subgrupos_atomicos:
        for _, r in df_resultado.iterrows():
            subgrupos_atomicos.add(str(r.get("Grupo", r.get("grupo", ""))).strip())

    subgrupos_ordenados = sorted(list(subgrupos_atomicos), key=lambda x: int(x) if x.isdigit() else x)
    num_subgrupos = len(subgrupos_ordenados)
    track_map = {sg: idx for idx, sg in enumerate(subgrupos_ordenados)}
    w_tr = (col_width - 0.08) / max(1, num_subgrupos)

    # 1. Cabecera superior: Días y Subgrupos
    for j, dia in enumerate(dias):
        x = x_offset + j * col_width
        if num_subgrupos > 1:
            header_box = patches.FancyBboxPatch(
                (x + 0.04, len(horas) * row_height + y_offset + 0.32), col_width - 0.08, 0.42,
                boxstyle="round,pad=0.03,rounding_size=0.08",
                facecolor="#1A237E", edgecolor="none"
            )
            ax.add_patch(header_box)
            ax.text(x + col_width / 2, len(horas) * row_height + y_offset + 0.53, dia.upper(),
                    ha="center", va="center", color="white", fontsize=11.5, fontweight="bold")

            # Sub-cabeceras por subgrupo atómico
            for t_idx, sg in enumerate(subgrupos_ordenados):
                x_sub = x + 0.04 + t_idx * w_tr
                sub_box = patches.FancyBboxPatch(
                    (x_sub + 0.01, len(horas) * row_height + y_offset + 0.04), w_tr - 0.02, 0.24,
                    boxstyle="round,pad=0.02,rounding_size=0.04",
                    facecolor="#E8EAF6", edgecolor="#C5CAE9", linewidth=0.9
                )
                ax.add_patch(sub_box)
                ax.text(x_sub + w_tr / 2, len(horas) * row_height + y_offset + 0.16,
                        f"G{sg}" if len(sg) <= 2 else sg,
                        ha="center", va="center", color="#283593", fontsize=7.5, fontweight="bold")
        else:
            header_box = patches.FancyBboxPatch(
                (x + 0.05, len(horas) * row_height + y_offset + 0.1), col_width - 0.1, 0.55,
                boxstyle="round,pad=0.03,rounding_size=0.1",
                facecolor="#1A237E", edgecolor="none"
            )
            ax.add_patch(header_box)
            ax.text(x + col_width / 2, len(horas) * row_height + y_offset + 0.38, dia.upper(),
                    ha="center", va="center", color="white", fontsize=12, fontweight="bold")

    # 2. Cabecera lateral: Horas
    for i, hora in enumerate(horas):
        y = (len(horas) - 1 - i) * row_height + y_offset
        time_box = patches.FancyBboxPatch(
            (0.2, y + 0.05), x_offset - 0.3, row_height - 0.1,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#E8EAF6", edgecolor="#C5CAE9", linewidth=1.2
        )
        ax.add_patch(time_box)
        ax.text(0.2 + (x_offset - 0.3) / 2, y + row_height / 2, hora,
                ha="center", va="center", color="#283593", fontsize=10, fontweight="bold")

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
            if num_subgrupos > 1:
                for t_idx in range(1, num_subgrupos):
                    x_sep = x + 0.04 + t_idx * w_tr
                    ax.plot([x_sep, x_sep], [y + 0.04, y + row_height - 0.04],
                            color="#F0F0F0", linestyle="--", linewidth=0.6)

    # 4. Asignación de posiciones basada en subgrupos atómicos fijos
    horas_map = {h: i for i, h in enumerate(horas)}

    for _, ev in df_resultado.iterrows():
        dia = ev["Dia"]
        hora = ev["Hora"]
        duracion = int(str(ev["Duracion"]).replace("h", ""))
        row_idx = horas_map[hora]
        asig = ev["Asignatura"]
        aula = ev["Aula"]
        col_idx = dias.index(dia)

        tipo_str = str(ev.get("Tipo", "")).strip().lower()
        if "teor" in tipo_str:
            tipo_clave = "teoria"
            tipo_tag = "T"
        elif "prob" in tipo_str or "aula" in tipo_str or "ejer" in tipo_str or "pa" in tipo_str:
            tipo_clave = "problemas"
            tipo_tag = "PA"
        else:
            tipo_clave = "practica"
            tipo_tag = "P"
        grupo = f"G{ev['Grupo']}"

        # Subgrupos atómicos a los que pertenece esta sesión
        subs = obtener_subgrupos_estudiantes(ev, df_clases=df_resultado)
        tracks = [track_map[g] for g in subs if g in track_map]

        if not tracks or num_subgrupos <= 1:
            min_t = 0
            span = max(1, num_subgrupos)
        else:
            min_t = min(tracks)
            span = max(tracks) - min_t + 1

        x_box = x_offset + col_idx * col_width + 0.04 + min_t * w_tr
        w_box = span * w_tr

        h_box = duracion * row_height - 0.08
        y_box = (len(horas) - row_idx - duracion) * row_height + y_offset + 0.04

        estilo = estilo_tipo[tipo_clave]
        rounding = 0.08 if span >= 2 else 0.03
        lwidth = 1.8 if span >= 2 else 1.1

        tarjeta = patches.FancyBboxPatch(
            (x_box + 0.02, y_box + 0.02), w_box - 0.04, h_box - 0.04,
            boxstyle=f"round,pad=0.02,rounding_size={rounding}",
            facecolor=estilo["bg"], edgecolor=estilo["border"], linewidth=lwidth
        )
        ax.add_patch(tarjeta)

        cx = x_box + w_box / 2
        cy = y_box + h_box / 2

        # Tipografía responsiva según el ancho disponible (span)
        if span >= 3:
            # Teoría o clases que abarcan casi todo el día: formato espacioso a 2 líneas
            f_asig = 11.0 if span == num_subgrupos else 10.0
            f_sub = 9.5 if span == num_subgrupos else 8.5
            ax.text(cx, cy + (0.18 if duracion > 1 else 0.10), f"{asig} ({tipo_tag}-{grupo})",
                    ha="center", va="center", color=estilo["text"],
                    fontsize=f_asig, fontweight="bold")
            ax.text(cx, cy - (0.14 if duracion > 1 else 0.10), f"Aula: {aula}",
                    ha="center", va="center", color="#37474F",
                    fontsize=f_sub, fontweight="bold")
        elif span == 2:
            # Práctica de aula (2 subgrupos, ej: G19 sobre 45-46 o G20 sobre 47-48)
            f_asig = 9.0
            f_sub = 8.0
            if duracion >= 2:
                ax.text(cx, cy + 0.20, f"{asig} ({tipo_tag}-{grupo})",
                        ha="center", va="center", color=estilo["text"],
                        fontsize=f_asig, fontweight="bold")
                ax.text(cx, cy - 0.16, f"Aula: {aula}",
                        ha="center", va="center", color="#37474F",
                        fontsize=f_sub, fontweight="bold")
            else:
                ax.text(cx, cy + 0.12, f"{asig} ({tipo_tag}-{grupo})",
                        ha="center", va="center", color=estilo["text"],
                        fontsize=f_asig - 0.5, fontweight="bold")
                ax.text(cx, cy - 0.12, f"Aula: {aula}",
                        ha="center", va="center", color="#37474F",
                        fontsize=f_sub - 0.5, fontweight="bold")
        else:
            # Laboratorio individual (carril estrecho de 1 subgrupo): formato compacto en 3 líneas
            f_asig = 8.0
            f_sub = 7.0
            if duracion >= 3:
                ax.text(cx, cy + 0.42, asig, ha="center", va="center",
                        color=estilo["text"], fontsize=f_asig, fontweight="bold")
                ax.text(cx, cy + 0.02, f"{tipo_tag}-{grupo}", ha="center", va="center",
                        color=estilo["text"], fontsize=f_sub, fontweight="bold")
                ax.text(cx, cy - 0.38, aula, ha="center", va="center",
                        color="#37474F", fontsize=f_sub, fontweight="bold")
            elif duracion == 2:
                ax.text(cx, cy + 0.28, asig, ha="center", va="center",
                        color=estilo["text"], fontsize=f_asig, fontweight="bold")
                ax.text(cx, cy + 0.02, f"{tipo_tag}-{grupo}", ha="center", va="center",
                        color=estilo["text"], fontsize=f_sub, fontweight="bold")
                ax.text(cx, cy - 0.26, aula, ha="center", va="center",
                        color="#37474F", fontsize=f_sub, fontweight="bold")
            else:
                ax.text(cx, cy + 0.18, asig, ha="center", va="center",
                        color=estilo["text"], fontsize=f_asig - 1, fontweight="bold")
                ax.text(cx, cy - 0.01, f"{tipo_tag}-{grupo}", ha="center", va="center",
                        color=estilo["text"], fontsize=f_sub - 0.5, fontweight="bold")
                ax.text(cx, cy - 0.20, aula, ha="center", va="center",
                        color="#37474F", fontsize=f_sub - 0.5, fontweight="bold")

    # 5. Leyenda en la parte superior derecha (3 modalidades oficiales EII)
    leyenda_y = len(horas) * row_height + y_offset + 0.85

    # Caja 1: Teoría
    box_t = patches.FancyBboxPatch((x_offset + 2.65 * col_width, leyenda_y), 1.15, 0.40,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=estilo_tipo["teoria"]["bg"], edgecolor=estilo_tipo["teoria"]["border"], linewidth=1.6)
    ax.add_patch(box_t)
    ax.text(x_offset + 2.65 * col_width + 0.575, leyenda_y + 0.20, "TEORÍA",
            ha="center", va="center", color=estilo_tipo["teoria"]["text"], fontsize=9.0, fontweight="bold")

    # Caja 2: Práctica de Aula / Problemas
    box_a = patches.FancyBboxPatch((x_offset + 3.40 * col_width, leyenda_y), 1.55, 0.40,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=estilo_tipo["problemas"]["bg"], edgecolor=estilo_tipo["problemas"]["border"], linewidth=1.6)
    ax.add_patch(box_a)
    ax.text(x_offset + 3.40 * col_width + 0.775, leyenda_y + 0.20, "PRÁCTICA AULA",
            ha="center", va="center", color=estilo_tipo["problemas"]["text"], fontsize=9.0, fontweight="bold")

    # Caja 3: Laboratorio
    box_p = patches.FancyBboxPatch((x_offset + 4.25 * col_width, leyenda_y), 1.50, 0.40,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=estilo_tipo["practica"]["bg"], edgecolor=estilo_tipo["practica"]["border"], linewidth=1.6)
    ax.add_patch(box_p)
    ax.text(x_offset + 4.25 * col_width + 0.750, leyenda_y + 0.20, "LABORATORIO",
            ha="center", va="center", color=estilo_tipo["practica"]["text"], fontsize=9.0, fontweight="bold")

    ax.set_xlim(0, x_offset + len(dias) * col_width + 0.3)
    ax.set_ylim(0, len(horas) * row_height + y_offset + 1.4)
    ax.axis("off")

    if titulo is None:
        c_val = df_resultado["Curso"].iloc[0] if "Curso" in df_resultado.columns else 3
        gp_val = df_resultado["GrupoPrincipal"].iloc[0] if "GrupoPrincipal" in df_resultado.columns else 1
        if "Semestre" in df_resultado.columns:
            s_num = int(df_resultado["Semestre"].iloc[0])
            sem_str = "1er SEMESTRE" if s_num == 1 else f"{s_num}º SEMESTRE"
        else:
            sem_str = "2º SEMESTRE" if ("2do" in ruta_salida or "semestre 2" in ruta_salida.lower()) else "1er SEMESTRE"
        titulo = f"CALENDARIO ACADÉMICO — {c_val}º GII (Grupo {gp_val} - {sem_str})"

    plt.title(titulo, fontsize=16, fontweight="bold", pad=25, color="#1A237E")
    plt.tight_layout()
    carpeta = os.path.dirname(ruta_salida)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    plt.savefig(ruta_salida, dpi=300, bbox_inches="tight")
    plt.close()
    print(f" Imagen guardada con éxito en: {ruta_salida}")

    # 6. Abrir automáticamente la imagen generada
    if abrir_al_terminar:
        try:
            if sys.platform.startswith("win"):
                os.startfile(ruta_salida)
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", ruta_salida])
            else:
                subprocess.run(["xdg-open", ruta_salida])
        except Exception as e:
            print(f"No se pudo abrir automáticamente la imagen: {e}")