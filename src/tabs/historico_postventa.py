"""
Pestaña Histórico Postventa - Tablero SUMMA
Implementa la lógica completa del histórico de RNs postventa
"""

import streamlit as st
import pandas as pd
import re
import unicodedata
import time
import os
import pickle
from datetime import datetime, timedelta, date
from src.jira_conexion import get_jira
from src.utils.configuracion import cache_path, cargar_epicas_relevantes
from src.utils.database_helper import DatabaseHelper

def mostrar_historico_postventa(df):
    """Mostrar la pestaña de Histórico Postventa"""
    
    # ------------------ Helpers ------------------
    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    def _status_norm(s: str) -> str:
        return (s or "").strip().lower()

    def _safe_issue_key(iss) -> str:
        return (iss.get("key") or iss.get("id") or "") if isinstance(iss, dict) else ""

    # --- Cálculo de días laborables (excluyendo fines de semana y feriados) ---
    def calcular_dias_laborables(fecha_inicio, fecha_fin):
        """Calcula días laborables entre dos fechas (excluyendo fines de semana y feriados)"""
        if pd.isna(fecha_inicio) or pd.isna(fecha_fin):
            return 0
        feriados = [
            date(2025, 1, 1),
            date(2025, 2, 24),
            date(2025, 2, 25),
            date(2025, 3, 24),
            date(2025, 4, 2),
            date(2025, 4, 18),
            date(2025, 5, 1),
            date(2025, 5, 25),
            date(2025, 6, 20),
            date(2025, 6, 16),
            date(2025, 7, 9),
            date(2025, 8, 17),
            date(2025, 10, 12),
            date(2025, 11, 24),
            date(2025, 12, 8),
            date(2025, 12, 25),
        ]
        ini = fecha_inicio.date() if hasattr(fecha_inicio, 'date') else fecha_inicio
        fin = fecha_fin.date() if hasattr(fecha_fin, 'date') else fecha_fin
        if ini > fin:
            return 0
        dias = 0
        actual = ini  # incluir día de inicio si es hábil
        while actual <= fin:
            if actual.weekday() < 5 and actual not in feriados:
                dias += 1
            actual += timedelta(days=1)
        return dias
    
    # --- Cálculo robusto de horas desde changelog (con fallbacks) ---
    def _bug_resolution_hours(bug_issue) -> float | None:
        f = bug_issue.get("fields", {}) or {}
        created = pd.to_datetime(f.get("created"), errors="coerce")
        resolution = pd.to_datetime(f.get("resolutiondate"), errors="coerce")
        updated = pd.to_datetime(f.get("updated"), errors="coerce")

        TODO_PATTERNS     = ("to do", "por hacer", "pendiente", "backlog", "asignados a backlog")
        PROGRESS_PATTERNS = ("in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo")
        DONE_PATTERNS     = ("cerrad", "done", "resuelt", "hech", "closed")

        start_dt, end_dt, last_hist_dt = None, None, None
        histories = (bug_issue.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))

        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            last_hist_dt = h_created if pd.notna(h_created) else last_hist_dt
            for it in hist.get("items", []) or []:
                if _status_norm(it.get("field")) != "status":
                    continue
                to_str  = _status_norm(it.get("toString"))
                from_str= _status_norm(it.get("fromString"))

                if start_dt is None:
                    sale_de_todo  = any(p in from_str for p in TODO_PATTERNS) and not any(p in to_str for p in TODO_PATTERNS)
                    entra_en_prog = any(p in to_str for p in PROGRESS_PATTERNS)
                    if sale_de_todo or entra_en_prog:
                        start_dt = h_created

                if end_dt is None and any(p in to_str for p in DONE_PATTERNS):
                    end_dt = h_created

            if start_dt is not None and end_dt is not None:
                break

        if start_dt is None:
            start_dt = created
        if end_dt is None:
            if pd.notna(resolution):
                end_dt = resolution
            else:
                status_now = _status_norm((f.get("status") or {}).get("name"))
                if any(p in status_now for p in DONE_PATTERNS):
                    end_dt = last_hist_dt or updated

        if pd.isna(start_dt) or pd.isna(end_dt):
            return None

        # Calcular días laborables y convertir a horas (8 horas por día laboral)
        dias_lab = calcular_dias_laborables(start_dt, end_dt)
        if dias_lab < 0:
            return None
        
        # Convertir días laborables a horas (8 horas por día)
        horas_laborables = dias_lab * 8.0
        return horas_laborables

    def _bugs_por_hu(bugs_issues) -> dict:
        """
        Dict { HU_KEY: {"bugs": [bug_key,...], "hrs": [resol_horas,...]} }
        Para bugs de REP/TAL (métrica 'Bugs asociados' + promedio hs).
        """
        por_hu = {}
        for iss in bugs_issues:
            f = iss.get("fields", {}) or {}
            itype = _status_norm((f.get("issuetype", {}) or {}).get("name"))
            if itype not in ("error", "bug", "defecto", "incidencia"):
                continue
            bug_key = iss.get("key", "")
            if not bug_key:
                continue
            candidate_hus = set()
            parent_key = (f.get("parent") or {}).get("key", "")
            if parent_key:
                candidate_hus.add(parent_key)
            for link in (f.get("issuelinks") or []):
                for side in ("inwardIssue", "outwardIssue"):
                    lk = link.get(side) or {}
                    k = lk.get("key")
                    if k:
                        candidate_hus.add(k)
            hrs = _bug_resolution_hours(iss)
            for hu in candidate_hus:
                if not hu:
                    continue
                slot = por_hu.setdefault(hu, {"bugs": [], "hrs": []})
                slot["bugs"].append(bug_key)
                if hrs is not None:
                    slot["hrs"].append(hrs)
        return por_hu

    def _es_tipo_bug_uat(issuetype_name: str) -> bool:
        n = (issuetype_name or "").lower()
        return any(k in n for k in ("bug", "error", "defecto", "incidencia"))

    # ------------------ Fuente de datos ------------------
    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    # Cargar historias REP+TAL desde la base de datos
    db = DatabaseHelper()
    db.conectar()
    historias_db = db.obtener_historias_con_transiciones(["REP", "TAL"])  # Jira-like dicts
    db.cerrar()

    issues = historias_db

    # Desduplico por key
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # Map RN (nombre de épica) → historias y → set de EPIC KEYS (para UAT)
    EPIC_LINK_CAMPO_STORY = "customfield_10016"
    epicas = {}              # { RN_name: {"Historias": [...] } }
    epicas_por_key = {}      # { EPIC_KEY: {"Historias": [...] } }
    rn_to_epic_keys = {}     # { RN_name: set([EPIC-123,...]) }

    # Mapeo auxiliar desde clave de épica (REP-xxx/TAL-xxx) a nombre de RN
    epicas_relevantes_all = cargar_epicas_relevantes()
    epic_key_to_name = {e.get("rn", ""): e.get("nombre", "") for e in epicas_relevantes_all}

    # Filtrar solo issues de postventas (REP y TAL)
    issues_postventas = [i for i in issues if (i.get("fields",{}).get("project",{}) or {}).get("key") in ["REP", "TAL"]]

    for issue in issues_postventas:
        f = issue.get("fields", {}) or {}

        # Determinar RN/Épica (nombre) y parent_key de forma robusta con base de datos
        epic_name = None
        parent = f.get("parent")
        parent_key = None
        if parent:
            parent_key = (parent.get("key") or (parent.get("fields") or {}).get("key"))
            # Si tenemos la clave, podemos mapear a nombre usando JSON
            if parent_key:
                epic_name = epic_key_to_name.get(parent_key) or (parent.get("summary") or (parent.get("fields") or {}).get("summary"))
        # Fallback: intentar con customfield_10016 (puede ser string con key)
        if not epic_name:
            ep_ref = f.get(EPIC_LINK_CAMPO_STORY)
            if isinstance(ep_ref, dict):
                # Algunos tableros guardan {key: REP-123, name: \n}
                ek = ep_ref.get("key") or ep_ref.get("id") or ep_ref.get("value")
                if ek:
                    epic_name = epic_key_to_name.get(str(ek).strip()) or ep_ref.get("value") or ep_ref.get("name")
                    if not parent_key:
                        parent_key = str(ek).strip()
            elif isinstance(ep_ref, str) and ep_ref.strip():
                ek = ep_ref.strip()
                epic_name = epic_key_to_name.get(ek) or ek
                if not parent_key:
                    parent_key = ek
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            epic_name = "Sin epica"

        summary = f.get("summary", "")
        if "madre" in (summary or "").lower():
            continue

        estado = _status_norm((f.get("status") or {}).get("name"))
        asg = (f.get("assignee") or {})
        asignado = asg.get("displayName", "")
        puntos = f.get("customfield_10026", 0) or 0
        try:
            puntos = float(puntos)
        except Exception:
            puntos = 0.0

        key = issue.get("key", "")
        fecha_estado = f.get("statuscategorychangedate") or f.get("updated") or ""
        duedate = f.get("duedate") or ""

        detalle_historia = {
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos,
        }
        epicas.setdefault(epic_name, {"Historias": []})["Historias"].append(detalle_historia)
        if parent_key:
            epicas_por_key.setdefault(parent_key, {"Historias": []})["Historias"].append(detalle_historia)
        if parent_key:
            rn_to_epic_keys.setdefault(epic_name, set()).add(parent_key)

    # Bugs REP/TAL con datos de la base (incluye parent/issuelinks/fechas). El cálculo de horas usa fallback si no hay changelog.
    db = DatabaseHelper()
    db.conectar()
    bugs_rep = db.obtener_bugs_con_cierre(["REP"]) or []
    bugs_tal = db.obtener_bugs_con_cierre(["TAL"]) or []
    db.cerrar()
    bugs_all = bugs_rep + bugs_tal
    mapa_bugs_hu = _bugs_por_hu(bugs_all)

    # BUGS UAT (project = BUG) — desde la base (Epic Link en customfield_10016)
    EPIC_FIELD_BUG = "customfield_10016"  # principal, pero probaremos alternativas
    EPIC_FIELD_CANDIDATES = [
        "customfield_10016", "customfield_10014",  # ids comunes
        "epic_link", "epicLink", "Epic Link"       # nombres posibles en custom_fields
    ]
    db = DatabaseHelper()
    db.conectar()
    bugs_uat = db.obtener_bugs_proyecto_bug() or []
    db.cerrar()

    epic_to_bugs_uat: dict[str, set] = {}
    def _collect_epic_keys_from_fields(f: dict) -> set:
        keys = set()
        # 0) PRIORIDAD: Buscar en parent.key (como lo hace la pestaña de bugs)
        parent = f.get("parent", {}) or {}
        parent_key = parent.get("key", "") if isinstance(parent, dict) else ""
        if parent_key and isinstance(parent_key, str):
            keys.add(parent_key.strip().upper())
        
        # 1) Campos directos
        for k in EPIC_FIELD_CANDIDATES:
            v = f.get(k)
            if isinstance(v, dict):
                val = (v.get("key") or v.get("id") or v.get("value") or "").strip().upper()
                if val:
                    keys.add(val)
            elif isinstance(v, str) and v.strip():
                keys.add(v.strip().upper())
        # 2) Dentro de custom_fields serializado
        cf = f.get("custom_fields")
        try:
            import json as _json
            if isinstance(cf, str):
                cf_obj = _json.loads(cf)
            elif isinstance(cf, dict):
                cf_obj = cf
            else:
                cf_obj = None
            if isinstance(cf_obj, dict):
                for k in EPIC_FIELD_CANDIDATES:
                    v = cf_obj.get(k)
                    if isinstance(v, dict):
                        val = (v.get("key") or v.get("id") or v.get("value") or "").strip().upper()
                        if val:
                            keys.add(val)
                    elif isinstance(v, str) and v.strip():
                        keys.add(v.strip().upper())
        except Exception:
            pass
        return keys

    for iss in bugs_uat:
        f = iss.get("fields", {}) or {}
        itype = (f.get("issuetype") or {}).get("name") or ""
        if not _es_tipo_bug_uat(itype):
            continue
        bug_key = iss.get("key", "")
        if not bug_key:
            continue
        # 1) Epic Link directo + custom_fields con múltiples candidatos
        epic_keys_found = _collect_epic_keys_from_fields(f)
        # 2) Fallback: buscar claves REP-/TAL- en issuelinks
        if not epic_keys_found:
            for link in (f.get("issuelinks") or []):
                for side in ("inwardIssue", "outwardIssue"):
                    lk = link.get(side) or {}
                    k = (lk.get("key") or "").strip().upper()
                    if k.startswith("REP-") or k.startswith("TAL-"):
                        epic_keys_found.add(k)
        # Registrar por clave de épica (normalizar formato "TAL-3544 [NOMBRE]" -> "TAL-3544")
        import re as _re
        for ek in epic_keys_found:
            if ek:
                # Extraer solo la clave si viene como "TAL-3544 [NOMBRE]"
                ek_clean = ek.strip().upper()  # Normalizar a mayúsculas
                match_key = _re.match(r"^([A-Z]{2,10}-\d+)", ek_clean)
                if match_key:
                    ek_clean = match_key.group(1)  # Solo la parte "TAL-3544"
                epic_to_bugs_uat.setdefault(ek_clean, set()).add(bug_key)

    # ------------------ Tabla de histórico (usa 'epicas_relevantes') - SIN cache, siempre desde BD ------------------
    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except Exception:
            return 99

    # Procesar tabla histórica siempre desde la base de datos (sin cache)
    tabla_historico = []
    # Filtrar solo épicas de postventas (REP y TAL), excluir ATI
    epicas_relevantes = cargar_epicas_relevantes()
    epicas_postventas = [e for e in epicas_relevantes if e["rn"].startswith(("REP-", "TAL-"))]
    for epica_rn in epicas_postventas:
        nombre_epica = epica_rn.get("nombre", "")
        mes_entrega = epica_rn.get("mes_entrega", "")
        epic_match = next((rn for rn in epicas if normalize(nombre_epica) == normalize(rn)), None)

        if epic_match:
            data = epicas[epic_match]
            historias = data["Historias"]
        else:
            # Fallback: buscar por clave de RN (REP-xxx/TAL-xxx)
            historias = epicas_por_key.get(epica_rn.get("rn", ""), {}).get("Historias", [])

        # Métricas por RN (si no hay historias, quedan en 0)
        total = len(historias)
        listas_para_implementar = sum(1 for h in historias if h["Estado"] == "lista para implementar")
        porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
        puntos_totales = sum(h.get("Puntos", 0) or 0 for h in historias)

        # Bugs asociados (REP/TAL) + promedio hs
        hu_keys = [h["Clave"] for h in historias if h.get("Clave")]
        bugs_keys_rep_tal = []
        # Recolectar todos los bugs únicos con sus horas
        bugs_unicos_con_hrs = {}  # {bug_key: hrs} - cada bug aparece una sola vez
        for hu in hu_keys:
            info = mapa_bugs_hu.get(hu)
            if not info:
                continue
            bugs_list = info.get("bugs", [])
            hrs_list = info.get("hrs", [])
            # Para cada bug, agregarlo a la lista y guardar sus horas si no está ya registrado
            for i, bug_key in enumerate(bugs_list):
                bugs_keys_rep_tal.append(bug_key)
                # Guardar horas del bug solo la primera vez que lo encontramos
                if bug_key not in bugs_unicos_con_hrs and i < len(hrs_list):
                    hrs_value = hrs_list[i]
                    if hrs_value is not None:
                        bugs_unicos_con_hrs[bug_key] = hrs_value
        uniq_bugs_rep_tal = sorted(set(bugs_keys_rep_tal))
        bugs_cnt_rep_tal = len(uniq_bugs_rep_tal)
        # Calcular promedio: suma de horas de bugs únicos / cantidad de bugs únicos con horas
        hrs_unicas = [h for h in bugs_unicos_con_hrs.values() if h is not None]
        prom_hrs = round(sum(hrs_unicas) / len(hrs_unicas), 2) if hrs_unicas else None

        # UAT por RN (solo Epic Link)
        # Siempre incluir la clave RN directamente (ej: TAL-3544)
        rn_key = epica_rn.get("rn", "").strip().upper() if epica_rn.get("rn") else ""
        candidate_epic_keys = {rn_key} if rn_key else set()
        # También agregar claves desde rn_to_epic_keys si epic_match existe
        if epic_match:
            for ek in rn_to_epic_keys.get(epic_match, set()):
                if ek:
                    # Normalizar a mayúsculas
                    ek_clean = str(ek).strip().upper()
                    # Limpiar formato "TAL-3544 [NOMBRE]" -> "TAL-3544"
                    import re as _re
                    match_key = _re.match(r"^([A-Z]{2,10}-\d+)", ek_clean)
                    if match_key:
                        ek_clean = match_key.group(1)
                    candidate_epic_keys.add(ek_clean)
        uat_keys = set()
        for ek in candidate_epic_keys:
            if ek:
                # Buscar en mayúsculas
                ek_upper = str(ek).strip().upper()
                uat_keys |= epic_to_bugs_uat.get(ek_upper, set())
        uniq_bugs_uat = sorted(uat_keys)
        bugs_cnt_uat = len(uniq_bugs_uat)
        # Calcular DCR (Defect Containment Rate) = QBug / (QBug + QUAT) * 100
        total_bugs = bugs_cnt_rep_tal + bugs_cnt_uat
        dcr = round((bugs_cnt_rep_tal / total_bugs * 100), 1) if total_bugs > 0 else 0.0

        tabla_historico.append({
            "Épica": nombre_epica,
            "Mes entrega": mes_entrega,
            "%_num": porcentaje_num,
            "Historias": historias,
            "Puntos totales": puntos_totales,
            "Bugs_asociados": bugs_cnt_rep_tal,
            "Bugs_asociados_claves": ", ".join(uniq_bugs_rep_tal),
            "Promedio_resolucion_bugs_hs": prom_hrs,
            "Bugs_pruebas_UAT": bugs_cnt_uat,
            "Bugs_pruebas_UAT_claves": ", ".join(uniq_bugs_uat),
            "DCR_%": dcr,
        })

    tabla_historico = sorted(tabla_historico, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    # ------------------ UI ------------------
    st.markdown("## Histórico de RNs postventa")
    
    if not tabla_historico:
        st.info("No hay datos históricos disponibles.")
    
    # Leyenda de colores DCR
    st.caption("🎨 **DCR**: 🟢 ≥90% (Excelente) | 🔴 <90% (Necesita mejora)")

    # Filtro de entregable (RN)
    colf1, colf2 = st.columns([3,1])
    with colf1:
        buscar_rn = st.text_input("Buscar entregable (RN)", value="", placeholder="Ej: Generar presupuesto")
    with colf2:
        st.caption("Filtra por nombre (ignora acentos y mayúsculas).")

    buscar_norm = normalize(buscar_rn)
    if buscar_norm:
        tabla_filtrada = [r for r in tabla_historico if buscar_norm in normalize(r["Épica"])]
    else:
        tabla_filtrada = tabla_historico

    for row in tabla_filtrada:
        nombre = row["Épica"]
        mes = row["Mes entrega"]
        porcentaje = row["%_num"]
        puntos_totales = row["Puntos totales"]
        historias = row["Historias"]

        bugs_cnt_rep_tal = row["Bugs_asociados"]
        prom_hrs = row["Promedio_resolucion_bugs_hs"]
        prom_txt = f"{prom_hrs:.2f} hs" if prom_hrs is not None else "-"

        bugs_cnt_uat = row.get("Bugs_pruebas_UAT", 0)
        dcr = row.get("DCR_%", 0.0)

        # Color para DCR: Verde si ≥90%, Rojo si <90%
        dcr_color = "🟢" if dcr >= 90 else "🔴"

        expander_title = (
            f"{nombre} | Avance: {porcentaje:.1f}% | {mes} | "
            f"Puntos: {puntos_totales} | Bugs: {bugs_cnt_rep_tal} | UAT: {bugs_cnt_uat} | "
            f"DCR: {dcr_color} {dcr}% | Prom. resolución: {prom_txt}"
        )
        with st.expander(expander_title, expanded=False):
            st.markdown(
                f"**Bugs asociados (REP/TAL):** {bugs_cnt_rep_tal} &nbsp;|&nbsp; "
                f"**Promedio resolución (REP/TAL):** {prom_txt} &nbsp;|&nbsp; "
                f"**Claves REP/TAL:** {row['Bugs_asociados_claves'] or '-'}"
            )
            st.markdown(
                f"**Bugs pruebas UAT (project BUG, Epic Link):** {bugs_cnt_uat} &nbsp;|&nbsp; "
                f"**Claves UAT:** {row.get('Bugs_pruebas_UAT_claves','') or '-'}"
            )
            st.markdown(
                f"**DCR (Defect Containment Rate):** {dcr_color} **{dcr}%** &nbsp;|&nbsp; "
                f"**Fórmula:** QBug / (QBug + QUAT) × 100 = {bugs_cnt_rep_tal} / ({bugs_cnt_rep_tal} + {bugs_cnt_uat}) × 100"
            )
            st.markdown("---")

            if historias:
                for h in historias:
                    estado = h["Estado"]
                    color_estado = (
                        "#39d353" if estado == "lista para implementar"
                        else "#fa4" if "desarroll" in estado
                        else "#bbb"
                    )
                    asignado = h["Asignado"] if h["Asignado"] else "<i>Sin asignar</i>"
                    st.markdown(
                        f"- **{h['Clave']}** — {h['Nombre']} | "
                        f"<span style='color:{color_estado}'>{estado.capitalize()}</span> | "
                        f"{asignado} | <b>Puntos:</b> {h['Puntos']}",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("*Sin historias cargadas*", unsafe_allow_html=True)