"""
Herramientas interactivas unificadas para el Cuadro de Mandos EII – ULPGC:
- Generador de calendario RFC 5545 (.ics) para Google Calendar / Outlook / Apple Calendar
- Filtro y cálculo de huecos para el modo "Mi Horario de Estudiante" (por subgrupo o multi-curso)
- Validador en tiempo real de restricciones duras y blandas para el "Editor Manual"
"""

from datetime import date, datetime, timedelta
import pandas as pd


DIAS_ORDEN = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
DIA_A_INDICE = {d: i for i, d in enumerate(DIAS_ORDEN)}

# Jerarquía oficial EII de prácticas de aula -> subgrupos de laboratorio
MAPEO_AULA_SUBGRUPOS = {
    "17": {"41", "42"},
    "18": {"43", "44"},
    "19": {"45", "46"},
    "20": {"47", "48"},
    "21": {"49", "50"},
    "22": {"51", "52"},
}


def normalizar_dia(valor: str) -> str:
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


def subgrupos_de_sesion(row: pd.Series, subgrupos_curso: set[str]) -> set[str]:
    """Devuelve el conjunto de subgrupos atómicos afectados por una sesión."""
    mod = str(row.get("Modalidad", "")).strip().lower()
    grp = str(row.get("Grupo", "")).strip()

    if "teor" in mod:
        return set(subgrupos_curso) if subgrupos_curso else {grp}
    if "aula" in mod or "problem" in mod:
        if grp in MAPEO_AULA_SUBGRUPOS:
            inter = MAPEO_AULA_SUBGRUPOS[grp] & subgrupos_curso
            return inter if inter else set(MAPEO_AULA_SUBGRUPOS[grp])
        return set(subgrupos_curso) if subgrupos_curso else {grp}
    return {grp}


def detectar_subgrupos_disponibles(df_curso: pd.DataFrame) -> list[str]:
    """Devuelve la lista ordenada de subgrupos de laboratorio existentes en un DataFrame."""
    if df_curso.empty:
        return []
    labs = df_curso[df_curso["Modalidad"] == "Laboratorio"]["Grupo"].astype(str).str.strip().unique().tolist()
    subs = sorted([g for g in labs if g], key=lambda x: (int(x) if x.isdigit() else 999, x))
    if not subs:
        subs = sorted(df_curso["Grupo"].astype(str).str.strip().unique().tolist())
    return subs


def filtrar_horario_subgrupo(df_curso: pd.DataFrame, subgrupo: str) -> pd.DataFrame:
    """Filtra un horario de curso/grupo para dejar únicamente las sesiones de un subgrupo concreto."""
    if df_curso.empty:
        return df_curso.copy()
    subgrupos_all = set(detectar_subgrupos_disponibles(df_curso))
    filas = []
    for _, row in df_curso.iterrows():
        afectados = subgrupos_de_sesion(row, subgrupos_all)
        if subgrupo in afectados:
            filas.append(row)
    return pd.DataFrame(filas).reset_index(drop=True) if filas else df_curso.iloc[0:0].copy()


def calcular_huecos_estudiante(df_est: pd.DataFrame) -> dict:
    """Calcula huecos diarios reales, horas por día y solapes para un horario personal de alumno."""
    if df_est.empty:
        return {"huecos_totales": 0, "solapes": 0, "horas_totales": 0, "dias_activos": 0, "detalle_dias": {}}

    horas_por_dia = {d: [] for d in DIAS_ORDEN}
    for _, r in df_est.iterrows():
        dia = normalizar_dia(r["Dia"])
        if dia not in horas_por_dia:
            continue
        try:
            h0 = int(str(r["Hora"]).split(":")[0])
        except Exception:
            continue
        dur = max(1, int(r["DuracionHoras"]))
        for off in range(dur):
            horas_por_dia[dia].append(h0 + off)

    huecos_tot = 0
    solapes = 0
    detalle = {}
    for d, hs in horas_por_dia.items():
        if not hs:
            detalle[d] = {"horas": 0, "huecos": 0, "solapes": 0}
            continue
        unicas = sorted(set(hs))
        sol_d = len(hs) - len(unicas)
        span = unicas[-1] - unicas[0] + 1
        huecos_d = max(0, span - len(unicas))
        huecos_tot += huecos_d
        solapes += sol_d
        detalle[d] = {"horas": len(hs), "huecos": huecos_d, "solapes": sol_d}

    return {
        "huecos_totales": huecos_tot,
        "solapes": solapes,
        "horas_totales": int(df_est["DuracionHoras"].sum()),
        "dias_activos": sum(1 for v in detalle.values() if v["horas"] > 0),
        "detalle_dias": detalle,
    }


