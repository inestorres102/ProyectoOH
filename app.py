"""
Cuadro de Mandos Interactivo — Planificación Automática de Horarios EII (ULPGC)
Proyecto de Optimización y Heurística (Curso 2026-2027)

Integra en una única aplicación interactiva las tres titulaciones de la Escuela:
- GII  (Grado en Ingeniería Informática)
- GCID (Grado en Ciencia e Ingeniería de Datos)
- GIFM (Grado en Ingeniería Física y Matemática)
"""

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
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


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
    },
}

GII_PDF_PAGES = {
    (1, 1): 0,
    (1, 2): 1,
    (2, 1): 2,
    (2, 2): 3,
    (3, 1): 4,
    (3, 2): 5,
    (4, 1): 6,
}

GCID_CARPETA_CURSO = {1: "primero", 2: "segundo", 3: "tercero", 4: "cuarto"}

# Resultados experimentales oficiales documentados en GCID/README.md
GCID_BENCHMARK = pd.DataFrame([
    {"Cuatrimestre": "1er Semestre", "Metodo": "OR-Tools CP-SAT", "Sesiones": 86, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 85, "Tiempo_s": 10.78},
    {"Cuatrimestre": "1er Semestre", "Metodo": "Recocido Simulado", "Sesiones": 86, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 160, "Tiempo_s": 11.08},
    {"Cuatrimestre": "2º Semestre", "Metodo": "OR-Tools CP-SAT", "Sesiones": 64, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 25, "Tiempo_s": 4.77},
    {"Cuatrimestre": "2º Semestre", "Metodo": "Recocido Simulado", "Sesiones": 64, "Choques": 0, "Huecos": 0, "Penalizacion_Blanda": 150, "Tiempo_s": 9.45},
])


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
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }
    .eii-hero {
        background: linear-gradient(125deg, #0B1F42 0%, #153A75 58%, #1D4ED8 100%);
        color: #FFFFFF;
        padding: 1.4rem 1.8rem;
        border-radius: 14px;
        margin-bottom: 1.25rem;
        box-shadow: 0 8px 24px rgba(15, 41, 82, 0.16);
    }
    .eii-hero h1 {
        margin: 0 0 0.35rem 0;
        font-size: 1.75rem;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: -0.02em;
    }
    .eii-hero p {
        margin: 0;
        color: #DBEAFE;
        font-size: 0.96rem;
    }
    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.85rem;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        border: 1px solid rgba(255,255,255,0.22);
        background: rgba(255,255,255,0.12);
        color: #FFFFFF;
    }
    .legend-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        align-items: center;
        margin: 0.4rem 0 0.9rem 0;
    }
    .leg-item {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.22rem 0.68rem;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    .leg-teoria { background: #FFF9C4; color: #E65100; border: 1.5px solid #FBC02D; }
    .leg-aula   { background: #E1F5FE; color: #01579B; border: 1.5px solid #0288D1; }
    .leg-lab    { background: #C8E6C9; color: #1B5E20; border: 1.5px solid #43A047; }
    .info-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1rem 1.15rem;
        box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
        height: 100%;
    }
    .info-card h4 {
        margin: 0 0 0.45rem 0;
        color: #0F2952;
        font-size: 1.02rem;
    }
    .info-card p {
        margin: 0.25rem 0;
        font-size: 0.88rem;
        color: #334155;
        line-height: 1.45;
    }
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 0.85rem 1rem;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
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
    filas = []
    for f in sorted(carpeta.glob("estadisticas_recocido_*.csv")):
        filas.append(pd.read_csv(f, encoding="utf-8-sig"))
    if not filas:
        return pd.DataFrame()
    df = pd.concat(filas, ignore_index=True)
    df["Instancia"] = df.apply(lambda r: f"{int(r['Curso'])}º GIFM · C{int(r['Cuatrimestre'])}", axis=1)
    return df


@st.cache_data(show_spinner=False)
def renderizar_pagina_pdf_gii(page_idx: int, zoom: float = 2.0) -> bytes | None:
    pdf_path = REPO_ROOT / "GII" / "horario_GII_2026_2027.pdf"
    if not HAS_PYMUPDF or not pdf_path.exists():
        return None
    doc = pymupdf.open(str(pdf_path))
    if page_idx < 0 or page_idx >= len(doc):
        doc.close()
        return None
    page = doc.load_page(page_idx)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def obtener_opciones_gii(curso: int, cuatrimestre: int) -> dict[str, Path]:
    sem_dir = "1er_Semestre" if cuatrimestre == 1 else "2do_Semestre"
    carpeta = REPO_ROOT / "GII" / "horarios" / f"{curso}GII" / sem_dir
    opciones = {}
    orden = [
        ("Vista Conjunta (Mañana: G1 + G2)", "horario_conjunto.png"),
        ("Grupo 1 (Mañana)", "horario_Grupo_1.png"),
        ("Grupo 2 (Mañana)", "horario_Grupo_2.png"),
        ("Grupo 3 (Turno de Tarde)", "horario_Grupo_3.png"),
    ]
    for label, fname in orden:
        p = carpeta / fname
        if p.exists():
            opciones[label] = p
    return opciones


def obtener_rutas_gcid(curso: int, cuatrimestre: int) -> tuple[Path, Path]:
    c_dir = GCID_CARPETA_CURSO[curso]
    sem = "1er" if cuatrimestre == 1 else "2do"
    p_cp = REPO_ROOT / "GCID" / "horarios_CP-SAT" / c_dir / f"horario_{curso}GCID_{sem}.png"
    p_sa = REPO_ROOT / "GCID" / "horarios_metaheuristica" / c_dir / f"horario_SA_{curso}GCID_{sem}.png"
    return p_cp, p_sa


def obtener_rutas_gifm(curso: int, cuatrimestre: int) -> tuple[Path, Path, Path, Path]:
    base = REPO_ROOT / "GIFM" / "resultados"
    p_cp = base / f"horario_{curso}GIFM_{cuatrimestre}cuatri.png"
    p_sa = base / f"horario_{curso}GIFM_{cuatrimestre}cuatri_recocido.png"
    p_csv = base / f"horario_{curso}GIFM_{cuatrimestre}cuatri_recocido.csv"
    p_stats = base / f"estadisticas_recocido_{curso}GIFM_{cuatrimestre}cuatri.csv"
    return p_cp, p_sa, p_csv, p_stats


def mostrar_leyenda_colores():
    st.markdown(
        """
        <div class="legend-bar">
            <span style="font-size:0.82rem; font-weight:700; color:#475569;">Código visual EII:</span>
            <span class="leg-item leg-teoria">Teoría</span>
            <span class="leg-item leg-aula">Práctica de Aula / Problemas</span>
            <span class="leg-item leg-lab">Práctica de Laboratorio</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# SIDEBAR DE NAVEGACIÓN
# ---------------------------------------------------------------------------
df_catalogo = cargar_catalogo_unificado()
df_aulas = cargar_aulas()

with st.sidebar:
    st.markdown(
        """
        <div style="padding:0.4rem 0 0.8rem 0;">
            <div style="font-size:0.75rem; font-weight:800; letter-spacing:0.08em; color:#64748B; text-transform:uppercase;">
                ULPGC · Escuela de Ingeniería Informática
            </div>
            <div style="font-size:1.3rem; font-weight:800; color:#0F2952; margin-top:0.15rem;">
                Planificador OH
            </div>
            <div style="font-size:0.82rem; color:#475569; margin-top:0.1rem;">
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
        f"• **12 cursos** (1º a 4º · 2 cuatrimestres)\n"
        f"• **{len(df_catalogo)} sesiones** ({int(df_catalogo['Horas'].sum())} h semanales)\n"
        f"• **{len(df_aulas)} espacios físicos** EII\n"
        f"• **Motores:** CP-SAT + Recocido Simulado"
    )
    st.divider()
    st.caption("Equipo: Yone (GII) · Inés (GCID) · María (GIFM)")


# ---------------------------------------------------------------------------
# VISTA 1 (PORTADA INTERACTIVA): EXPLORADOR DE HORARIOS
# ---------------------------------------------------------------------------
if vista == "🗓️ Explorador de Horarios":
    st.markdown(
        """
        <div class="eii-hero">
            <h1>🗓️ Explorador Interactivo de Horarios — EII ULPGC</h1>
            <p>Navega los calendarios optimizados de <b>GII</b>, <b>GCID</b> y <b>GIFM</b>, compara <b>OR-Tools CP-SAT</b> frente a <b>Recocido Simulado</b> y contrasta con el horario oficial de la Escuela.</p>
            <div class="badge-row">
                <span class="pill">GII · 4 Cursos (Mañana y Tarde)</span>
                <span class="pill">GCID · 4 Cursos (CP-SAT vs SA)</span>
                <span class="pill">GIFM · 4 Cursos (Híbrido CP-SAT → SA)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns([1.4, 1.0, 1.1, 1.5])
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

    df_sel = df_catalogo[
        (df_catalogo["Titulación"] == tit)
        & (df_catalogo["Curso"] == curso)
        & (df_catalogo["Cuatrimestre"] == cuatri)
    ].copy()

    # Selector de modo según titulación
    with c4:
        if tit == "GII":
            modo_gii = st.selectbox(
                "Modo de visualización",
                options=[
                    "Horario Optimizado (CP-SAT)",
                    "Comparativa: Optimizado vs. Oficial EII (PDF)",
                ],
            )
        else:
            modo_comp = st.selectbox(
                "Modo de visualización",
                options=[
                    "Comparativa lado a lado (CP-SAT vs. Recocido Simulado)",
                    "Solo OR-Tools CP-SAT",
                    "Solo Recocido Simulado (SA)",
                ],
            )

    # KPIs rápidos de la selección
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Sesiones programadas", f"{len(df_sel)}")
    k2.metric("Horas semanales", f"{int(df_sel['Horas'].sum())} h")
    k3.metric("Asignaturas", f"{df_sel['Asignatura'].nunique()}")
    k4.metric("Docentes implicados", f"{df_sel['Profesor'].nunique()}")

    mostrar_leyenda_colores()

    # Renderizado del horario según titulación
    if tit == "GII":
        opciones_gii = obtener_opciones_gii(curso, cuatri)
        if not opciones_gii:
            st.warning("No se encontraron imágenes generadas para esta selección de GII.")
        else:
            label_sel = st.radio(
                "Grupo / Turno a visualizar:",
                options=list(opciones_gii.keys()),
                horizontal=True,
            )
            ruta_img = opciones_gii[label_sel]

            if modo_gii == "Horario Optimizado (CP-SAT)":
                st.image(str(ruta_img), caption=f"{curso}º GII · {cuatri}º Semestre — {label_sel}", width="stretch")
                with open(ruta_img, "rb") as f_bin:
                    st.download_button(
                        "⬇️ Descargar horario en PNG (300 DPI)",
                        data=f_bin.read(),
                        file_name=f"{curso}GII_S{cuatri}_{ruta_img.name}",
                        mime="image/png",
                    )
            else:
                col_opt, col_ofi = st.columns(2)
                with col_opt:
                    st.subheader("Propuesta Optimizada (Proyecto OH)")
                    st.image(str(ruta_img), caption=f"Optimizado · {curso}º GII ({label_sel})", width="stretch")
                with col_ofi:
                    st.subheader("Horario Oficial EII 2026–2027 (PDF)")
                    page_idx = GII_PDF_PAGES.get((curso, cuatri))
                    if page_idx is not None:
                        img_pdf = renderizar_pagina_pdf_gii(page_idx, zoom=2.0)
                        if img_pdf:
                            st.image(
                                img_pdf,
                                caption=f"PDF Oficial EII — Página {page_idx + 1} ({curso}º GII · {cuatri}º Sem.)",
                                width="stretch",
                            )
                        else:
                            st.info("Instala `pymupdf` para previsualizar el PDF oficial dentro de la app.")
                    else:
                        st.info(
                            "El PDF oficial de GII (`horario_GII_2026_2027.pdf`) incluye páginas 1–7 "
                            "(1º a 4º S1); la página 8 corresponde a la leyenda general de siglas de asignaturas."
                        )
                        img_ley = renderizar_pagina_pdf_gii(7, zoom=1.8)
                        if img_ley:
                            st.image(img_ley, caption="PDF Oficial EII — Página 8 (Leyenda de siglas)", width="stretch")

    elif tit == "GCID":
        p_cp, p_sa = obtener_rutas_gcid(curso, cuatri)
        if curso == 3 and cuatri == 2:
            st.info(
                "📌 **Particularidad 3º GCID (2º Cuatrimestre):** Jueves y viernes se mantienen "
                "100% libres de docencia presencial para facilitar las **Prácticas Externas** en empresa."
            )
        elif curso == 1:
            st.info(
                "📌 **Particularidad 1º GCID:** Las sesiones de teoría de una misma asignatura se reparten "
                "en días distintos y la carga lectiva diaria de cada subgrupo no supera las 4 horas (0 huecos)."
            )

        if modo_comp.startswith("Comparativa"):
            c_left, c_right = st.columns(2)
            with c_left:
                st.subheader("OR-Tools CP-SAT (Óptimo Exacto)")
                if p_cp.exists():
                    st.image(str(p_cp), width="stretch")
                    with open(p_cp, "rb") as fb:
                        st.download_button("⬇️ Descargar CP-SAT PNG", fb.read(), file_name=p_cp.name, mime="image/png")
            with c_right:
                st.subheader("Recocido Simulado (Metaheurística)")
                if p_sa.exists():
                    st.image(str(p_sa), width="stretch")
                    with open(p_sa, "rb") as fb:
                        st.download_button("⬇️ Descargar SA PNG", fb.read(), file_name=p_sa.name, mime="image/png")
        elif "CP-SAT" in modo_comp:
            st.image(str(p_cp), caption=f"{curso}º GCID · {cuatri}º Cuatrimestre (CP-SAT)", width="stretch")
            with open(p_cp, "rb") as fb:
                st.download_button("⬇️ Descargar CP-SAT PNG", fb.read(), file_name=p_cp.name, mime="image/png")
        else:
            st.image(str(p_sa), caption=f"{curso}º GCID · {cuatri}º Cuatrimestre (Recocido Simulado)", width="stretch")
            with open(p_sa, "rb") as fb:
                st.download_button("⬇️ Descargar SA PNG", fb.read(), file_name=p_sa.name, mime="image/png")

    else:  # GIFM
        p_cp, p_sa, p_csv, p_stats = obtener_rutas_gifm(curso, cuatri)
        if curso == 3 and cuatri == 2:
            st.info(
                "📌 **Particularidad 3º GIFM (2º Cuatrimestre):** Debido a la alta densidad de asignaturas y "
                "bloques semanales, el solver activa automáticamente la **jornada ampliada (08:30–16:30)**."
            )

        if p_stats.exists():
            st_row = pd.read_csv(p_stats, encoding="utf-8-sig").iloc[0]
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Coste inicial → final (SA)", f"{int(st_row['Coste_inicial'])} → {int(st_row['Mejor_coste'])}")
            s2.metric("Tiempo SA", f"{float(st_row['Tiempo_segundos']):.2f} s")
            s3.metric("Movimientos aceptados", f"{int(st_row['Aceptados'])} / {int(st_row['Iteraciones'])}")
            s4.metric("Horario válido", "100% Factible" if bool(st_row["Horario_valido"]) else "Revisar")

        if modo_comp.startswith("Comparativa"):
            c_left, c_right = st.columns(2)
            with c_left:
                st.subheader("OR-Tools CP-SAT (Solución Inicial)")
                if p_cp.exists():
                    st.image(str(p_cp), width="stretch")
                    with open(p_cp, "rb") as fb:
                        st.download_button("⬇️ Descargar CP-SAT PNG", fb.read(), file_name=p_cp.name, mime="image/png")
            with c_right:
                st.subheader("Recocido Simulado (Refinamiento SA)")
                if p_sa.exists():
                    st.image(str(p_sa), width="stretch")
                    with open(p_sa, "rb") as fb:
                        st.download_button("⬇️ Descargar SA PNG", fb.read(), file_name=p_sa.name, mime="image/png")
        elif "CP-SAT" in modo_comp:
            st.image(str(p_cp), caption=f"{curso}º GIFM · {cuatri}º Cuatrimestre (CP-SAT)", width="stretch")
        else:
            st.image(str(p_sa), caption=f"{curso}º GIFM · {cuatri}º Cuatrimestre (Recocido Simulado)", width="stretch")

        if p_csv.exists():
            with st.expander("📋 Ver horario resuelto detallado de GIFM (tabla filtrable por día/asignatura)", expanded=False):
                df_gifm_res = pd.read_csv(p_csv, encoding="utf-8-sig")
                f_dia = st.multiselect(
                    "Filtrar por día",
                    options=df_gifm_res["Dia"].unique().tolist(),
                    default=df_gifm_res["Dia"].unique().tolist(),
                )
                df_show = df_gifm_res[df_gifm_res["Dia"].isin(f_dia)]
                cols_show = [c for c in ["Dia", "Hora", "Asignatura", "Tipo", "Grupo", "Aula", "Profesor", "Semanas_activas"] if c in df_show.columns]
                st.dataframe(df_show[cols_show], width="stretch", hide_index=True)

    # Inspector de sesiones de entrada de la selección
    with st.expander(f"🔎 Inspector de sesiones de entrada ({tit} · {curso}º Curso · {cuatri}º Cuatrimestre)", expanded=False):
        q = st.text_input("Buscar asignatura, profesor o grupo", key="busq_exp")
        df_disp = df_sel.copy()
        if q.strip():
            mask = (
                df_disp["Asignatura"].str.contains(q, case=False, na=False)
                | df_disp["Profesor"].str.contains(q, case=False, na=False)
                | df_disp["Grupo"].str.contains(q, case=False, na=False)
            )
            df_disp = df_disp[mask]
        cols_cat = ["ID", "Asignatura", "Modalidad", "Grupo", "Horas", "Alumnos", "Tipo_Aula", "Profesor"]
        if tit == "GIFM":
            cols_cat.append("Semanas")
        if tit == "GII":
            cols_cat.insert(4, "Grupo_Principal")
        st.dataframe(df_disp[cols_cat], width="stretch", hide_index=True)


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
    m1.metric("Titulaciones integradas", "3 Grados", "GII · GCID · GIFM")
    m2.metric("Sesiones en catálogo", f"{len(df_catalogo)}", "1º a 4º · Ambos cuatris")
    m3.metric("Carga lectiva semanal", f"{int(df_catalogo['Horas'].sum())} h", "Teoría, Aula y Lab")
    m4.metric("Espacios docentes EII", f"{len(df_aulas)}", "12 Teoría · 15 Labs")
    m5.metric("Factibilidad alcanzada", "100 %", "0 choques duros")

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
            "Sesiones": int((df_catalogo["Titulación"] == deg).sum()),
            "Horas": int(df_catalogo.loc[df_catalogo["Titulación"] == deg, "Horas"].sum()),
            "Asignaturas": int(df_catalogo.loc[df_catalogo["Titulación"] == deg, "Asignatura"].nunique()),
            "Docentes": int(df_catalogo.loc[df_catalogo["Titulación"] == deg, "Profesor"].nunique()),
            "Horarios PNG": "18 (CP-SAT, Mañana y Tarde)" if deg == "GII" else "16 (8 CP-SAT + 8 SA)",
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

    # ---- TAB GII ----
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
            k1.metric("Factibilidad Búsqueda Aleatoria", "0.0 %", "6–16 choques duros", delta_color="inverse")
            k2.metric("Factibilidad CP-SAT & SA", "100.0 %", "0 violaciones duras")
            k3.metric("Reducción de huecos (SA vs CP-SAT)", "56% – 100%", "0 pts en 1º GII")
            k4.metric("Tiempo medio de ejecución", "1.4 – 5.1 s", "5 semillas independientes")

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

    # ---- TAB GCID ----
    with tab_gcid:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Sesiones globales optimizadas", "150", "86 en S1 · 64 en S2")
        k2.metric("Choques duros y huecos", "0 / 0", "Tanto en CP-SAT como en SA")
        k3.metric("Penalización blanda (1er Sem.)", "85 vs 160", "CP-SAT óptimo vs SA")
        k4.metric("Penalización blanda (2º Sem.)", "25 vs 150", "CP-SAT óptimo vs SA")

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

    # ---- TAB GIFM ----
    with tab_gifm:
        df_gifm = cargar_estadisticas_gifm()
        if not df_gifm.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Instancias resueltas", f"{len(df_gifm)} / 8", "1º a 4º · Ambos cuatris")
            k2.metric("Horarios válidos", f"{int(df_gifm['Horario_valido'].sum())} / {len(df_gifm)}", "100% Factibles")
            k3.metric("Coste medio final", f"{df_gifm['Mejor_coste'].mean():.2f}", "0 en 7 de 8 instancias")
            k4.metric("Tiempo medio SA", f"{df_gifm['Tiempo_segundos'].mean():.2f} s", f"Máx: {df_gifm['Tiempo_segundos'].max():.2f} s (3º C2)")

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

    # ---- TAB SÍNTESIS COMPARATIVA ----
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

    # Hiperparámetros ajustables cuando se elige Recocido Simulado
    t_inicial, alpha, iter_por_temp, max_iter, semilla = 120.0, 0.985, 140, 20000, 42
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
            else:  # GIFM
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
        k2.metric("Violaciones duras", f"{s['violaciones_duras']}", "Factible" if s["factible"] else "Revisar")
        k3.metric("Coste blando / Energía", f"{s['coste_blando']:.1f}")
        k4.metric("Sesiones ubicadas", f"{s['sesiones']}")

        # Curva interactiva de convergencia en directo si existe historial
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
            st.metric("Aulas de Teoría", f"{int((df_aulas['tipo'] == 'Teoria').sum())}", f"Cap. total: {int(df_aulas.loc[df_aulas['tipo'] == 'Teoria', 'capacidad'].sum())} plazas")
            st.metric("Laboratorios", f"{int((df_aulas['tipo'] == 'Laboratorio').sum())}", f"Cap. total: {int(df_aulas.loc[df_aulas['tipo'] == 'Laboratorio', 'capacidad'].sum())} plazas")
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
