"""
Pestaña Histórico ATI - Tablero SUMMA
Implementa la lógica completa del histórico ATI
"""

import streamlit as st
import pandas as pd
import unicodedata
import re
import time
import os
import pickle
from datetime import datetime, timedelta
from jira_conexion import get_jira
from utils.configuracion import cache_path, cargar_epicas_relevantes

def mostrar_historico_ati(epicas_relevantes, issues_jira):
    """Mostrar la pestaña de Histórico ATI"""
    
    # Crear diccionario inverso name_to_acc
    import json
    with open('data/accountid_to_name.json', 'r', encoding='utf-8') as f:
        accountid_to_name = json.load(f)
    name_to_acc = {v: k for k, v in accountid_to_name.items()}

    # ------------------ Helpers ------------------
    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    def _status_norm(s: str) -> str:
        return (s or "").strip().lower()

    def _safe_issue_key(iss) -> str:
        return (iss.get("key") or iss.get("id") or "") if isinstance(iss, dict) else ""

    def _unwrap_issue(iss):
        if isinstance(iss, dict) and "fields" in iss:
            return iss
        return {"key": str(iss), "fields": {}}

    def traer_todos_las_issues(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
        while True:
            endpoint = f'search?jql={jql}&fields={fields}&startAt={start_at}&maxResults={max_results}'
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    def traer_bugs_con_changelog(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
        while True:
            endpoint = (f'search?jql={jql}&fields={fields}'
                        f'&expand=changelog&startAt={start_at}&maxResults={max_results}')
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    # --- FIX: cálculo robusto de horas desde changelog (con fallbacks) ---
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

        delta_hs = (end_dt - start_dt).total_seconds() / 3600.0
        return None if delta_hs < 0 else float(delta_hs)

    def _bugs_por_hu(bugs_issues) -> dict:
        """
        Dict { HU_KEY: {"bugs": [bug_key,...], "hrs": [resol_horas,...]} }
        Para bugs de ATI (métrica 'Bugs asociados' + promedio hs).
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

    def detectar_campo_epic_link():
        try:
            jira = get_jira()
            fields = jira._get_json("field")
            candidatos = []
            for f in fields:
                name = (f.get("name") or "").strip().lower()
                key  = (f.get("key") or f.get("id") or "").strip()
                if any(x in name for x in ["epic link", "enlace épico", "enlace epico", "epik link"]):
                    candidatos.append(key)
            for c in candidatos:
                if c.startswith("customfield_"):
                    return c
            return candidatos[0] if candidatos else None
        except Exception:
            return None

    def _es_tipo_bug_uat(issuetype_name: str) -> bool:
        n = (issuetype_name or "").lower()
        return any(k in n for k in ("bug", "error", "defecto", "incidencia"))

    # ------------------ Fuente de datos ------------------
    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    # Historias ATI → base de RN (con cache)
    fields_hist = ("key,summary,status,project,issuetype,assignee,parent,"
                   "customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated")
    
    # Cache para issues de ATI - OPTIMIZADO para primera carga
    cache_key_ati = "desarrollo_ati_issues"
    cache_file_ati = cache_path(cache_key_ati, 'pkl')
    
    jira = get_jira()
    
    # Cargar desde cache o consultar Jira con límites para primera carga rápida
    try:
        if os.path.exists(cache_file_ati):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_ati))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_ati, 'rb') as f:
                    issues_ati = pickle.load(f)
            else:
                issues_ati = traer_todos_las_issues(jira, 'project = ATI AND issuetype = Historia ORDER BY updated DESC', fields_hist)
                with open(cache_file_ati, 'wb') as f:
                    pickle.dump(issues_ati, f)
        else:
            issues_ati = traer_todos_las_issues(jira, 'project = ATI AND issuetype = Historia ORDER BY updated DESC', fields_hist)
            with open(cache_file_ati, 'wb') as f:
                pickle.dump(issues_ati, f)
    except Exception:
        issues_ati = traer_todos_las_issues(jira, 'project = ATI AND issuetype = Historia ORDER BY updated DESC', fields_hist)
    
    issues = issues_ati

    # Desduplico por key
    issues = [_unwrap_issue(iss) for iss in issues]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # Map RN (nombre de épica) → historias y → set de EPIC KEYS (para UAT)
    EPIC_LINK_CAMPO_STORY = "customfield_10016"
    epicas = {}              # { RN_name: {"Historias": [...] } }
    rn_to_epic_keys = {}     # { RN_name: set([EPIC-123,...]) }

    # Filtrar solo issues de ATI
    issues_ati_filtered = [i for i in issues if i["fields"]["project"]["key"] == "ATI"]

    for issue in issues_ati_filtered:
        f = issue.get("fields", {}) or {}

        # RN/Épica (nombre) desde parent.summary (o custom)
        epic_name = None
        parent = f.get("parent")
        parent_key = None
        if parent:
            epic_name = (parent.get("summary") or (parent.get("fields") or {}).get("summary"))
            parent_key = (parent.get("key") or (parent.get("fields") or {}).get("key"))
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            epica_custom = f.get(EPIC_LINK_CAMPO_STORY, None)
            if isinstance(epica_custom, dict) and epica_custom.get("value"):
                epic_name = epica_custom["value"]
            elif isinstance(epica_custom, str) and epica_custom:
                epic_name = epica_custom
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

        epicas.setdefault(epic_name, {"Historias": []})["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos,
        })
        if parent_key:
            rn_to_epic_keys.setdefault(epic_name, set()).add(parent_key)

    # Bugs ATI con changelog (para 'Bugs asociados' y promedio hs) - con cache
    fields_bugs_ati = "key,project,issuetype,status,resolutiondate,assignee,parent,issuelinks,created,updated"
    
    # Cache para bugs de ATI
    cache_key_bugs_ati = "desarrollo_bugs_ati"
    cache_file_bugs_ati = cache_path(cache_key_bugs_ati, 'pkl')
    
    try:
        if os.path.exists(cache_file_bugs_ati):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_ati))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_ati, 'rb') as f:
                    bugs_ati = pickle.load(f)
            else:
                bugs_ati = traer_bugs_con_changelog(jira, 'project = ATI AND issuetype = Error ORDER BY updated DESC', fields_bugs_ati)
                with open(cache_file_bugs_ati, 'wb') as f:
                    pickle.dump(bugs_ati, f)
        else:
            bugs_ati = traer_bugs_con_changelog(jira, 'project = ATI AND issuetype = Error ORDER BY updated DESC', fields_bugs_ati)
            with open(cache_file_bugs_ati, 'wb') as f:
                pickle.dump(bugs_ati, f)
    except Exception:
        bugs_ati = traer_bugs_con_changelog(jira, 'project = ATI AND issuetype = Error ORDER BY updated DESC', fields_bugs_ati)
    
    bugs_all = bugs_ati
    mapa_bugs_hu = _bugs_por_hu(bugs_all)

    # BUGS UAT (project = BUG) — SOLO por Epic Link - con cache
    EPIC_FIELD_BUG = detectar_campo_epic_link() or "customfield_10016"
    fields_bugs_uat = f"key,issuetype,created,{EPIC_FIELD_BUG}"
    
    cache_key_bugs_uat = "desarrollo_bugs_uat_ati"
    cache_file_bugs_uat = cache_path(cache_key_bugs_uat, 'pkl')
    
    try:
        if os.path.exists(cache_file_bugs_uat):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_uat))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_uat, 'rb') as f:
                    bugs_uat = pickle.load(f)
            else:
                bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat)
                with open(cache_file_bugs_uat, 'wb') as f:
                    pickle.dump(bugs_uat, f)
        else:
            bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat)
            with open(cache_file_bugs_uat, 'wb') as f:
                pickle.dump(bugs_uat, f)
    except Exception:
        bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat)

    epic_to_bugs_uat: dict[str, set] = {}
    for iss in bugs_uat:
        f = iss.get("fields", {}) or {}
        itype = (f.get("issuetype") or {}).get("name") or ""
        if not _es_tipo_bug_uat(itype):
            continue
        bug_key = iss.get("key", "")
        if not bug_key:
            continue
        epic_ref = f.get(EPIC_FIELD_BUG)
        epic_key = ""
        if isinstance(epic_ref, dict):
            epic_key = (epic_ref.get("key") or epic_ref.get("id") or "").strip()
        elif isinstance(epic_ref, str):
            epic_key = epic_ref.strip()
        if epic_key:
            epic_to_bugs_uat.setdefault(epic_key, set()).add(bug_key)

    # ------------------ Tabla de histórico (usa 'epicas_relevantes') - con cache ------------------
    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except Exception:
            return 99

    # Cache para tabla histórica procesada
    cache_key_historico = "historico_tabla_procesada_ati"
    cache_file_historico = cache_path(cache_key_historico, 'pkl')
    
    # Intentar cargar tabla histórica desde cache
    tabla_historico = []
    try:
        if os.path.exists(cache_file_historico):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_historico))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_historico, 'rb') as f:
                    tabla_historico = pickle.load(f)
                    # Verificar si el cache tiene el campo DCR_% (nuevo campo)
                    if tabla_historico and "DCR_%" not in tabla_historico[0]:
                        # Cache antiguo sin DCR, limpiarlo para recalcular
                        os.remove(cache_file_historico)
                        tabla_historico = []
    except Exception:
        pass
    
    # Botón para limpiar cache del histórico
    if st.button("🗑️ Limpiar Cache Histórico", help="Limpia el cache del histórico para regenerar datos"):
        cache_file_historico = cache_path("historico_ati", 'pkl')
        if os.path.exists(cache_file_historico):
            os.remove(cache_file_historico)
        st.success("✅ Cache del histórico limpiado. Recargando datos...")
        st.rerun()

    # Si no hay cache, procesar tabla histórica
    if not tabla_historico:
        st.info("⏳ **Procesando datos históricos de ATI**... Esto puede tomar unos minutos la primera vez.")
        tabla_historico = []
        # Filtrar solo épicas de ATI
        epicas_ati = [e for e in epicas_relevantes if e["rn"].startswith("ATI-")]
        for epica_rn in epicas_ati:
            nombre_epica = epica_rn.get("nombre", "")
            mes_entrega = epica_rn.get("mes_entrega", "")
            epic_match = next((rn for rn in epicas if normalize(nombre_epica) == normalize(rn)), None)

            if epic_match:
                data = epicas[epic_match]
                historias = data["Historias"]
                total = len(historias)
                listas_para_implementar = sum(1 for h in historias if h["Estado"] == "lista para implementar")
                porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
                puntos_totales = sum(h.get("Puntos", 0) or 0 for h in historias)

                # Bugs asociados (ATI) + promedio hs
                hu_keys = [h["Clave"] for h in historias if h.get("Clave")]
                bugs_keys_ati, bugs_hrs = [], []
                for hu in hu_keys:
                    info = mapa_bugs_hu.get(hu)
                    if not info:
                        continue
                    bugs_keys_ati.extend(info.get("bugs", []))
                    bugs_hrs.extend(info.get("hrs", []))
                uniq_bugs_ati = sorted(set(bugs_keys_ati))
                bugs_cnt_ati = len(uniq_bugs_ati)
                prom_hrs = round(sum(bugs_hrs) / len(bugs_hrs), 2) if bugs_hrs else None

                # UAT por RN (solo Epic Link)
                candidate_epic_keys = rn_to_epic_keys.get(epic_match, set())
                uat_keys = set()
                for ek in candidate_epic_keys:
                    uat_keys |= epic_to_bugs_uat.get(ek, set())
                uniq_bugs_uat = sorted(uat_keys)
                bugs_cnt_uat = len(uniq_bugs_uat)
                
                # Calcular DCR (Defect Containment Rate) = QBug / (QBug + QUAT) * 100
                total_bugs = bugs_cnt_ati + bugs_cnt_uat
                dcr = round((bugs_cnt_ati / total_bugs * 100), 1) if total_bugs > 0 else 0.0
                    
            else:
                historias = []
                porcentaje_num = 0
                puntos_totales = 0
                uniq_bugs_ati, bugs_cnt_ati, prom_hrs = [], 0, None
                uniq_bugs_uat, bugs_cnt_uat = [], 0
                dcr = 0.0  # Sin datos, DCR = 0

            tabla_historico.append({
                "Épica": nombre_epica,
                "Mes entrega": mes_entrega,
                "%_num": porcentaje_num,
                "Historias": historias,
                "Puntos totales": puntos_totales,
                "Bugs_asociados": bugs_cnt_ati,
                "Bugs_asociados_claves": ", ".join(uniq_bugs_ati),
                "Promedio_resolucion_bugs_hs": prom_hrs,
                "Bugs_pruebas_UAT": bugs_cnt_uat,
                "Bugs_pruebas_UAT_claves": ", ".join(uniq_bugs_uat),
                "DCR_%": dcr,
            })
        
        # Guardar tabla histórica en cache
        try:
            with open(cache_file_historico, 'wb') as f:
                pickle.dump(tabla_historico, f)
        except Exception:
            pass

    tabla_historico = sorted(tabla_historico, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    # ------------------ UI ------------------
    st.markdown("## Histórico de RNs ATI")
    
    # Mostrar información sobre datos limitados en primera carga
    if not tabla_historico:
        st.info("🔄 Cargando datos limitados para primera carga rápida...")
    else:
        st.caption("ℹ️ **Primera carga optimizada**: Mostrando datos más recientes. Usa 'Actualizar' para datos completos.")
    
    # Leyenda de colores DCR
    st.caption("🎨 **DCR**: 🟢 ≥90% (Excelente) | 🔴 <90% (Necesita mejora)")
    
    # Verificar si hay DCR mal calculado y mostrar advertencia
    dcr_mal_calculado = any(row.get("DCR_%", 0) == 0.0 and row.get("Bugs_asociados", 0) > 0 for row in tabla_historico)
    if dcr_mal_calculado:
        st.warning("⚠️ **DCR mal calculado detectado**. Usa 'Actualizar' para recalcular con la fórmula correcta.")

    # Filtro de entregable (RN)
    colf1, colf2, colf3 = st.columns([2,1,1])
    with colf1:
        buscar_rn = st.text_input("Buscar entregable (RN)", value="", placeholder="Ej: Generar presupuesto")
    with colf2:
        st.caption("Filtra por nombre (ignora acentos y mayúsculas).")
    with colf3:
        # Botón para forzar actualización
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="historico_ati_actualizar"):
            # Limpiar todos los caches relacionados con histórico ATI
            cache_keys_to_clear = [
                "desarrollo_ati_issues",
                "desarrollo_bugs_ati",
                "desarrollo_bugs_uat_ati",
                "historico_tabla_procesada_ati"  # Cache de tabla con nuevo campo DCR
            ]
            
            for cache_key in cache_keys_to_clear:
                cache_file = cache_path(cache_key, 'pkl')
                if os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                    except Exception:
                        pass
            
            st.success("✅ Cache limpiado. Recargando datos...")
            st.rerun()

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

        bugs_cnt_ati = row["Bugs_asociados"]
        prom_hrs = row["Promedio_resolucion_bugs_hs"]
        prom_txt = f"{prom_hrs:.2f} hs" if prom_hrs is not None else "-"

        bugs_cnt_uat = row.get("Bugs_pruebas_UAT", 0)
        dcr = row.get("DCR_%", 0.0)

        # Color para DCR: Verde si ≥90%, Rojo si <90%
        dcr_color = "🟢" if dcr >= 90 else "🔴"

        expander_title = (
            f"{nombre} | Avance: {porcentaje:.1f}% | {mes} | "
            f"Puntos: {puntos_totales} | Bugs: {bugs_cnt_ati} | UAT: {bugs_cnt_uat} | "
            f"DCR: {dcr_color} {dcr}% | Prom. resolución: {prom_txt}"
        )
        with st.expander(expander_title, expanded=False):
            st.markdown(
                f"**Bugs asociados (ATI):** {bugs_cnt_ati} &nbsp;|&nbsp; "
                f"**Promedio resolución (ATI):** {prom_txt} &nbsp;|&nbsp; "
                f"**Claves ATI:** {row['Bugs_asociados_claves'] or '-'}"
            )
            st.markdown(
                f"**Bugs pruebas UAT (project BUG, Epic Link):** {bugs_cnt_uat} &nbsp;|&nbsp; "
                f"**Claves UAT:** {row.get('Bugs_pruebas_UAT_claves','') or '-'}"
            )
            st.markdown(
                f"**DCR (Defect Containment Rate):** {dcr_color} **{dcr}%** &nbsp;|&nbsp; "
                f"**Fórmula:** QBug / (QBug + QUAT) × 100 = {bugs_cnt_ati} / ({bugs_cnt_ati} + {bugs_cnt_uat}) × 100"
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