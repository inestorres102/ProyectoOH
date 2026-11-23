"""
Cuadro de Mandos Interactivo — Planificación Automática de Horarios EII (ULPGC)
Proyecto de Optimización y Heurística (Curso 2026-2027)

Integra en una interfaz homogénea las tres titulaciones de la Escuela:
- GII  (Grado en Ingeniería Informática)
- GCID (Grado en Ciencia e Ingeniería de Datos)
- GIFM (Grado en Ingeniería Física y Matemática)
"""

import html
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

try:
    import pymupdf
    from PIL import Image
    HAS_PDF_RENDER = True
except ImportError:
    HAS_PDF_RENDER = False


REPO_ROOT = Path(__file__).resolve().parent

TITULACIONES_INFO = {
    "GII": {
        "nombre": "Grado en Ingeniería Informática",
        "corto": "GII",
        "autor": "Yone",
        "color": "#1E40AF",
        "estrategia": "OR-Tools CP-SAT + Recocido Simulado propio (desde cero) + Baseline Aleatorio",
        "particularidades": (
            "Turnos de Mañana (Grupos 1 y 2) y Tarde (Grupo 3 en 1º), "
            "jerarquía de subgrupos (Teoría / Práctica de Aula / Lab) y Laboratorio de Física (LF-4)."
        ),
        "ruta_clases": REPO_ROOT / "GII" / "datos" / "clases.csv",
        "ruta_aulas": REPO_ROOT / "GII" / "datos" / "aulas.csv",
        "ruta_pdf": REPO_ROOT / "GII" / "horario_GII_2026_2027.pdf",
        "pdf_leyenda_idx": 7,
        "pdf_pages": {
            (1, 1): (0, "full"),
            (1, 2): (1, "full"),
            (2, 1): (2, "full"),
            (2, 2): (3, "full"),
            (3, 1): (4, "full"),
            (3, 2): (5, "full"),
            (4, 1): (6, "top"),
            (4, 2): (6, "bottom"),
        },
    },
    "GCID": {
        "nombre": "Grado en Ciencia e Ingeniería de Datos",
        "corto": "GCID",
        "autor": "Inés",
        "color": "#0F766E",
        "estrategia": "OR-Tools CP-SAT global por cuatrimestre + Recocido Simulado propio (60.000 iter.)",
        "particularidades": (
            "Compactación estricta sin huecos (0 horas libres), equilibrio diario en 1º curso, "
            "jueves y viernes libres en 3º (2º cuatri) para prácticas externas y aula preferida A2-5."
        ),
        "ruta_clases": REPO_ROOT / "GCID" / "datos" / "clases_gcid.csv",
        "ruta_aulas": REPO_ROOT / "GCID" / "datos" / "aulas.csv",
        "ruta_pdf": REPO_ROOT / "GCID" / "horario_GCID_2026_2027.pdf",
        "pdf_leyenda_idx": 4,
        "pdf_pages": {
            (1, 1): (0, "top"),
            (1, 2): (0, "bottom"),
            (2, 1): (1, "top"),
            (2, 2): (1, "bottom"),
            (3, 1): (2, "top"),
            (3, 2): (2, "bottom"),
            (4, 1): (3, "top"),
            (4, 2): (3, "bottom"),
        },
    },
    "GIFM": {
        "nombre": "Grado en Ingeniería Física y Matemática",
        "corto": "GIFM",
        "autor": "María",
        "color": "#B45309",
        "estrategia": "Pipeline híbrido: solución factible CP-SAT refinada mediante Recocido Simulado",
        "particularidades": (
            "Desglose en bloques horarios con semanas activas (p. ej. 1-15 o parciales), "
            "aula preferida A3-1 y ampliación excepcional de jornada (08:30-16:30) para 3º (2º cuatri)."
        ),
        "ruta_clases": REPO_ROOT / "GIFM" / "datos" / "clases.csv",
        "ruta_aulas": REPO_ROOT / "GIFM" / "datos" / "aulas.csv",
        "ruta_pdf": REPO_ROOT / "GIFM" / "horario_GIFM_2026_2027.pdf",
        "pdf_leyenda_idx": 7,
        "pdf_pages": {
            (1, 1): (0, "full"),
            (1, 2): (1, "full"),
            (2, 1): (2, "top"),
            (2, 2): (2, "bottom"),
            (3, 1): (3, "full"),
            (3, 2): (4, "full"),
            (4, 1): (5, "full"),
            (4, 2): (6, "full"),
        },
    },
}

GCID_CARPETA_CURSO = {1: "primero", 2: "segundo", 3: "tercero", 4: "cuarto"}

GCID_BENCHMARK = pd.DataFrame([
    {"Cuatrimestre": "1er Semestre", "Metodo": "OR-Tools CP-SAT", "Sesiones": 86, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 85, "Tiempo_s": 10.78},
    {"Cuatrimestre": "1er Semestre", "Metodo": "Recocido Simulado", "Sesiones": 86, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 160, "Tiempo_s": 11.08},
    {"Cuatrimestre": "2º Semestre", "Metodo": "OR-Tools CP-SAT", "Sesiones": 64, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 25, "Tiempo_s": 4.77},
    {"Cuatrimestre": "2º Semestre", "Metodo": "Recocido Simulado", "Sesiones": 64, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 150, "Tiempo_s": 9.45},
])

DIAS_ORDEN = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]


# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Horarios EII · ULPGC — Proyecto OH",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.3rem;
        padding-bottom: 2.5rem;
    }
    .eii-hero {
        background: linear-gradient(125deg, #0B1F42 0%, #153A75 58%, #1D4ED8 100%);
        color: #FFFFFF;
        padding: 1.35rem 1.75rem;
        border-radius: 14px;
        margin-bottom: 1.2rem;
        box-shadow: 0 8px 24px rgba(15, 41, 82, 0.16);
    }
    .eii-hero h1 {
        margin: 0 0 0.3rem 0;
        font-size: 1.7rem;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: -0.02em;
    }
    .eii-hero p {
        margin: 0;
        color: #DBEAFE;
        font-size: 0.94rem;
    }
    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.8rem;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        padding: 0.22rem 0.68rem;
        border-radius: 999px;
        font-size: 0.77rem;
        font-weight: 700;
        border: 1px solid rgba(255,255,255,0.22);
        background: rgba(255,255,255,0.12);
        color: #FFFFFF;
    }
    .legend-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        align-items: center;
        margin: 0.35rem 0 0.8rem 0;
    }
    .leg-item {
        display: inline-flex;
        align-items: center;
        padding: 0.2rem 0.65rem;
        border-radius: 8px;
        font-size: 0.79rem;
        font-weight: 700;
    }
    .leg-teoria { background: #FFF9C4; color: #E65100; border: 1.5px solid #FBC02D; }
    .leg-aula   { background: #E1F5FE; color: #01579B; border: 1.5px solid #0288D1; }
    .leg-lab    { background: #C8E6C9; color: #1B5E20; border: 1.5px solid #43A047; }
    .leg-morado { background: #D1C4E9; color: #4527A0; border: 1.5px solid #7E57C2; }
    .info-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1rem 1.15rem;
        box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
        height: 100%;
    }
    .info-card h4 { margin: 0 0 0.4rem 0; color: #0F2952; font-size: 1.02rem; }
    .info-card p  { margin: 0.25rem 0; font-size: 0.88rem; color: #334155; line-height: 1.45; }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
    /* Cuadrícula HTML interactiva unificada EII */
    .tt-wrap {
        background: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-radius: 12px;
        overflow-x: auto;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
        margin-bottom: 1rem;
    }
    .tt-header {
        background: #0F2952;
        color: #FFFFFF;
        padding: 0.65rem 1rem;
        font-weight: 800;
        font-size: 0.94rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .tt-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        min-width: 780px;
    }
    .tt-table th {
        background: #1A237E;
        color: #FFFFFF;
        font-size: 0.82rem;
        font-weight: 700;
        padding: 0.55rem 0.4rem;
        border: 1px solid #334155;
        text-align: center;
        letter-spacing: 0.03em;
    }
    .tt-table th.tt-hcol {
        width: 108px;
        background: #0F2952;
    }
    .tt-table td {
        border: 1px solid #E2E8F0;
        vertical-align: top;
        padding: 4px;
        height: 68px;
        background: #FCFDFE;
    }
    .tt-table td.tt-time {
        background: #EEF2FF;
        color: #1E293B;
        font-weight: 700;
        font-size: 0.78rem;
        text-align: center;
        vertical-align: middle;
        white-space: nowrap;
    }
    .tt-cell-flex {
        display: flex;
        gap: 4px;
        height: 100%;
        align-items: stretch;
    }
    .tt-card {
        flex: 1 1 0;
        min-width: 0;
        border-radius: 7px;
        padding: 5px 6px;
        font-size: 0.74rem;
        line-height: 1.25;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
        overflow: hidden;
    }
    .tt-card:hover {
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.14);
    }
    .tt-card-teoria { background: #FFF9C4; border: 1.6px solid #FBC02D; color: #7C2D12; }
    .tt-card-aula   { background: #E1F5FE; border: 1.6px solid #0288D1; color: #0C4A6E; }
    .tt-card-lab    { background: #C8E6C9; border: 1.6px solid #43A047; color: #14532D; }
    .tt-card-dim    { opacity: 0.22; filter: grayscale(0.6); }
    .tt-asig  { font-weight: 800; font-size: 0.8rem; }
    .tt-meta  { font-size: 0.7rem; font-weight: 600; margin-top: 2px; }
    .tt-prof  { font-size: 0.65rem; opacity: 0.85; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# CARGA CACHEADA DE DATOS Y RECURSOS
# ---------------------------------------------------------------------------
def _normalizar_tipo(valor: str) -> str:
    t = str(valor).strip().lower()
    if "teor" in t:
        return "Teoría"
    if "aula" in t or "problem" in t:
        return "Práctica de Aula"
    return "Laboratorio"


def _normalizar_dia(valor: str) -> str:
    d = str(valor).strip().lower()
    if "lun" in d:
        return "Lunes"
    if "mar" in d:
        return "Martes"
    if "mi" in d:
        return "Miércoles"
    if "jue" in d:
        return "Jueves"
    if "vie" in d:
        return "Viernes"
    return str(valor).strip()


@st.cache_data(show_spinner=False)
def cargar_catalogo_unificado() -> pd.DataFrame:
    frames = []
    for deg, info in TITULACIONES_INFO.items():
        df = pd.read_csv(info["ruta_clases"], encoding="utf-8-sig")
        df.columns = df.columns.str.strip()
        sem_col = "semestre" if "semestre" in df.columns else "cuatrimestre"
        norm = pd.DataFrame({
            "Titulación": deg,
            "ID": df["id_sesion"].astype(str).str.strip(),
            "Curso": pd.to_numeric(df["curso"], errors="coerce").fillna(1).astype(int),
            "Cuatrimestre": pd.to_numeric(df[sem_col], errors="coerce").fillna(1).astype(int),
            "Asignatura": df["asignatura"].astype(str).str.strip(),
            "Modalidad": df["tipo"].apply(_normalizar_tipo),
            "Tipo_Original": df["tipo"].astype(str).str.strip(),
            "Grupo": df["grupo"].astype(str).str.strip(),
            "Grupo_Principal": (
                pd.to_numeric(df["grupo_principal"], errors="coerce").fillna(1).astype(int)
                if "grupo_principal" in df.columns
                else 1
            ),
            "Horas": pd.to_numeric(df["duracion_horas"], errors="coerce").fillna(0).astype(int),
            "Alumnos": pd.to_numeric(df["num_alumnos"], errors="coerce").fillna(0).astype(int),
            "Tipo_Aula": df["tipo_aula_requerida"].astype(str).str.strip(),
            "Profesor": df["profesor"].astype(str).str.strip(),
            "Semanas": df["semanas"].astype(str).str.strip() if "semanas" in df.columns else "1-15",
        })
        frames.append(norm)
    return pd.concat(frames, ignore_index=True)


@st.cache_data(show_spinner=False)
def cargar_horarios_resueltos() -> pd.DataFrame:
    p = REPO_ROOT / "dashboard_data" / "horarios_unificados.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, encoding="utf-8-sig")
    df["Dia"] = df["Dia"].apply(_normalizar_dia)
    df["Grupo"] = df["Grupo"].astype(str).str.strip()
    df["Aula"] = df["Aula"].astype(str).str.strip()
    df["Profesor"] = df["Profesor"].astype(str).str.strip()
    df["Semanas"] = df["Semanas"].fillna("1-15").astype(str).str.strip()
    return df


@st.cache_data(show_spinner=False)
def cargar_aulas() -> pd.DataFrame:
    df = pd.read_csv(REPO_ROOT / "GII" / "datos" / "aulas.csv", encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df["tipo"] = df["tipo"].astype(str).str.strip()
    df["capacidad"] = pd.to_numeric(df["capacidad"], errors="coerce").fillna(0).astype(int)
    return df


@st.cache_data(show_spinner=False)
def cargar_benchmark_gii() -> pd.DataFrame:
    p = REPO_ROOT / "GII" / "memoria" / "benchmark_resultados.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, encoding="utf-8-sig")


@st.cache_data(show_spinner=False)
def cargar_estadisticas_gifm() -> pd.DataFrame:
    carpeta = REPO_ROOT / "GIFM" / "resultados"
    filas = [pd.read_csv(f, encoding="utf-8-sig") for f in sorted(carpeta.glob("estadisticas_recocido_*.csv"))]
    if not filas:
        return pd.DataFrame()
    df = pd.concat(filas, ignore_index=True)
    df["Instancia"] = df.apply(lambda r: f"{int(r['Curso'])}º GIFM · C{int(r['Cuatrimestre'])}", axis=1)
    return df


@st.cache_data(show_spinner=False)
def renderizar_pagina_pdf(tit: str, page_idx: int, crop_mode: str = "full", zoom: float = 2.0) -> bytes | None:
    pdf_path = TITULACIONES_INFO[tit]["ruta_pdf"]
    if not HAS_PDF_RENDER or not pdf_path.exists():
        return None
    doc = pymupdf.open(str(pdf_path))
    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        return None
    page = doc.load_page(page_idx)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    if crop_mode in ("top", "bottom"):
        # Calcular el punto exacto de corte vertical usando la caja de "Segundo Semestre"
        w, h = img.size
        split_ratio = 0.425
        hits = page.search_for("Segundo Semestre")
        if hits:
            # Convertir coordenadas del PDF a coordenadas visuales rotadas
            r_vis = hits[0] * page.rotation_matrix
            pr = page.rect
            cand = (r_vis.y0 - pr.y0) / max(pr.height, 1.0)
            if 0.28 <= cand <= 0.65:
                split_ratio = max(0.28, cand - 0.012)
        y_cut = int(h * split_ratio)
        if crop_mode == "top":
            img = img.crop((0, int(h * 0.04), w, y_cut))
        else:
            img = img.crop((0, y_cut, w, int(h * 0.94)))

    doc.close()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def obtener_opciones_gii(curso: int, cuatrimestre: int) -> list[dict]:
    """Devuelve opciones homogéneas (label, grupo_principal o None, ruta CP-SAT, ruta SA)."""
    sem_dir = "1er_Semestre" if cuatrimestre == 1 else "2do_Semestre"
    carpeta_cp = REPO_ROOT / "GII" / "horarios" / f"{curso}GII" / sem_dir
    carpeta_sa = REPO_ROOT / "GII" / "horarios_SA" / f"{curso}GII" / sem_dir

    conj_label = (
        "Vista Conjunta (G1 + G2 + G3 Tarde)"
        if curso == 1
        else "Vista Conjunta (Mañana: G1 + G2)"
    )
    especificaciones = [
        (conj_label, None, "horario_conjunto.png"),
        ("Grupo 1 (Mañana)", 1, "horario_Grupo_1.png"),
        ("Grupo 2 (Mañana)", 2, "horario_Grupo_2.png"),
        ("Grupo 3 (Turno de Tarde)", 3, "horario_Grupo_3.png"),
    ]
    opciones = []
    for label, gp, fname in especificaciones:
        p_cp = carpeta_cp / fname
        p_sa = carpeta_sa / fname
        if p_cp.exists() or p_sa.exists():
            opciones.append({"label": label, "gp": gp, "cp": p_cp, "sa": p_sa})
    return opciones


def obtener_rutas_png(tit: str, curso: int, cuatrimestre: int, gii_opt: dict | None = None) -> tuple[Path | None, Path | None]:
    if tit == "GII":
        if gii_opt is None:
            return None, None
        return gii_opt["cp"], gii_opt["sa"]
    if tit == "GCID":
        c_dir = GCID_CARPETA_CURSO[curso]
        sem = "1er" if cuatrimestre == 1 else "2do"
        return (
            REPO_ROOT / "GCID" / "horarios_CP-SAT" / c_dir / f"horario_{curso}GCID_{sem}.png",
            REPO_ROOT / "GCID" / "horarios_metaheuristica" / c_dir / f"horario_SA_{curso}GCID_{sem}.png",
        )
    base = REPO_ROOT / "GIFM" / "resultados"
    return (
        base / f"horario_{curso}GIFM_{cuatrimestre}cuatri.png",
        base / f"horario_{curso}GIFM_{cuatrimestre}cuatri_recocido.png",
    )


def mostrar_leyenda(paleta: str = "eii"):
    if paleta == "gifm_orig":
        st.markdown(
            """
            <div class="legend-bar">
                <span style="font-size:0.81rem; font-weight:700; color:#475569;">Leyenda original PNG de GIFM:</span>
                <span class="leg-item leg-teoria">Teoría</span>
                <span class="leg-item leg-morado">Práctica / Laboratorio (GIFM)</span>
                <span style="font-size:0.78rem; color:#64748B;">(En la pestaña <b>Vista Interactiva Unificada</b> se muestran con la paleta oficial EII).</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="legend-bar">
                <span style="font-size:0.81rem; font-weight:700; color:#475569;">Paleta oficial EII unificada:</span>
                <span class="leg-item leg-teoria">Teoría</span>
                <span class="leg-item leg-aula">Práctica de Aula / Problemas</span>
                <span class="leg-item leg-lab">Práctica de Laboratorio</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def renderizar_cuadricula_html(df_bloques: pd.DataFrame, titulo_barra: str, filtro_texto: str = "") -> str:
    """Genera una cuadrícula semanal HTML limpia y 100% uniforme en las 3 titulaciones."""
    if df_bloques.empty:
        return "<p>No hay sesiones resueltas para mostrar.</p>"

    # Detectar horas de inicio (mañana 08:30, tarde 14:30, o ampliada 08:30-16:30)
    slots_min = int(df_bloques["Slot"].min())
    es_tarde = any(str(h).startswith(("14:30", "15:30", "16:30", "17:30", "18:30", "19:30")) for h in df_bloques["Hora"]) and not any(
        str(h).startswith(("08:30", "09:30", "10:30", "11:30")) for h in df_bloques["Hora"]
    )

    if es_tarde:
        h_ini, n_horas = 14, 6
    else:
        # Comprobar si hay horario ampliado hasta las 16:30 (3º GIFM C2)
        necesita_8 = any(str(h).endswith(("15:30", "16:30")) or str(h).startswith(("14:30", "15:30")) for h in df_bloques["Hora"])
        h_ini, n_horas = 8, (8 if necesita_8 else 6)

    horas_labels = [f"{h_ini + i:02d}:30-{h_ini + i + 1:02d}:30" for i in range(n_horas)]

    # Colocar cada bloque en su celda (dia, hora_idx) con rowspan = duracion
    # Si hay varios bloques solapados en un mismo día/hora (subgrupos distintos), los agrupamos en la celda de inicio
    # Para que las tablas HTML nunca se rompan con rowspans cruzados entre subgrupos, renderizamos por hora con tarjetas limpias
    celdas: dict[tuple[str, int], list[dict]] = {(d, h): [] for d in DIAS_ORDEN for h in range(n_horas)}

    q = filtro_texto.strip().lower()
    for _, r in df_bloques.iterrows():
        dia = _normalizar_dia(r["Dia"])
        if dia not in DIAS_ORDEN:
            continue
        hora_str = str(r["Hora"]).strip()
        try:
            h_start = int(hora_str.split(":")[0])
            h_idx = h_start - h_ini
        except Exception:
            h_idx = int(r["Slot"]) % n_horas
        dur = max(1, int(r["DuracionHoras"]))

        coincide = True
        if q:
            blob = f"{r['Asignatura']} {r['Profesor']} {r['Aula']} {r['Grupo']} {r['Modalidad']}".lower()
            coincide = q in blob

        for offset in range(dur):
            idx = h_idx + offset
            if 0 <= idx < n_horas:
                celdas[(dia, idx)].append({
                    "asig": str(r["Asignatura"]),
                    "mod": str(r["Modalidad"]),
                    "grupo": str(r["Grupo"]),
                    "aula": str(r["Aula"]),
                    "prof": str(r["Profesor"]),
                    "sem": str(r["Semanas"]),
                    "dur": dur,
                    "cont": offset > 0,
                    "match": coincide,
                })

    cls_map = {
        "Teoría": "tt-card-teoria",
        "Práctica de Aula": "tt-card-aula",
        "Laboratorio": "tt-card-lab",
    }

    rows_html = []
    for h_idx, h_lbl in enumerate(horas_labels):
        tds = [f'<td class="tt-time">{h_lbl}</td>']
        for d in DIAS_ORDEN:
            items = sorted(celdas[(d, h_idx)], key=lambda x: (x["mod"] != "Teoría", x["grupo"], x["asig"]))
            if not items:
                tds.append("<td></td>")
                continue
            cards = []
            for it in items:
                cls = cls_map.get(it["mod"], "tt-card-lab")
                if not it["match"]:
                    cls += " tt-card-dim"
                sem_tag = f" · Sem. {html.escape(it['sem'])}" if it["sem"] not in ("", "1-15", "nan") else ""
                cont_tag = " ↳" if it["cont"] else ""
                tip = html.escape(f"{it['asig']} ({it['mod']}) | Grupo {it['grupo']} | Aula {it['aula']} | {it['prof']} | Semanas: {it['sem']}")
                cards.append(
                    f'<div class="tt-card {cls}" title="{tip}">'
                    f'<div class="tt-asig">{html.escape(it["asig"])}{cont_tag} <span style="font-weight:600;opacity:0.85;">(G{html.escape(it["grupo"])})</span></div>'
                    f'<div class="tt-meta">{html.escape(it["aula"])}{sem_tag}</div>'
                    f'<div class="tt-prof">{html.escape(it["prof"])}</div>'
                    f'</div>'
                )
            tds.append(f'<td><div class="tt-cell-flex">{"".join(cards)}</div></td>')
        rows_html.append(f'<tr>{"".join(tds)}</tr>')

    ths = '<th class="tt-hcol">HORA</th>' + "".join(f"<th>{d.upper()}</th>" for d in DIAS_ORDEN)
    return (
        f'<div class="tt-wrap">'
        f'<div class="tt-header"><span>{html.escape(titulo_barra)}</span>'
        f'<span style="font-size:0.78rem; font-weight:600; color:#BFDBFE;">Pasa el ratón por cualquier tarjeta para ver el detalle completo</span></div>'
        f'<table class="tt-table"><thead><tr>{ths}</tr></thead><tbody>{"".join(rows_html)}</tbody></table>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# CARGA GLOBAL Y SIDEBAR DE NAVEGACIÓN
# ---------------------------------------------------------------------------
df_catalogo = cargar_catalogo_unificado()
df_resueltos = cargar_horarios_resueltos()
df_aulas = cargar_aulas()

with st.sidebar:
    st.markdown(
        """
        <div style="padding:0.35rem 0 0.75rem 0;">
            <div style="font-size:0.74rem; font-weight:800; letter-spacing:0.08em; color:#64748B; text-transform:uppercase;">
                ULPGC · Escuela de Ingeniería Informática
            </div>
            <div style="font-size:1.28rem; font-weight:800; color:#0F2952; margin-top:0.15rem;">
                Planificador OH
            </div>
            <div style="font-size:0.81rem; color:#475569; margin-top:0.1rem;">
                Curso Académico 2026–2027
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    vista = st.radio(
        "Navegación del cuadro de mandos",
        options=[
            "🗓️ Explorador de Horarios",
            "🏠 Visión General (EII)",
            "📊 Resultados y Convergencia",
            "⚡ Simulador en Vivo",
            "📚 Modelo Matemático y Catálogo",
        ],
        index=0,
    )

    st.divider()
    st.markdown("**Resumen integrado**")
    st.caption(
        f"• **3 titulaciones:** GII, GCID y GIFM\n"
        f"• **24 calendarios** (1º–4º · S1 y S2)\n"
        f"• **{len(df_catalogo)} sesiones** ({int(df_catalogo['Horas'].sum())} h semanales)\n"
        f"• **3 PDFs oficiales EII** integrados\n"
        f"• **Motores:** CP-SAT + Recocido Simulado"
    )
    st.divider()
    st.caption("Equipo: Yone (GII) · Inés (GCID) · María (GIFM)")


# ---------------------------------------------------------------------------
# VISTA 1 (PORTADA INTERACTIVA): EXPLORADOR DE HORARIOS HOMOGÉNEO
# ---------------------------------------------------------------------------
if vista == "🗓️ Explorador de Horarios":
    st.markdown(
        """
        <div class="eii-hero">
            <h1>🗓️ Explorador Interactivo de Horarios — EII ULPGC</h1>
            <p>Experiencia unificada para <b>GII</b>, <b>GCID</b> y <b>GIFM</b>: cuadrícula interactiva con paleta oficial EII, comparativa <b>CP-SAT vs. Recocido Simulado</b> y contraste directo frente a los <b>PDFs oficiales 2026–2027</b>.</p>
            <div class="badge-row">
                <span class="pill">GII · Mañana y Tarde + PDF Oficial</span>
                <span class="pill">GCID · CP-SAT vs SA + PDF Oficial</span>
                <span class="pill">GIFM · Híbrido CP-SAT → SA + PDF Oficial</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Controles superiores idénticos en las 3 titulaciones
    c1, c2, c3 = st.columns([1.8, 1.0, 1.1])
    with c1:
        tit = st.selectbox(
            "Titulación",
            options=["GII", "GCID", "GIFM"],
            format_func=lambda k: f"{k} — {TITULACIONES_INFO[k]['nombre']}",
        )
    with c2:
        curso = st.selectbox("Curso", options=[1, 2, 3, 4], format_func=lambda x: f"{x}º Curso")
    with c3:
        cuatri = st.selectbox(
            "Cuatrimestre",
            options=[1, 2],
            format_func=lambda x: "1er Cuatrimestre" if x == 1 else "2º Cuatrimestre",
        )

    # Selector de Grupo/Turno solo cuando la titulación tiene múltiples grupos principales (GII 1º y 2º)
    gii_opt_sel = None
    gp_filtro = None
    if tit == "GII":
        opciones_gii = obtener_opciones_gii(curso, cuatri)
        if len(opciones_gii) > 1:
            lbls = [o["label"] for o in opciones_gii]
            lbl_sel = st.radio("Grupo / Turno a inspeccionar:", options=lbls, horizontal=True)
            gii_opt_sel = next(o for o in opciones_gii if o["label"] == lbl_sel)
            gp_filtro = gii_opt_sel["gp"]
        elif opciones_gii:
            gii_opt_sel = opciones_gii[0]
            gp_filtro = gii_opt_sel["gp"]

    # Filtrado exacto de catálogo y de horario resuelto (KPIs 100% coherentes con lo mostrado)
    df_cat_sel = df_catalogo[
        (df_catalogo["Titulación"] == tit)
        & (df_catalogo["Curso"] == curso)
        & (df_catalogo["Cuatrimestre"] == cuatri)
    ].copy()
    if gp_filtro is not None:
        df_cat_sel = df_cat_sel[df_cat_sel["Grupo_Principal"] == gp_filtro].copy()

    df_res_sel_all = pd.DataFrame()
    if not df_resueltos.empty:
        df_res_sel_all = df_resueltos[
            (df_resueltos["Titulacion"] == tit)
            & (df_resueltos["Curso"] == curso)
            & (df_resueltos["Cuatrimestre"] == cuatri)
        ].copy()
        if gp_filtro is not None:
            df_res_sel_all = df_res_sel_all[df_res_sel_all["GrupoPrincipal"] == gp_filtro].copy()

    df_res_cp = df_res_sel_all[df_res_sel_all["Metodo"] == "CP-SAT"].copy() if not df_res_sel_all.empty else pd.DataFrame()
    df_res_sa = df_res_sel_all[df_res_sel_all["Metodo"] == "Recocido Simulado"].copy() if not df_res_sel_all.empty else pd.DataFrame()

    # KPIs limpios y reactivos
    n_bloques = len(df_res_cp) if not df_res_cp.empty else len(df_cat_sel)
    horas_sem = int(df_res_cp["DuracionHoras"].sum()) if not df_res_cp.empty else int(df_cat_sel["Horas"].sum())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Sesiones en horario", f"{n_bloques}")
    k2.metric("Horas semanales", f"{horas_sem} h")
    k3.metric("Asignaturas", f"{df_cat_sel['Asignatura'].nunique()}")
    k4.metric("Docentes implicados", f"{df_cat_sel['Profesor'].nunique()}")

    # Notas específicas útiles del grado
    if tit == "GCID" and curso == 3 and cuatri == 2:
        st.info("📌 **3º GCID (2º Cuatri):** Jueves y viernes se mantienen 100% libres para las **Prácticas Externas** en empresa.")
    elif tit == "GCID" and curso == 1:
        st.info("📌 **1º GCID:** Teorías de una misma asignatura en días distintos, máximo 4 h/día por subgrupo y **0 huecos**.")
    elif tit == "GIFM" and curso == 3 and cuatri == 2:
        st.info("📌 **3º GIFM (2º Cuatri):** Alta carga de bloques → activación automática de **jornada ampliada (08:30–16:30)**.")

    # 3 PESTAÑAS LIMPIAS Y 100% HOMOGÉNEAS PARA LAS 3 TITULACIONES
    tab_int, tab_pdf, tab_tab = st.tabs([
        "🗓️ Horario Interactivo (CP-SAT / SA)",
        "📄 Contraste vs. Horario Oficial EII (PDF)",
        "📋 Tabla Detallada y Descargas",
    ])

    def _dibujar_bloques_titulacion(df_g: pd.DataFrame, metodo_lbl: str, filtro_txt: str):
        if df_g.empty:
            st.warning("No hay caché resuelta disponible para esta combinación. Ejecuta `python generar_activos_integracion.py`.")
            return
        for gp_val in sorted(df_g["GrupoPrincipal"].unique().tolist()):
            sub_g = df_g[df_g["GrupoPrincipal"] == gp_val].copy()
            if tit == "GII":
                gp_txt = f"Grupo {gp_val} (Turno de Tarde)" if gp_val == 3 else f"Grupo {gp_val} (Mañana)"
                t_barra = f"{curso}º GII · {cuatri}º Cuatrimestre · {gp_txt} — {metodo_lbl}"
            else:
                t_barra = f"{curso}º {tit} · {cuatri}º Cuatrimestre — {metodo_lbl}"
            st.markdown(renderizar_cuadricula_html(sub_g, t_barra, filtro_texto=filtro_txt), unsafe_allow_html=True)

    # ---- PESTAÑA 1: HORARIO INTERACTIVO Y COMPARATIVA DIRECTA CP-SAT vs SA ----
    with tab_int:
        mostrar_leyenda("eii")
        col_m, col_q = st.columns([1.45, 1.55])
        with col_m:
            met_int = st.radio(
                "Modo de visualización",
                options=["OR-Tools CP-SAT", "Recocido Simulado (SA)", "⚖️ Comparar CP-SAT vs. SA"],
                horizontal=True,
                key="met_int",
            )
        with col_q:
            q_hl = st.text_input(
                "Resaltar asignatura, profesor, aula o subgrupo",
                placeholder="Ej. A2-1, L1-2, Quevedo, G41, FP1...",
                key="q_hl",
            )

        if met_int == "OR-Tools CP-SAT":
            _dibujar_bloques_titulacion(df_res_cp, "OR-Tools CP-SAT (Método Exacto)", q_hl)
        elif met_int == "Recocido Simulado (SA)":
            _dibujar_bloques_titulacion(df_res_sa, "Recocido Simulado (Metaheurística)", q_hl)
        else:
            # Resumen cuantitativo de diferencias entre CP-SAT y SA
            if not df_res_cp.empty and not df_res_sa.empty:
                m_cp = df_res_cp.set_index("Sesion")["Slot"].to_dict()
                m_sa = df_res_sa.set_index("Sesion")["Slot"].to_dict()
                comunes = set(m_cp.keys()) & set(m_sa.keys())
                movidos = sum(1 for k in comunes if m_cp[k] != m_sa[k])

                if tit == "GIFM":
                    p_st = REPO_ROOT / "GIFM" / "resultados" / f"estadisticas_recocido_{curso}GIFM_{cuatri}cuatri.csv"
                    if p_st.exists():
                        r_st = pd.read_csv(p_st, encoding="utf-8-sig").iloc[0]
                        st.info(
                            f"⚖️ **Diferencias CP-SAT vs. SA:** `{movidos}` de `{len(comunes)}` sesiones cambiaron de franja. "
                            f"En GIFM el enfoque es **híbrido (CP-SAT → SA)**: CP-SAT partió de coste `{int(r_st['Coste_inicial'])}` "
                            f"y SA validó `{int(r_st['Aceptados'])}`/{int(r_st['Iteraciones'])} vecinos factibles en `{float(r_st['Tiempo_segundos']):.2f} s` "
                            f"(coste final `{int(r_st['Mejor_coste'])}`)."
                        )
                else:
                    st.info(
                        f"⚖️ **Comparativa directa:** `{movidos}` de `{len(comunes)}` sesiones ocupan distinta franja horaria "
                        "entre **CP-SAT** y **Recocido Simulado** (usa el buscador de arriba para seguir cómo se reubica una asignatura o docente concreto)."
                    )

            st.markdown("#### 🔵 OR-Tools CP-SAT (Método Exacto)")
            _dibujar_bloques_titulacion(df_res_cp, "OR-Tools CP-SAT", q_hl)
            st.markdown("#### 🟠 Recocido Simulado (Metaheurística)")
            _dibujar_bloques_titulacion(df_res_sa, "Recocido Simulado (SA)", q_hl)

    # ---- PESTAÑA 2: CONTRASTE VS HORARIO OFICIAL EII (PDF 2026-2027) ----
    with tab_pdf:
        p_cp, p_sa = obtener_rutas_png(tit, curso, cuatri, gii_opt_sel)
        ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1.3, 1.1])
        with ctrl1:
            met_pdf = st.radio("Propuesta a contrastar:", ["OR-Tools CP-SAT", "Recocido Simulado"], horizontal=True, key="met_pdf")
        with ctrl2:
            disp_pdf = st.radio("Disposición:", ["Apilado (ancho completo)", "Lado a lado"], horizontal=True, key="disp_pdf")
        with ctrl3:
            ver_full_pdf = st.checkbox("Mostrar página entera del PDF (sin recortar)", value=False, key="ver_full_pdf")

        page_idx, default_crop = TITULACIONES_INFO[tit]["pdf_pages"][(curso, cuatri)]
        crop_to_use = "full" if ver_full_pdf else default_crop
        img_pdf = renderizar_pagina_pdf(tit, page_idx, crop_mode=crop_to_use, zoom=2.1)

        if disp_pdf.startswith("Apilado"):
            mostrar_leyenda("eii")
            st.markdown(f"#### ✨ Propuesta Optimizada — {met_pdf}")
            df_pdf_prop = df_res_cp if met_pdf == "OR-Tools CP-SAT" else df_res_sa
            _dibujar_bloques_titulacion(df_pdf_prop, f"Propuesta Optimizada ({met_pdf})", "")
            st.markdown(f"#### 📄 Horario Oficial EII 2026–2027 ({tit})")
            if img_pdf:
                st.image(
                    img_pdf,
                    caption=f"PDF Oficial EII ({TITULACIONES_INFO[tit]['ruta_pdf'].name}) — Página {page_idx + 1}",
                    width="stretch",
                )
            else:
                st.warning("No se pudo renderizar el PDF oficial.")
        else:
            ruta_prop = p_cp if met_pdf == "OR-Tools CP-SAT" else p_sa
            co1, co2 = st.columns(2)
            with co1:
                st.subheader(f"Propuesta Optimizada ({met_pdf})")
                if ruta_prop and ruta_prop.exists():
                    st.image(str(ruta_prop), caption=f"{curso}º {tit} · C{cuatri} ({met_pdf})", width="stretch")
            with co2:
                st.subheader(f"Horario Oficial EII 2026–2027 ({tit})")
                if img_pdf:
                    st.image(
                        img_pdf,
                        caption=f"PDF Oficial EII ({TITULACIONES_INFO[tit]['ruta_pdf'].name}) — Página {page_idx + 1}",
                        width="stretch",
                    )

        with st.expander(f"📖 Ver página oficial de leyenda de siglas ({tit})", expanded=False):
            ley_idx = TITULACIONES_INFO[tit]["pdf_leyenda_idx"]
            img_ley = renderizar_pagina_pdf(tit, ley_idx, crop_mode="full", zoom=1.8)
            if img_ley:
                st.image(img_ley, caption=f"Leyenda oficial de asignaturas — {tit} (Página {ley_idx + 1})", width="stretch")

    # ---- PESTAÑA 3: TABLA DETALLADA Y DESCARGAS (CSV + PNG 300 DPI) ----
    with tab_tab:
        t_met = st.radio("Tabla resuelta del método:", ["OR-Tools CP-SAT", "Recocido Simulado"], horizontal=True, key="t_met")
        df_t = (df_res_cp if t_met == "OR-Tools CP-SAT" else df_res_sa).copy()

        if not df_t.empty:
            ft1, ft2, ft3 = st.columns([1.4, 1.2, 1.4])
            with ft1:
                f_dias = st.multiselect("Día", options=DIAS_ORDEN, default=DIAS_ORDEN, key="t_dias")
            with ft2:
                mods_disp = sorted(df_t["Modalidad"].unique().tolist())
                f_mods = st.multiselect("Modalidad", options=mods_disp, default=mods_disp, key="t_mods")
            with ft3:
                f_q = st.text_input("Buscar asignatura, aula o docente", key="t_q")

            df_t = df_t[df_t["Dia"].isin(f_dias) & df_t["Modalidad"].isin(f_mods)]
            if f_q.strip():
                mask = (
                    df_t["Asignatura"].str.contains(f_q, case=False, na=False)
                    | df_t["Profesor"].str.contains(f_q, case=False, na=False)
                    | df_t["Aula"].str.contains(f_q, case=False, na=False)
                    | df_t["Grupo"].str.contains(f_q, case=False, na=False)
                )
                df_t = df_t[mask]

            df_t = df_t.sort_values(by=["GrupoPrincipal", "Slot", "Asignatura"])
            cols_t = ["Dia", "Hora", "Asignatura", "Modalidad", "Grupo", "Aula", "DuracionHoras", "Profesor", "Semanas"]
            if tit == "GII":
                cols_t.insert(0, "GrupoPrincipal")
            st.dataframe(df_t[cols_t], width="stretch", hide_index=True)

            p_cp, p_sa = obtener_rutas_png(tit, curso, cuatri, gii_opt_sel)
            d1, d2, d3 = st.columns(3)
            with d1:
                st.download_button(
                    "⬇️ Descargar tabla en CSV",
                    data=df_t[cols_t].to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"horario_{tit}_{curso}_C{cuatri}_{t_met.replace(' ', '_')}.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with d2:
                if p_cp and p_cp.exists():
                    st.download_button(
                        "⬇️ Descargar lámina PNG (CP-SAT)",
                        data=p_cp.read_bytes(),
                        file_name=p_cp.name,
                        mime="image/png",
                        width="stretch",
                    )
            with d3:
                if p_sa and p_sa.exists():
                    st.download_button(
                        "⬇️ Descargar lámina PNG (SA)",
                        data=p_sa.read_bytes(),
                        file_name=p_sa.name,
                        mime="image/png",
                        width="stretch",
                    )

        with st.expander(f"📦 Catálogo bruto de sesiones de entrada ({tit} · {curso}º · C{cuatri})", expanded=False):
            cols_cat = ["ID", "Asignatura", "Modalidad", "Grupo", "Horas", "Alumnos", "Tipo_Aula", "Profesor"]
            if tit == "GIFM":
                cols_cat.append("Semanas")
            if tit == "GII":
                cols_cat.insert(4, "Grupo_Principal")
            st.dataframe(df_cat_sel[cols_cat], width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# VISTA 2: VISIÓN GENERAL DE LA ESCUELA (EII)
# ---------------------------------------------------------------------------
elif vista == "🏠 Visión General (EII)":
    st.markdown(
        """
        <div class="eii-hero">
            <h1>🏛️ Visión General — Optimización de Horarios de la EII (ULPGC)</h1>
            <p>Integración unificada de las tres titulaciones de grado impartidas en el Edificio de Informática y Matemáticas para el curso 2026–2027.</p>
            <div class="badge-row">
                <span class="pill">Propuesta D1 · Optimización y Heurística</span>
                <span class="pill">Programación con Restricciones (CP-SAT)</span>
                <span class="pill">Metaheurística Propia (Simulated Annealing)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Titulaciones integradas", "3 Grados", "GII · GCID · GIFM", delta_color="off", delta_arrow="off")
    m2.metric("Sesiones en catálogo", f"{len(df_catalogo)}", "1º a 4º · Ambos cuatris", delta_color="off", delta_arrow="off")
    m3.metric("Carga lectiva semanal", f"{int(df_catalogo['Horas'].sum())} h", "Teoría, Aula y Lab", delta_color="off", delta_arrow="off")
    m4.metric("Espacios docentes EII", f"{len(df_aulas)}", "12 Teoría · 15 Labs", delta_color="off", delta_arrow="off")
    m5.metric("Factibilidad alcanzada", "100 %", "0 choques duros", delta_color="normal", delta_arrow="off")

    st.markdown("### Arquitectura por Titulación")
    col_cards = st.columns(3)
    for col, deg in zip(col_cards, ["GII", "GCID", "GIFM"]):
        info = TITULACIONES_INFO[deg]
        sub = df_catalogo[df_catalogo["Titulación"] == deg]
        with col:
            st.markdown(
                f"""
                <div class="info-card" style="border-top: 4px solid {info['color']};">
                    <h4>{deg} — {info['nombre']}</h4>
                    <p><b>Responsable:</b> {info['autor']} &nbsp;|&nbsp; <b>Sesiones:</b> {len(sub)} ({int(sub['Horas'].sum())} h)</p>
                    <p><b>Estrategia:</b> {info['estrategia']}</p>
                    <p><b>Particularidades:</b> {info['particularidades']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### Radiografía de la Carga Docente Integrada")
    g1, g2 = st.columns(2)
    with g1:
        res_mod = (
            df_catalogo.groupby(["Titulación", "Modalidad"], as_index=False)
            .agg(Sesiones=("ID", "count"), Horas=("Horas", "sum"))
        )
        fig_mod = px.bar(
            res_mod,
            x="Titulación",
            y="Sesiones",
            color="Modalidad",
            barmode="stack",
            text="Sesiones",
            title="Distribución de Sesiones por Titulación y Modalidad",
            color_discrete_map={
                "Teoría": "#F59E0B",
                "Práctica de Aula": "#0288D1",
                "Laboratorio": "#16A34A",
            },
        )
        fig_mod.update_layout(height=390, margin=dict(t=50, b=20, l=20, r=20), legend_title_text="Modalidad")
        st.plotly_chart(fig_mod, width="stretch")

    with g2:
        res_curso = (
            df_catalogo.groupby(["Titulación", "Curso"], as_index=False)
            .agg(Horas=("Horas", "sum"), Sesiones=("ID", "count"))
        )
        res_curso["Curso_lbl"] = res_curso["Curso"].astype(str) + "º Curso"
        fig_cur = px.bar(
            res_curso,
            x="Curso_lbl",
            y="Horas",
            color="Titulación",
            barmode="group",
            text="Horas",
            title="Carga Horaria Semanal por Curso y Titulación",
            color_discrete_map={k: v["color"] for k, v in TITULACIONES_INFO.items()},
        )
        fig_cur.update_layout(height=390, xaxis_title="Curso académico", yaxis_title="Horas semanales", margin=dict(t=50, b=20, l=20, r=20))
        st.plotly_chart(fig_cur, width="stretch")

    st.markdown("### Tabla Consolidada de las 3 Titulaciones")
    resumen_global = pd.DataFrame([
        {
            "Titulación": f"{deg} ({TITULACIONES_INFO[deg]['nombre']})",
            "Cursos": "1º – 4º (S1 y S2)",
            "Sesiones CSV": int((df_catalogo["Titulación"] == deg).sum()),
            "Bloques Horario": int(((df_resueltos["Titulacion"] == deg) & (df_resueltos["Metodo"] == "CP-SAT")).sum()) if not df_resueltos.empty else "-",
            "Horas/Sem": int(df_catalogo.loc[df_catalogo["Titulación"] == deg, "Horas"].sum()),
            "Asignaturas": int(df_catalogo.loc[df_catalogo["Titulación"] == deg, "Asignatura"].nunique()),
            "Docentes": int(df_catalogo.loc[df_catalogo["Titulación"] == deg, "Profesor"].nunique()),
            "Cobertura Visual": "CP-SAT + SA + PDF Oficial",
            "Factibilidad": "100%",
        }
        for deg in ["GII", "GCID", "GIFM"]
    ])
    st.dataframe(resumen_global, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# VISTA 3: RESULTADOS EXPERIMENTALES Y CONVERGENCIA
# ---------------------------------------------------------------------------
elif vista == "📊 Resultados y Convergencia":
    st.markdown(
        """
        <div class="eii-hero">
            <h1>📊 Resultados Experimentales y Convergencia (CP-SAT vs. Recocido Simulado)</h1>
            <p>Análisis riguroso de calidad de solución, factibilidad, tiempos de cómputo y dinámica térmica del Recocido Simulado en las tres titulaciones.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_gii, tab_gcid, tab_gifm, tab_comp = st.tabs([
        "🔵 GII (Benchmark Multi-Semilla)",
        "🟢 GCID (CP-SAT vs. SA Global)",
        "🟠 GIFM (Pipeline Híbrido CP-SAT → SA)",
        "⚖️ Síntesis Comparativa Global",
    ])

    with tab_gii:
        df_b = cargar_benchmark_gii()
        if not df_b.empty:
            resumen_gii = (
                df_b.groupby(["instancia", "metodo"], as_index=False)
                .agg(
                    Sesiones=("num_sesiones", "first"),
                    Tiempo_Medio_s=("tiempo_seg", "mean"),
                    Tiempo_Std=("tiempo_seg", "std"),
                    Energia_Media=("energia", "mean"),
                    Energia_Std=("energia", "std"),
                    Violaciones_Duras=("duras", "mean"),
                    Coste_Huecos=("blandas", "mean"),
                    Factibilidad_Pct=("factible", lambda s: 100.0 * s.mean()),
                )
            )
            resumen_gii["Instancia_Corta"] = resumen_gii["instancia"].str.replace(" - Semestre 1 (Grupo 1)", " (S1)", regex=False)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Factibilidad Búsqueda Aleatoria", "0.0 %", "6–16 choques duros", delta_color="inverse", delta_arrow="off")
            k2.metric("Factibilidad CP-SAT & SA", "100.0 %", "0 violaciones duras", delta_color="normal", delta_arrow="off")
            k3.metric("Reducción de huecos (SA vs CP-SAT)", "56% – 100%", "0 pts en 1º GII", delta_color="normal", delta_arrow="off")
            k4.metric("Tiempo medio de ejecución", "1.4 – 5.1 s", "5 semillas independientes", delta_color="off", delta_arrow="off")

            c_ch1, c_ch2 = st.columns(2)
            with c_ch1:
                solo_factibles = st.checkbox("Ocultar Búsqueda Aleatoria (ver detalle de huecos CP-SAT vs SA)", value=True)
                df_plot = resumen_gii[resumen_gii["metodo"] != "Búsqueda Aleatoria (Baseline)"] if solo_factibles else resumen_gii
                fig_e = px.bar(
                    df_plot,
                    x="Instancia_Corta",
                    y="Energia_Media",
                    error_y="Energia_Std",
                    color="metodo",
                    barmode="group",
                    text=df_plot["Energia_Media"].round(1),
                    title="Calidad de Solución — Energía / Coste (menor es mejor)",
                    color_discrete_map={
                        "Búsqueda Aleatoria (Baseline)": "#64748B",
                        "OR-Tools CP-SAT (Exacto)": "#16A34A",
                        "Recocido Simulado (Propio)": "#F59E0B",
                    },
                )
                fig_e.update_layout(height=380, xaxis_title="Instancia GII", yaxis_title="Energía media (pts)", legend_title_text="Método")
                st.plotly_chart(fig_e, width="stretch")

            with c_ch2:
                fig_t = px.bar(
                    resumen_gii,
                    x="Instancia_Corta",
                    y="Tiempo_Medio_s",
                    error_y="Tiempo_Std",
                    color="metodo",
                    barmode="group",
                    text=resumen_gii["Tiempo_Medio_s"].round(2),
                    title="Eficiencia Computacional — Tiempo Medio (s)",
                    color_discrete_map={
                        "Búsqueda Aleatoria (Baseline)": "#64748B",
                        "OR-Tools CP-SAT (Exacto)": "#16A34A",
                        "Recocido Simulado (Propio)": "#F59E0B",
                    },
                )
                fig_t.update_layout(height=380, xaxis_title="Instancia GII", yaxis_title="Tiempo (segundos)", legend_title_text="Método")
                st.plotly_chart(fig_t, width="stretch")

            st.markdown("#### Tabla Experimental GII (Media y Desviación Típica sobre 5 Semillas)")
            st.dataframe(
                resumen_gii[[
                    "Instancia_Corta", "metodo", "Sesiones", "Tiempo_Medio_s", "Tiempo_Std",
                    "Energia_Media", "Energia_Std", "Violaciones_Duras", "Coste_Huecos", "Factibilidad_Pct"
                ]].round(2),
                width="stretch",
                hide_index=True,
            )

        st.markdown("#### Curva de Convergencia Térmica del Recocido Simulado (GII)")
        p_conv_gii = REPO_ROOT / "GII" / "memoria" / "curva_convergencia_sa.png"
        if p_conv_gii.exists():
            st.image(str(p_conv_gii), caption="Evolución de Energía, Temperatura y Tasa de Aceptación (3º GII · 24.300 iteraciones)", width="stretch")

    with tab_gcid:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Sesiones globales optimizadas", "150", "86 en S1 · 64 en S2", delta_color="off", delta_arrow="off")
        k2.metric("Choques duros y huecos", "0 / 0", "Tanto en CP-SAT como en SA", delta_color="normal", delta_arrow="off")
        k3.metric("Penalización blanda (1er Sem.)", "85 vs 160", "CP-SAT óptimo vs SA", delta_color="off", delta_arrow="off")
        k4.metric("Penalización blanda (2º Sem.)", "25 vs 150", "CP-SAT óptimo vs SA", delta_color="off", delta_arrow="off")

        c1, c2 = st.columns(2)
        with c1:
            fig_gcid_p = px.bar(
                GCID_BENCHMARK,
                x="Cuatrimestre",
                y="Penalizacion_Blanda",
                color="Metodo",
                barmode="group",
                text="Penalizacion_Blanda",
                title="GCID — Penalización Blanda Final (menor es mejor)",
                color_discrete_map={"OR-Tools CP-SAT": "#0F766E", "Recocido Simulado": "#F59E0B"},
            )
            fig_gcid_p.update_layout(height=360, yaxis_title="Penalización blanda (pts)")
            st.plotly_chart(fig_gcid_p, width="stretch")

        with c2:
            fig_gcid_t = px.bar(
                GCID_BENCHMARK,
                x="Cuatrimestre",
                y="Tiempo_s",
                color="Metodo",
                barmode="group",
                text="Tiempo_s",
                title="GCID — Tiempo de Ejecución Global (4 cursos simultáneos)",
                color_discrete_map={"OR-Tools CP-SAT": "#0F766E", "Recocido Simulado": "#F59E0B"},
            )
            fig_gcid_t.update_layout(height=360, yaxis_title="Tiempo (segundos)")
            st.plotly_chart(fig_gcid_t, width="stretch")

        st.dataframe(GCID_BENCHMARK, width="stretch", hide_index=True)

        st.markdown("#### Curvas de Convergencia del Recocido Simulado (GCID · 60.000 iteraciones)")
        g_left, g_right = st.columns(2)
        p_c1 = REPO_ROOT / "GCID" / "graficas" / "convergencia_SA_1er.png"
        p_c2 = REPO_ROOT / "GCID" / "graficas" / "convergencia_SA_2do.png"
        with g_left:
            if p_c1.exists():
                st.image(str(p_c1), caption="GCID — Convergencia 1er Semestre", width="stretch")
        with g_right:
            if p_c2.exists():
                st.image(str(p_c2), caption="GCID — Convergencia 2º Semestre", width="stretch")

    with tab_gifm:
        df_gifm = cargar_estadisticas_gifm()
        if not df_gifm.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Instancias resueltas", f"{len(df_gifm)} / 8", "1º a 4º · Ambos cuatris", delta_color="off", delta_arrow="off")
            k2.metric("Horarios válidos", f"{int(df_gifm['Horario_valido'].sum())} / {len(df_gifm)}", "100% Factibles", delta_color="normal", delta_arrow="off")
            k3.metric("Coste medio final", f"{df_gifm['Mejor_coste'].mean():.2f}", "0 en 7 de 8 instancias", delta_color="off", delta_arrow="off")
            k4.metric("Tiempo medio SA", f"{df_gifm['Tiempo_segundos'].mean():.2f} s", f"Máx: {df_gifm['Tiempo_segundos'].max():.2f} s (3º C2)", delta_color="off", delta_arrow="off")

            c1, c2 = st.columns(2)
            with c1:
                fig_gt = px.bar(
                    df_gifm,
                    x="Instancia",
                    y="Tiempo_segundos",
                    text=df_gifm["Tiempo_segundos"].round(2),
                    title="GIFM — Tiempo de Ejecución del Recocido Simulado (1.000 iter.)",
                    color="Curso",
                    color_continuous_scale="Blues",
                )
                fig_gt.update_layout(height=370, yaxis_title="Tiempo (s)", coloraxis_showscale=False)
                st.plotly_chart(fig_gt, width="stretch")

            with c2:
                fig_ga = px.bar(
                    df_gifm,
                    x="Instancia",
                    y="Aceptados",
                    text="Aceptados",
                    title="GIFM — Movimientos Aceptados en el Vecindario SA (de 1.000 iter.)",
                    color_discrete_sequence=["#B45309"],
                )
                fig_ga.update_layout(height=370, yaxis_title="Movimientos aceptados")
                st.plotly_chart(fig_ga, width="stretch")

            st.info(
                "💡 **Lectura técnica del enfoque híbrido en GIFM:** Al inicializar el Recocido Simulado "
                "a partir de la solución ya optimizada por CP-SAT, el coste inicial parte en `0` en 7 de las 8 instancias "
                "(y `10` en 3º C2 con jornada ampliada), validando que CP-SAT alcanza directamente el óptimo blando "
                "mientras SA explora miles de permutaciones vecinas válidas sin degradar la solución."
            )
            st.dataframe(
                df_gifm[[
                    "Instancia", "Algoritmo", "Coste_inicial", "Mejor_coste",
                    "Iteraciones", "Aceptados", "Mejoras", "Tiempo_segundos", "Horario_valido"
                ]].round(3),
                width="stretch",
                hide_index=True,
            )

    with tab_comp:
        st.markdown("#### Comparativa Arquitectónica de los Motores de Optimización")
        df_arch = pd.DataFrame([
            {
                "Titulación": "GII",
                "Alcance de resolución": "Por curso, semestre y turno (Mañana G1+G2 acoplados / Tarde G3)",
                "CP-SAT": "Resolución exacta (<1.6 s) con minimización de huecos y viernes",
                "Recocido Simulado": "Desde solución aleatoria (Python puro, ~24.300 iter., 5 semillas)",
                "Hallazgo clave": "SA propio supera a CP-SAT en compactación de huecos (0–61 vs 140–270 pts)",
            },
            {
                "Titulación": "GCID",
                "Alcance de resolución": "Global por cuatrimestre (4 cursos simultáneos compartiendo aulas)",
                "CP-SAT": "Óptimo global exacto (4.8–10.8 s, 0 huecos duros, penalización 25–85)",
                "Recocido Simulado": "Desde solución aleatoria (60.000 iter., 9.5–11.1 s, 0 choques y 0 huecos)",
                "Hallazgo clave": "Ambos alcanzan 0 choques y 0 huecos; CP-SAT afina mejor las preferencias blandas",
            },
            {
                "Titulación": "GIFM",
                "Alcance de resolución": "Por curso y cuatrimestre con desglose en bloques y semanas activas",
                "CP-SAT": "Solución factible/óptima con ampliación automática en 3º C2 (08:30–16:30)",
                "Recocido Simulado": "Híbrido (parte del horario CP-SAT y explora 1.000 vecinos factibles)",
                "Hallazgo clave": "100% de horarios válidos en los 8 casos, coste 0 en 7/8 instancias",
            },
        ])
        st.dataframe(df_arch, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# VISTA 4: SIMULADOR EN VIVO (DEMO EN CLASE)
# ---------------------------------------------------------------------------
elif vista == "⚡ Simulador en Vivo":
    st.markdown(
        """
        <div class="eii-hero">
            <h1>⚡ Simulador de Optimización en Vivo</h1>
            <p>Ejecuta en directo el motor exacto (<b>CP-SAT</b>) o la metaheurística de <b>Recocido Simulado</b> sobre cualquier titulación sin modificar los archivos del repositorio.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns([1.3, 1.1, 1.0, 1.0])
    with c1:
        sim_tit = st.selectbox(
            "Titulación a optimizar",
            options=["GII", "GCID", "GIFM"],
            format_func=lambda k: f"{k} — {TITULACIONES_INFO[k]['nombre']}",
            key="sim_tit",
        )
    with c2:
        sim_metodo = st.selectbox(
            "Motor de optimización",
            options=["SA", "CP-SAT"],
            format_func=lambda m: "Recocido Simulado (SA)" if m == "SA" else "OR-Tools CP-SAT (Exacto)",
            key="sim_met",
        )
    with c3:
        sim_curso = st.selectbox("Curso", options=[1, 2, 3, 4], index=2 if sim_tit == "GII" else 0, format_func=lambda x: f"{x}º", key="sim_cur")
    with c4:
        sim_cuatri = st.selectbox("Cuatrimestre", options=[1, 2], format_func=lambda x: f"{x}º Cuatri", key="sim_cua")

    sim_gp = 1
    if sim_tit == "GII":
        gps_disp = sorted(
            df_catalogo[
                (df_catalogo["Titulación"] == "GII")
                & (df_catalogo["Curso"] == sim_curso)
                & (df_catalogo["Cuatrimestre"] == sim_cuatri)
            ]["Grupo_Principal"].unique().tolist()
        )
        if len(gps_disp) > 1:
            sim_gp = st.radio(
                "Grupo Principal (GII)",
                options=gps_disp,
                format_func=lambda g: f"Grupo {g} (Tarde)" if g == 3 else f"Grupo {g} (Mañana)",
                horizontal=True,
            )
        elif gps_disp:
            sim_gp = int(gps_disp[0])

    t_inicial, alpha, iter_por_temp, max_iter, semilla = 120.0, 0.985, 140, 60000, 42
    if sim_metodo == "SA":
        with st.expander("🎛️ Parámetros del Recocido Simulado (ajustables para la demo)", expanded=True):
            p1, p2, p3, p4 = st.columns(4)
            if sim_tit == "GII":
                t_inicial = p1.slider("Temperatura inicial (T₀)", 40.0, 200.0, 120.0, 10.0)
                alpha = p2.slider("Factor enfriamiento (α)", 0.950, 0.995, 0.985, 0.005, format="%.3f")
                iter_por_temp = p3.slider("Iteraciones / escalón (L)", 60, 200, 140, 20)
                semilla = int(p4.number_input("Semilla aleatoria", min_value=1, max_value=9999, value=42, step=1))
            elif sim_tit == "GCID":
                max_iter = p1.slider("Iteraciones SA (4 cursos globales)", 15000, 60000, 60000, 5000)
                semilla = int(p2.number_input("Semilla aleatoria", min_value=1, max_value=9999, value=42, step=1))
                p3.info("T₀ = 5000 → T_f = 0.1 (enfriamiento geométrico)")
                p4.info("Optimiza los 4 cursos del cuatrimestre a la vez.")
            else:
                t_inicial = p1.slider("Temperatura inicial (T₀)", 5.0, 50.0, 10.0, 5.0)
                alpha = p2.slider("Factor enfriamiento (α)", 0.950, 0.999, 0.995, 0.005, format="%.3f")
                max_iter = p3.slider("Iteraciones SA", 200, 2000, 1000, 200)
                semilla = int(p4.number_input("Semilla aleatoria", min_value=1, max_value=9999, value=42, step=1))

    lanzar = st.button("🚀 Ejecutar optimización en vivo", type="primary", width="stretch")

    if lanzar:
        with st.spinner(f"Ejecutando {sim_metodo} para {sim_curso}º {sim_tit} ({sim_cuatri}º cuatrimestre)..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    sys.executable,
                    str(REPO_ROOT / "live_runner.py"),
                    "--titulacion", sim_tit,
                    "--metodo", sim_metodo,
                    "--curso", str(sim_curso),
                    "--cuatrimestre", str(sim_cuatri),
                    "--grupo_principal", str(sim_gp),
                    "--t_inicial", str(t_inicial),
                    "--alpha", str(alpha),
                    "--iter_por_temp", str(iter_por_temp),
                    "--max_iter", str(max_iter),
                    "--semilla", str(semilla),
                    "--out_dir", tmpdir,
                ]
                proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180)
                if proc.returncode != 0:
                    st.error("Ocurrió un error al ejecutar la simulación en vivo.")
                    st.code(proc.stderr or proc.stdout)
                else:
                    summary = json.loads((Path(tmpdir) / "summary.json").read_text(encoding="utf-8"))
                    png_bytes = Path(summary["png_principal"]).read_bytes()
                    csv_text = Path(summary["csv_principal"]).read_text(encoding="utf-8-sig")
                    png_cp_bytes = None
                    if "png_comparativa_cp" in summary and Path(summary["png_comparativa_cp"]).exists():
                        png_cp_bytes = Path(summary["png_comparativa_cp"]).read_bytes()

                    st.session_state["live_result"] = {
                        "summary": summary,
                        "png_bytes": png_bytes,
                        "png_cp_bytes": png_cp_bytes,
                        "csv_text": csv_text,
                        "df": pd.read_csv(Path(summary["csv_principal"]), encoding="utf-8-sig"),
                    }

    if "live_result" in st.session_state:
        res = st.session_state["live_result"]
        s = res["summary"]
        st.success(
            f"Optimización completada para **{s['curso']}º {s['titulacion']} (C{s['cuatrimestre']})** "
            f"mediante **{s['metodo']}** en **{s['tiempo_s']:.2f} s**."
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Tiempo de cómputo", f"{s['tiempo_s']:.2f} s")
        k2.metric("Violaciones duras", f"{s['violaciones_duras']}", "Factible" if s["factible"] else "Revisar", delta_color="normal" if s["factible"] else "inverse", delta_arrow="off")
        k3.metric("Coste blando / Energía", f"{s['coste_blando']:.1f}")
        k4.metric("Sesiones ubicadas", f"{s['sesiones']}")

        hist = s.get("historial") or []
        if hist:
            df_h = pd.DataFrame(hist)
            st.markdown("#### Curva de Convergencia Generada en Directo")
            fig_live = make_subplots(specs=[[{"secondary_y": True}]])
            fig_live.add_trace(
                go.Scatter(
                    x=df_h["iteracion"],
                    y=df_h["energia_actual"],
                    name="Energía actual (exploración)",
                    line=dict(color="#93C5FD", width=1.4),
                    opacity=0.75,
                ),
                secondary_y=False,
            )
            fig_live.add_trace(
                go.Scatter(
                    x=df_h["iteracion"],
                    y=df_h["mejor_energia"],
                    name="Mejor energía (E*)",
                    line=dict(color="#0F2952", width=2.8),
                ),
                secondary_y=False,
            )
            if "temperatura" in df_h.columns:
                fig_live.add_trace(
                    go.Scatter(
                        x=df_h["iteracion"],
                        y=df_h["temperatura"],
                        name="Temperatura (T)",
                        line=dict(color="#DC2626", width=1.8, dash="dot"),
                    ),
                    secondary_y=True,
                )
            fig_live.update_layout(
                height=360,
                xaxis_title="Iteración",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=40, b=20, l=20, r=20),
            )
            fig_live.update_yaxes(title_text="Energía / Coste", secondary_y=False)
            fig_live.update_yaxes(title_text="Temperatura (T)", secondary_y=True)
            st.plotly_chart(fig_live, width="stretch")

        st.markdown("#### Horario Generado en Directo")
        if res["png_cp_bytes"] is not None:
            col_a, col_b = st.columns(2)
            with col_a:
                st.image(res["png_cp_bytes"], caption="Paso 1: Solución inicial CP-SAT", width="stretch")
            with col_b:
                st.image(res["png_bytes"], caption="Paso 2: Refinamiento Recocido Simulado", width="stretch")
        else:
            st.image(res["png_bytes"], width="stretch")

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "⬇️ Descargar PNG generado",
                data=res["png_bytes"],
                file_name=f"live_{s['titulacion']}_{s['curso']}_C{s['cuatrimestre']}.png",
                mime="image/png",
                width="stretch",
            )
        with dl2:
            st.download_button(
                "⬇️ Descargar tabla CSV generada",
                data=res["csv_text"],
                file_name=f"live_{s['titulacion']}_{s['curso']}_C{s['cuatrimestre']}.csv",
                mime="text/csv",
                width="stretch",
            )

        with st.expander("📋 Ver asignaciones exactas (Día, Hora, Aula, Profesor)", expanded=False):
            st.dataframe(res["df"], width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# VISTA 5: MODELO MATEMÁTICO, AULAS Y CATÁLOGO UNIFICADO
# ---------------------------------------------------------------------------
else:
    st.markdown(
        """
        <div class="eii-hero">
            <h1>📚 Formulación Matemática, Infraestructura EII y Catálogo Unificado</h1>
            <p>Marco matemático común de las tres titulaciones (UCTP), catálogo físico de aulas y buscador global de sesiones y profesorado.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_mod, tab_aulas, tab_busq = st.tabs([
        "📐 Formulación Matemática Común",
        "🏫 Espacios y Aulas EII",
        "🔎 Buscador Global de Sesiones y Docentes",
    ])

    with tab_mod:
        st.markdown("#### 1. Variables de Decisión y Espacio Combinatorio")
        st.markdown(
            "El problema de planificación horaria universitaria (*University Course Timetabling Problem*, UCTP — NP-hard) "
            "se modela asignando a cada sesión docente $s \\in S$ una franja horaria de inicio $t \\in T$ "
            "y un aula compatible $r \\in R$:"
        )
        st.latex(r"X_{s, t, r} \in \{0, 1\} \quad \forall s \in S, \; t \in T, \; r \in R \qquad\Longrightarrow\qquad |\Omega| = (|T| \times |R|)^{|S|}")

        col_h, col_s = st.columns(2)
        with col_h:
            st.markdown("#### 2. Restricciones Duras Comunes (Inviolables)")
            st.markdown(
                """
                1. **Cobertura única:** cada sesión se imparte exactamente una vez.
                2. **No solapamiento docente:** ningún profesor puede impartir dos clases simultáneas.
                3. **Jerarquía y no colisión de alumnado:** un grupo de teoría bloquea a todos sus subgrupos de aula/laboratorio.
                4. **Compatibilidad y aforo de aulas:** teoría → aula de teoría; prácticas → laboratorio (o `LF-4` para Física) con capacidad suficiente.
                5. **Exclusividad física de aula:** como máximo una sesión por aula y franja.
                6. **Continuidad diaria:** ninguna sesión de varias horas puede partirse entre dos días distintos.
                """
            )
        with col_s:
            st.markdown("#### 3. Restricciones Blandas y Función Objetivo")
            st.latex(r"\min \; \Phi(X) = W_{\text{duras}} \cdot N_{\text{duras}}(X) + w_{\text{huecos}} \cdot C_{\text{huecos}}(X) + w_{\text{viernes}} \cdot C_{\text{viernes}}(X) + w_{\text{aula}} \cdot C_{\text{aula}}(X)")
            st.markdown(
                """
                * **Compactación diaria:** minimizar horas muertas (huecos) entre clases de cada subgrupo *(o exigir 0 huecos como restricción dura en GCID)*.
                * **Calidad del viernes:** penalizar sesiones en los últimos turnos del viernes.
                * **Estabilidad espacial:** priorizar aula de referencia para teoría (`A2-5` en GCID, `A3-1` en GIFM).
                * **Reglas específicas integradas:** turno de tarde en 1º GII (Grupo 3), jueves/viernes libres de prácticas externas en 3º GCID S2, y jornada ampliable en 3º GIFM S2.
                """
            )

    with tab_aulas:
        c1, c2 = st.columns([1.6, 1.0])
        with c1:
            fig_a = px.bar(
                df_aulas.sort_values("capacidad", ascending=True),
                x="capacidad",
                y="nombre",
                color="tipo",
                orientation="h",
                text="capacidad",
                title="Catálogo de Espacios Físicos de la EII (Capacidad y Tipología)",
                color_discrete_map={"Teoria": "#1E40AF", "Laboratorio": "#16A34A"},
            )
            fig_a.update_layout(height=620, xaxis_title="Capacidad (alumnos)", yaxis_title="", legend_title_text="Tipo de espacio")
            st.plotly_chart(fig_a, width="stretch")
        with c2:
            st.markdown("#### Resumen de Aforo")
            st.metric("Aulas de Teoría", f"{int((df_aulas['tipo'] == 'Teoria').sum())}", f"Cap. total: {int(df_aulas.loc[df_aulas['tipo'] == 'Teoria', 'capacidad'].sum())} plazas", delta_color="off", delta_arrow="off")
            st.metric("Laboratorios", f"{int((df_aulas['tipo'] == 'Laboratorio').sum())}", f"Cap. total: {int(df_aulas.loc[df_aulas['tipo'] == 'Laboratorio', 'capacidad'].sum())} plazas", delta_color="off", delta_arrow="off")
            st.dataframe(df_aulas, width="stretch", hide_index=True, height=400)

    with tab_busq:
        f1, f2, f3, f4 = st.columns([1.2, 1.0, 1.0, 1.8])
        with f1:
            f_tits = st.multiselect("Titulación", options=["GII", "GCID", "GIFM"], default=["GII", "GCID", "GIFM"])
        with f2:
            f_cursos = st.multiselect("Curso", options=[1, 2, 3, 4], default=[1, 2, 3, 4])
        with f3:
            f_mods = st.multiselect("Modalidad", options=["Teoría", "Práctica de Aula", "Laboratorio"], default=["Teoría", "Práctica de Aula", "Laboratorio"])
        with f4:
            f_texto = st.text_input("Filtrar por profesor o asignatura", placeholder="Ej. Quevedo, AL, BD, FFI...")

        df_f = df_catalogo[
            df_catalogo["Titulación"].isin(f_tits)
            & df_catalogo["Curso"].isin(f_cursos)
            & df_catalogo["Modalidad"].isin(f_mods)
        ].copy()
        if f_texto.strip():
            m = (
                df_f["Profesor"].str.contains(f_texto, case=False, na=False)
                | df_f["Asignatura"].str.contains(f_texto, case=False, na=False)
            )
            df_f = df_f[m]

        st.caption(f"Mostrando **{len(df_f)} sesiones** ({int(df_f['Horas'].sum())} horas totales) · **{df_f['Profesor'].nunique()} docentes**")
        st.dataframe(
            df_f[["Titulación", "Curso", "Cuatrimestre", "ID", "Asignatura", "Modalidad", "Grupo", "Horas", "Alumnos", "Tipo_Aula", "Profesor"]],
            width="stretch",
            hide_index=True,
            height=450,
        )