def evaluar_horario_manual(
    df_horario: pd.DataFrame,
    df_aulas: pd.DataFrame,
    df_catalogo_curso: pd.DataFrame | None = None,
    peso_duro: int = 2000,
    peso_hueco: int = 15,
    peso_viernes: int = 10,
) -> dict:
    """
    Evalúa en tiempo real todas las restricciones duras y blandas de un horario editado manualmente.
    Devuelve desglose de conflictos legibles para la interfaz y la energía total Phi(X).
    """
    if df_horario.empty:
        return {"energia": 0, "duras": 0, "huecos": 0, "viernes_tarde": 0, "alertas": [], "celdas_conflicto": set()}

    aulas_map = {}
    for _, ra in df_aulas.iterrows():
        aulas_map[str(ra["id_aula"]).strip()] = {
            "tipo": str(ra["tipo"]).strip().lower(),
            "capacidad": int(ra["capacidad"]),
        }

    alumnos_map = {}
    if df_catalogo_curso is not None and not df_catalogo_curso.empty:
        for _, rc in df_catalogo_curso.iterrows():
            alumnos_map[str(rc["ID"]).strip()] = int(rc.get("Alumnos", 20))
            alumnos_map[(str(rc["Asignatura"]).strip(), str(rc["Grupo"]).strip(), str(rc["Modalidad"]).strip())] = int(rc.get("Alumnos", 20))

    subgrupos_curso = set(detectar_subgrupos_disponibles(df_horario))
    alertas = []
    celdas_conflicto = set()  # (Dia, HoraIni)

    ocup_prof = {}   # (Dia, h, prof) -> list of labels
    ocup_aula = {}   # (Dia, h, aula) -> list of labels
    ocup_subg = {}   # (Dia, h, gp, sub) -> list of labels
    horas_subg_dia = {}  # (gp, sub, Dia) -> set of h

    duras = 0
    viernes_tarde = 0

    for _, r in df_horario.iterrows():
        dia = normalizar_dia(r["Dia"])
        asig = str(r["Asignatura"]).strip()
        grp = str(r["Grupo"]).strip()
        mod = str(r["Modalidad"]).strip()
        aula = str(r["Aula"]).strip()
        prof = str(r["Profesor"]).strip()
        gp = int(r.get("GrupoPrincipal", 1))
        dur = max(1, int(r["DuracionHoras"]))
        etiqueta = f"{asig} (G{grp})"

        try:
            h0 = int(str(r["Hora"]).split(":")[0])
        except Exception:
            h0 = 8

        # Comprobar compatibilidad de aula (tipo y aforo)
        info_a = aulas_map.get(aula)
        if info_a is not None:
            req_lab = (mod == "Laboratorio")
            es_lab = ("lab" in info_a["tipo"])
            if req_lab and not es_lab:
                duras += 1
                alertas.append(f"🏫 **Tipo de aula incompatible:** `{etiqueta}` es de Laboratorio pero se colocó en `{aula}` (Teoría).")
                for off in range(dur):
                    celdas_conflicto.add((dia, h0 + off))
            elif (not req_lab) and es_lab:
                duras += 1
                alertas.append(f"🏫 **Tipo de aula incompatible:** `{etiqueta}` es de {mod} pero se colocó en `{aula}` (Laboratorio).")
                for off in range(dur):
                    celdas_conflicto.add((dia, h0 + off))

            alum = alumnos_map.get(str(r.get("Sesion", "")).strip())
            if alum is None:
                alum = alumnos_map.get((asig, grp, mod), 0)
            if alum > info_a["capacidad"]:
                duras += 1
                alertas.append(f"👥 **Aforo excedido:** `{etiqueta}` tiene {alum} alumnos y `{aula}` solo admite {info_a['capacidad']}.")
                for off in range(dur):
                    celdas_conflicto.add((dia, h0 + off))

        # Viernes últimas horas
        if dia == "Viernes" and h0 in (12, 13, 18, 19):
            viernes_tarde += 1

        subs_afectados = subgrupos_de_sesion(r, subgrupos_curso)

        for off in range(dur):
            h = h0 + off
            # Profesor
            if prof and prof.lower() not in ("nan", "none", ""):
                key_p = (dia, h, prof)
                ocup_prof.setdefault(key_p, []).append(etiqueta)
            # Aula
            key_a = (dia, h, aula)
            ocup_aula.setdefault(key_a, []).append(etiqueta)
            # Subgrupos
            for sg in subs_afectados:
                key_s = (dia, h, gp, sg)
                ocup_subg.setdefault(key_s, []).append(etiqueta)
                horas_subg_dia.setdefault((gp, sg, dia), set()).add(h)

    # Reportar colisiones deduplicadas
    vistos_prof = set()
    for (dia, h, prof), lst in ocup_prof.items():
        if len(lst) > 1:
            duras += len(lst) - 1
            celdas_conflicto.add((dia, h))
            sig = (dia, prof, tuple(sorted(set(lst))))
            if sig not in vistos_prof:
                vistos_prof.add(sig)
                alertas.append(f"👨‍🏫 **Choque de profesor:** `{prof}` tiene simultáneamente {' y '.join(sorted(set(lst)))} el {dia} ({h:02d}:30).")

    vistos_aula = set()
    for (dia, h, aula), lst in ocup_aula.items():
        if len(lst) > 1:
            duras += len(lst) - 1
            celdas_conflicto.add((dia, h))
            sig = (dia, aula, tuple(sorted(set(lst))))
            if sig not in vistos_aula:
                vistos_aula.add(sig)
                alertas.append(f"🏫 **Choque de aula:** `{aula}` está ocupada a la vez por {' y '.join(sorted(set(lst)))} el {dia} ({h:02d}:30).")

    vistos_subg = set()
    for (dia, h, gp, sg), lst in ocup_subg.items():
        if len(lst) > 1:
            duras += len(lst) - 1
            celdas_conflicto.add((dia, h))
            sig = (dia, sg, tuple(sorted(set(lst))))
            if sig not in vistos_subg:
                vistos_subg.add(sig)
                alertas.append(f"🎓 **Choque de alumnado (Subgrupo {sg}):** coinciden {' y '.join(sorted(set(lst)))} el {dia} ({h:02d}:30).")

    # Huecos por subgrupo
    huecos = 0
    for (_, _, _), hs in horas_subg_dia.items():
        if len(hs) > 1:
            orden = sorted(hs)
            huecos += (orden[-1] - orden[0] + 1) - len(orden)

    coste_blando = huecos * peso_hueco + viernes_tarde * peso_viernes
    energia = duras * peso_duro + coste_blando

    return {
        "energia": int(energia),
        "duras": int(duras),
        "huecos": int(huecos),
        "viernes_tarde": int(viernes_tarde),
        "coste_blando": int(coste_blando),
        "alertas": alertas,
        "celdas_conflicto": celdas_conflicto,
    }


