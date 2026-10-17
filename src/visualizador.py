import os
import sys
import subprocess
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
from restricciones import obtener_subgrupos_estudiantes

# Diferenciación visual oficial EII: Teoría (Amarillo), Práctica de Aula (Azul), Laboratorio (Verde)
ESTILO_TIPO = {
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

def dibujar_bloque_grupo(ax, df_gp, gp_id, y_base, x_offset, col_width, row_height, dias, horas, estilo_tipo, mostrar_badge=True):
    """
    Dibuja un bloque completo de horario correspondiente a un Grupo Principal específico
    (Grupo 1, Grupo 2, Grupo 3 de tarde, etc.), con su distintivo lateral, horas, cabeceras y cuadrícula.
    """
    horas_map = {h: i for i, h in enumerate(horas)}
    h_bloque = len(horas) * row_height

    # 1. Distintivo del Grupo (a la izquierda)
    if mostrar_badge:
        x_badge = 0.4
        w_badge = 1.35
        badge_box = patches.FancyBboxPatch(
            (x_badge, y_base + 0.04), w_badge, h_bloque - 0.08,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#1A237E", edgecolor="none"
        )
        ax.add_patch(badge_box)

        es_tarde = any(int(h.split(":")[0]) >= 14 for h in horas if ":" in h)
        txt_badge = f"GRUPO {gp_id}" if not es_tarde else f"GRUPO {gp_id}\n\n(TARDE)"
        ax.text(x_badge + w_badge / 2, y_base + h_bloque / 2, txt_badge,
                ha="center", va="center", color="white", fontsize=12.5, fontweight="bold")

    # 2. Columna de Horas
    x_horas = 1.95 if mostrar_badge else 0.2
    w_horas = 1.65 if mostrar_badge else 1.6
    for i, hora in enumerate(horas):
        y = y_base + (len(horas) - 1 - i) * row_height
        time_box = patches.FancyBboxPatch(
            (x_horas, y + 0.04), w_horas, row_height - 0.08,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#E8EAF6", edgecolor="#C5CAE9", linewidth=1.1
        )
        ax.add_patch(time_box)
        ax.text(x_horas + w_horas / 2, y + row_height / 2, hora,
                ha="center", va="center", color="#283593", fontsize=9.5, fontweight="bold")

    # 3. Identificar subgrupos atómicos presentes en este grupo
    subgrupos_atomicos = set()
    for _, r in df_gp.iterrows():
        t = str(r.get("Tipo", r.get("tipo", ""))).lower()
        if "teor" not in t and "prob" not in t and "aula" not in t:
            subgrupos_atomicos.add(str(r.get("Grupo", r.get("grupo", ""))).strip())

    if not subgrupos_atomicos:
        for _, r in df_gp.iterrows():
            subgrupos_atomicos.add(str(r.get("Grupo", r.get("grupo", ""))).strip())

    subgrupos_ordenados = sorted(list(subgrupos_atomicos), key=lambda x: int(x) if x.isdigit() else x)
    num_subgrupos = len(subgrupos_ordenados)
    track_map = {sg: idx for idx, sg in enumerate(subgrupos_ordenados)}
    w_tr = (col_width - 0.08) / max(1, num_subgrupos)

    # 4. Cabeceras de días y subgrupos
    for j, dia in enumerate(dias):
        x = x_offset + j * col_width

        # Cabecera superior del Día
        header_box = patches.FancyBboxPatch(
            (x + 0.04, y_base + h_bloque + 0.30), col_width - 0.08, 0.40,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            facecolor="#1A237E", edgecolor="none"
        )
        ax.add_patch(header_box)
        ax.text(x + col_width / 2, y_base + h_bloque + 0.50, dia.upper(),
                ha="center", va="center", color="white", fontsize=11.5, fontweight="bold")

        # Sub-cabeceras de subgrupo atómico
        if num_subgrupos > 1:
            for t_idx, sg in enumerate(subgrupos_ordenados):
                x_sub = x + 0.04 + t_idx * w_tr
                sub_box = patches.FancyBboxPatch(
                    (x_sub + 0.01, y_base + h_bloque + 0.04), w_tr - 0.02, 0.22,
                    boxstyle="round,pad=0.02,rounding_size=0.04",
                    facecolor="#E8EAF6", edgecolor="#C5CAE9", linewidth=0.9
                )
                ax.add_patch(sub_box)
                ax.text(x_sub + w_tr / 2, y_base + h_bloque + 0.15,
                        f"G{sg}" if len(sg) <= 2 else sg,
                        ha="center", va="center", color="#283593", fontsize=7.5, fontweight="bold")

        # Cuadrícula de fondo
        for i in range(len(horas)):
            y = y_base + (len(horas) - 1 - i) * row_height
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

    # 5. Tarjetas de sesión de clase
    for _, ev in df_gp.iterrows():
        dia = ev["Dia"]
        hora = ev["Hora"]
        duracion = int(str(ev["Duracion"]).replace("h", ""))
        if hora not in horas_map or dia not in dias:
            continue
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

        subs = obtener_subgrupos_estudiantes(ev, df_clases=df_gp)
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
        y_box = y_base + (len(horas) - row_idx - duracion) * row_height + 0.04

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

        if span >= 3:
            f_asig = 10.5 if span == num_subgrupos else 9.5
            f_sub = 9.0 if span == num_subgrupos else 8.0
            ax.text(cx, cy + (0.16 if duracion > 1 else 0.09), f"{asig} ({tipo_tag}-{grupo})",
                    ha="center", va="center", color=estilo["text"],
                    fontsize=f_asig, fontweight="bold")
            ax.text(cx, cy - (0.13 if duracion > 1 else 0.09), f"Aula: {aula}",
                    ha="center", va="center", color="#37474F",
                    fontsize=f_sub, fontweight="bold")
        elif span == 2:
            f_asig = 8.5
            f_sub = 7.5
            if duracion >= 2:
                ax.text(cx, cy + 0.18, f"{asig} ({tipo_tag}-{grupo})",
                        ha="center", va="center", color=estilo["text"],
                        fontsize=f_asig, fontweight="bold")
                ax.text(cx, cy - 0.15, f"Aula: {aula}",
                        ha="center", va="center", color="#37474F",
                        fontsize=f_sub, fontweight="bold")
            else:
                ax.text(cx, cy + 0.11, f"{asig} ({tipo_tag}-{grupo})",
                        ha="center", va="center", color=estilo["text"],
                        fontsize=f_asig - 0.5, fontweight="bold")
                ax.text(cx, cy - 0.11, f"Aula: {aula}",
                        ha="center", va="center", color="#37474F",
                        fontsize=f_sub - 0.5, fontweight="bold")
        else:
            f_asig = 7.5
            f_sub = 6.8
            if duracion >= 3:
                ax.text(cx, cy + 0.38, asig, ha="center", va="center",
                        color=estilo["text"], fontsize=f_asig, fontweight="bold")
                ax.text(cx, cy + 0.02, f"{tipo_tag}-{grupo}", ha="center", va="center",
                        color=estilo["text"], fontsize=f_sub, fontweight="bold")
                ax.text(cx, cy - 0.34, aula, ha="center", va="center",
                        color="#37474F", fontsize=f_sub, fontweight="bold")
            elif duracion == 2:
                ax.text(cx, cy + 0.25, asig, ha="center", va="center",
                        color=estilo["text"], fontsize=f_asig, fontweight="bold")
                ax.text(cx, cy + 0.02, f"{tipo_tag}-{grupo}", ha="center", va="center",
                        color=estilo["text"], fontsize=f_sub, fontweight="bold")
                ax.text(cx, cy - 0.23, aula, ha="center", va="center",
                        color="#37474F", fontsize=f_sub, fontweight="bold")
            else:
                ax.text(cx, cy + 0.16, asig, ha="center", va="center",
                        color=estilo["text"], fontsize=f_asig - 0.5, fontweight="bold")
                ax.text(cx, cy - 0.01, f"{tipo_tag}-{grupo}", ha="center", va="center",
                        color=estilo["text"], fontsize=f_sub - 0.5, fontweight="bold")
                ax.text(cx, cy - 0.18, aula, ha="center", va="center",
                        color="#37474F", fontsize=f_sub - 0.5, fontweight="bold")


def exportar_horario_png(df_resultado, ruta_salida="horario_3GII_1er.png", titulo=None, abrir_al_terminar=False):
    """
    Exporta el horario a PNG.
    Si df_resultado contiene varios grupos principales, los dibuja apilados verticalmente
    (como en el PDF oficial de la EII), cada uno con su distintivo lateral y horas.
    """
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
    horas_manana = ["08:30-09:30", "09:30-10:30", "10:30-11:30", "11:30-12:30", "12:30-13:30", "13:30-14:30"]
    horas_tarde = ["14:30-15:30", "15:30-16:30", "16:30-17:30", "17:30-18:30", "18:30-19:30", "19:30-20:30"]

    grupos_presentes = sorted(df_resultado["GrupoPrincipal"].dropna().unique()) if "GrupoPrincipal" in df_resultado.columns else [1]
    num_grupos = len(grupos_presentes)

    col_width = 3.1
    x_offset = 3.8
    canvas_w = x_offset + len(dias) * col_width + 0.4

    if num_grupos > 1:
        row_height = 0.95
        h_bloque = len(horas_manana) * row_height + 0.8
        gap = 1.1
        canvas_h = num_grupos * h_bloque + (num_grupos - 1) * gap + 1.8
        fig, ax = plt.subplots(figsize=(20, 8.2 * num_grupos + 1.5), dpi=300)

        for k, gp in enumerate(grupos_presentes):
            df_gp = df_resultado[df_resultado["GrupoPrincipal"] == gp].copy()
            es_tarde = (gp == 3) or df_gp["Hora"].astype(str).str.startswith(("14:", "15:", "16:", "17:", "18:", "19:")).any()
            horas_gp = horas_tarde if es_tarde else horas_manana

            y_base = (num_grupos - 1 - k) * (h_bloque + gap) + 0.5
            dibujar_bloque_grupo(ax, df_gp, gp_id=int(gp), y_base=y_base,
                                 x_offset=x_offset, col_width=col_width, row_height=row_height,
                                 dias=dias, horas=horas_gp, estilo_tipo=ESTILO_TIPO, mostrar_badge=True)
    else:
        row_height = 1.15
        h_bloque = len(horas_manana) * row_height + 0.8
        canvas_h = h_bloque + 1.8
        fig, ax = plt.subplots(figsize=(20, 10.5), dpi=300)

        gp_val = int(grupos_presentes[0]) if grupos_presentes else 1
        es_tarde = (gp_val == 3) or df_resultado["Hora"].astype(str).str.startswith(("14:", "15:", "16:", "17:", "18:", "19:")).any()
        horas_gp = horas_tarde if es_tarde else horas_manana

        dibujar_bloque_grupo(ax, df_resultado, gp_id=gp_val, y_base=0.5,
                             x_offset=x_offset, col_width=col_width, row_height=row_height,
                             dias=dias, horas=horas_gp, estilo_tipo=ESTILO_TIPO, mostrar_badge=True)

    ax.set_facecolor("#F8F9FA")
    fig.patch.set_facecolor("#F8F9FA")

    # Leyenda en la parte superior derecha
    leyenda_y = canvas_h - 1.15

    box_t = patches.FancyBboxPatch((x_offset + 2.50 * col_width, leyenda_y), 1.25, 0.40,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=ESTILO_TIPO["teoria"]["bg"], edgecolor=ESTILO_TIPO["teoria"]["border"], linewidth=1.6)
    ax.add_patch(box_t)
    ax.text(x_offset + 2.50 * col_width + 0.625, leyenda_y + 0.20, "TEORÍA",
            ha="center", va="center", color=ESTILO_TIPO["teoria"]["text"], fontsize=9.0, fontweight="bold")

    box_a = patches.FancyBboxPatch((x_offset + 3.30 * col_width, leyenda_y), 1.65, 0.40,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=ESTILO_TIPO["problemas"]["bg"], edgecolor=ESTILO_TIPO["problemas"]["border"], linewidth=1.6)
    ax.add_patch(box_a)
    ax.text(x_offset + 3.30 * col_width + 0.825, leyenda_y + 0.20, "PRÁCTICA AULA",
            ha="center", va="center", color=ESTILO_TIPO["problemas"]["text"], fontsize=9.0, fontweight="bold")

    box_p = patches.FancyBboxPatch((x_offset + 4.25 * col_width, leyenda_y), 1.55, 0.40,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor=ESTILO_TIPO["practica"]["bg"], edgecolor=ESTILO_TIPO["practica"]["border"], linewidth=1.6)
    ax.add_patch(box_p)
    ax.text(x_offset + 4.25 * col_width + 0.775, leyenda_y + 0.20, "LABORATORIO",
            ha="center", va="center", color=ESTILO_TIPO["practica"]["text"], fontsize=9.0, fontweight="bold")

    ax.set_xlim(0, canvas_w)
    ax.set_ylim(0, canvas_h)
    ax.axis("off")

    if titulo is None:
        c_val = df_resultado["Curso"].iloc[0] if "Curso" in df_resultado.columns else 3
        s_num = int(df_resultado["Semestre"].iloc[0]) if "Semestre" in df_resultado.columns else 1
        sem_str = "1er SEMESTRE" if s_num == 1 else f"{s_num}º SEMESTRE"
        if num_grupos > 1:
            gps_str = f"Grupos {', '.join(str(g) for g in grupos_presentes)}"
        else:
            gps_str = f"Grupo {grupos_presentes[0]}"
        titulo = f"CALENDARIO ACADÉMICO — {c_val}º GII ({gps_str} - {sem_str})"

    plt.title(titulo, fontsize=16, fontweight="bold", pad=25, color="#1A237E")
    plt.tight_layout()
    carpeta = os.path.dirname(ruta_salida)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    plt.savefig(ruta_salida, dpi=300, bbox_inches="tight")
    plt.close()
    print(f" Imagen guardada con éxito en: {ruta_salida}")

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