def _escape_ics(texto: str) -> str:
    return (
        str(texto)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generar_ics(df_horario: pd.DataFrame, nombre_calendario: str, cuatrimestre: int = 1) -> str:
    """
    Exporta un DataFrame de horario semanal a formato iCalendar (.ics, RFC 5545)
    con recurrencia de 15 semanas lectivas (zona horaria Atlantic/Canary - ULPGC).
    """
    # Lunes de inicio aproximado del curso 2026-2027 en la ULPGC
    lunes_inicio = date(2026, 9, 14) if int(cuatrimestre) == 1 else date(2027, 2, 1)
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EII-ULPGC//ProyectoOH Horarios 2026-2027//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics(nombre_calendario)}",
        "X-WR-TIMEZONE:Atlantic/Canary",
    ]

    for idx, r in df_horario.reset_index(drop=True).iterrows():
        dia = normalizar_dia(r["Dia"])
        offset_dia = DIA_A_INDICE.get(dia, 0)
        fecha_ev = lunes_inicio + timedelta(days=offset_dia)
        try:
            h_ini = int(str(r["Hora"]).split(":")[0])
            m_ini = int(str(r["Hora"]).split(":")[1].split("-")[0])
        except Exception:
            h_ini, m_ini = 8, 30
        dur = max(1, int(r.get("DuracionHoras", 1)))
        dt_ini = datetime(fecha_ev.year, fecha_ev.month, fecha_ev.day, h_ini, m_ini)
        dt_fin = dt_ini + timedelta(hours=dur)

        asig = str(r.get("Asignatura", "")).strip()
        mod = str(r.get("Modalidad", "")).strip()
        grp = str(r.get("Grupo", "")).strip()
        aula = str(r.get("Aula", "")).strip()
        prof = str(r.get("Profesor", "")).strip()
        tit = str(r.get("Titulacion", "EII")).strip()
        curso = str(r.get("Curso", "")).strip()
        semanas = str(r.get("Semanas", "1-15")).strip()

        resumen = f"{asig} ({mod} · G{grp})"
        desc = f"Titulación: {tit} {curso}º | Modalidad: {mod} | Grupo: {grp} | Profesor: {prof} | Semanas: {semanas}"
        uid = f"eii-ulpgc-{tit.lower()}-c{cuatrimestre}-{idx}-{dia.lower()}-{h_ini}@oh2026"

        lineas.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;TZID=Atlantic/Canary:{dt_ini.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID=Atlantic/Canary:{dt_fin.strftime('%Y%m%dT%H%M%S')}",
            "RRULE:FREQ=WEEKLY;COUNT=15",
            f"SUMMARY:{_escape_ics(resumen)}",
            f"LOCATION:{_escape_ics('EII ULPGC - Aula ' + aula)}",
            f"DESCRIPTION:{_escape_ics(desc)}",
            "END:VEVENT",
        ])

    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas) + "\r\n"
