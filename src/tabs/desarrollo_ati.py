"""
Pestaña Desarrollo ATI - Tablero SUMMA
Implementa la lógica completa del desarrollo ATI
"""

import streamlit as st
import pandas as pd
import time
import os
import pickle
from datetime import datetime, timedelta
from jira_conexion import get_jira
from utils.configuracion import cache_path

def mostrar_desarrollo_ati(issues_jira):
    """Mostrar la pestaña de Desarrollo ATI"""
    
    # Funciones duplicadas eliminadas
    
    def traer_todas_las_issues(jira, jql, fields, max_results=100):
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

    def get_issue_summary(issue_key, cache):
        if issue_key in cache:
            return cache[issue_key]
        try:
            jira = get_jira()
            issue = jira.issue(issue_key)
            summary = issue.fields.summary
            cache[issue_key] = summary
            return summary
        except Exception:
            cache[issue_key] = issue_key
            return issue_key

    def get_fix_version(issue):
        fix = issue["fields"].get("fixVersions", [])
        if isinstance(fix, list) and fix:
            return fix[-1].get("name", "")
        return ""

    ESTADOS_EN_PROCESO = [
        "en desarrollo", "en testing", "en corrección", "por corregir",
        "requiere validación", "en análisis", "sin refinar", "pausada", "en correccion"
    ]
    ESTADO_LISTO_PARA_IMPLEMENTAR = "lista para implementar"
    ESTADO_LISTA_PARA_DESARROLLAR = "lista para desarrollar"

    fields = "key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,fixVersions,customfield_10021,updated,subtasks"
    
    # Cache para issues de ATI
    cache_key_ati_desarrollo = "desarrollo_ati_issues"
    cache_file_ati_desarrollo = cache_path(cache_key_ati_desarrollo, 'pkl')
    
    jira = get_jira()
    
    try:
        if os.path.exists(cache_file_ati_desarrollo):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_ati_desarrollo))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_ati_desarrollo, 'rb') as f:
                    issues_ati = pickle.load(f)
            else:
                progress_bar = st.progress(0)
                issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia AND created >= "2025-05-01"', fields)
                progress_bar.progress(1.0)
                with open(cache_file_ati_desarrollo, 'wb') as f:
                    pickle.dump(issues_ati, f)
        else:
            progress_bar = st.progress(0)
            issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia AND created >= "2025-05-01"', fields)
            progress_bar.progress(1.0)
            with open(cache_file_ati_desarrollo, 'wb') as f:
                pickle.dump(issues_ati, f)
    except Exception:
        issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia AND created >= "2025-05-01"', fields)

    # Función _unwrap_issue duplicada eliminada
    def _unwrap_issue(issue):
        """Función helper para unwrap issues"""
        if isinstance(issue, dict) and "fields" in issue:
            return issue
        return issue

    def _safe_issue_key(iss) -> str:
        return (iss.get("key") or iss.get("id") or "") if isinstance(iss, dict) else ""

    issues = [_unwrap_issue(iss) for iss in issues_ati]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # ==== FILTROS ====
    st.subheader("Filtros")
    cols = st.columns([1, 1, 1, 1])
    
    with cols[0]:
        version_sel = st.selectbox("Versión", ["Todas"] + sorted(set(get_fix_version(i) for i in issues if get_fix_version(i))), key="ati_version")
    with cols[1]:
        usuario_seleccionado = st.selectbox("Usuario", ["Todos"] + sorted(set(i["fields"]["assignee"]["displayName"] for i in issues if i["fields"].get("assignee"))), key="ati_usuario")
    with cols[2]:
        estado_sel = st.selectbox("Estado", ["Todos"] + sorted(set(i["fields"]["status"]["name"] for i in issues)), key="ati_estado")
    with cols[3]:
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="ati_desarrollo_actualizar"):
            # Limpiar cache de ATI desarrollo
            cache_keys_to_clear = ["desarrollo_ati_issues"]
            
            for cache_key in cache_keys_to_clear:
                cache_file = cache_path(cache_key, 'pkl')
                if os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                    except Exception:
                        pass
            
            st.success("✅ Cache limpiado. Recargando datos...")
            st.rerun()

    # ==== CONTADORES DE PORCENTAJE ====
    if version_sel != "Todas":
        historias_version = [i for i in issues if get_fix_version(i) == version_sel and "madre" not in i["fields"].get("summary", "").lower()]
        total_hist = len(historias_version)
        listas_implementar = [i for i in historias_version if i["fields"]["status"]["name"].strip().lower() == ESTADO_LISTO_PARA_IMPLEMENTAR]
        total_listas = len(listas_implementar)
        en_proceso = [i for i in historias_version if i["fields"]["status"]["name"].strip().lower() in ESTADOS_EN_PROCESO]
        total_proceso = len(en_proceso)
        porcentaje_avance = (total_listas / total_hist * 100) if total_hist > 0 else 0
        porcentaje_proceso = (total_proceso / total_hist * 100) if total_hist > 0 else 0

        cols = st.columns(2)
        cols[0].metric("% Avance", f"{porcentaje_avance:.1f}%")
        cols[1].metric("% En proceso", f"{porcentaje_proceso:.1f}%")

    # ==== ALERTAS ====
    hoy = datetime.now().date()
    alertas_vencidas = []
    alertas_proximas = []

    for issue in issues:
        estado = issue["fields"]["status"]["name"].strip().lower()
        fecha_fin_str = issue["fields"].get("duedate", "")
        asignado = issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else ""
        if estado == "en desarrollo" and fecha_fin_str:
            try:
                fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
                dias_a_vencer = (fecha_fin - hoy).days
                alerta_row = {
                    "Clave": issue["key"],
                    "Resumen": issue["fields"]["summary"],
                    "Asignado": asignado,
                    "Fecha de fin": fecha_fin.strftime("%d/%m/%Y"),
                    "Estado": estado.capitalize()
                }
                if fecha_fin < hoy:
                    alertas_vencidas.append(alerta_row)
                elif 0 <= dias_a_vencer <= 2:
                    alertas_proximas.append(alerta_row)
            except Exception:
                pass

    if alertas_vencidas:
        st.error("⚠️ Historias EN DESARROLLO con fecha de fin vencida:")
        df_vencidas = pd.DataFrame(alertas_vencidas)
        st.dataframe(df_vencidas, use_container_width=True, hide_index=True)
    if alertas_proximas:
        st.warning("⏳ Historias EN DESARROLLO que vencen en <= 2 días:")
        df_proximas = pd.DataFrame(alertas_proximas)
        st.dataframe(df_proximas, use_container_width=True, hide_index=True)
    if not alertas_vencidas and not alertas_proximas:
        st.success("No hay historias en desarrollo vencidas ni próximas a vencer.")

    # ==== FILTRADO DE ISSUES ====
    issues_filtradas = issues.copy()
    
    if version_sel != "Todas":
        issues_filtradas = [i for i in issues_filtradas if get_fix_version(i) == version_sel]
    
    if usuario_seleccionado != "Todos":
        issues_filtradas = [i for i in issues_filtradas if i["fields"].get("assignee") and i["fields"]["assignee"]["displayName"] == usuario_seleccionado]
    
    if estado_sel != "Todos":
        issues_filtradas = [i for i in issues_filtradas if i["fields"]["status"]["name"] == estado_sel]

    # ==== PROCESAMIENTO DE DATOS ====
    rows = []
    for issue in issues_filtradas:
        fila = {
            "Clave": issue["key"],
            "Resumen": issue["fields"]["summary"],
            "Estado": issue["fields"]["status"]["name"],
            "Proyecto": issue["fields"]["project"]["key"],
            "Asignado": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Sin asignar",
            "Duedate": issue["fields"].get("duedate", ""),
            "Version": get_fix_version(issue),
            "Puntos": issue["fields"].get("customfield_10026", 0),
            "Porcentaje avance": "Sin subtareas"
        }

        if issue["fields"].get("assignee"):
            fila["Asignado"] = issue["fields"]["assignee"]["displayName"]

        rows.append(fila)

    mostrar_todas = st.checkbox("Mostrar todas las historias filtradas (no solo las que están en desarrollo)", value=False, key="ati_mostrar_todas")

    estados = {}
    for fila in rows:
        estado = fila["Estado"]
        estados[estado] = estados.get(estado, 0) + 1
    estado_names = sorted(estados.keys())
    if estado_names:
        cols = st.columns(len(estado_names))
        for col, estado in zip(cols, estado_names):
            col.metric(label=estado, value=estados[estado])

    # Tabla
    if mostrar_todas:
        rows_a_mostrar = rows
        label_tabla = "Todas las historias filtradas"
    else:
        rows_a_mostrar = [r for r in rows if r["Estado"].strip().lower() == "en desarrollo"]
        label_tabla = "Todas las historias EN DESARROLLO"

    st.markdown(f"### {label_tabla}")

    if not rows_a_mostrar:
        st.info("No hay historias para mostrar con los filtros seleccionados.")
    else:
        calcular_avance = st.checkbox("Mostrar % de avance de subtareas (puede demorar)", value=False, key="avance_subtareas_ati")
        if calcular_avance:
            # Cache para estados de subtareas
            cache_key_subtareas = f"desarrollo_subtareas_ati_{version_sel}_{usuario_seleccionado}"
            cache_file_subtareas = cache_path(cache_key_subtareas, 'pkl')
            
            # Intentar cargar desde cache
            subtareas_cache = {}
            try:
                if os.path.exists(cache_file_subtareas):
                    mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_subtareas))
                    if (datetime.now() - mtime) < timedelta(hours=48):
                        with open(cache_file_subtareas, 'rb') as f:
                            subtareas_cache = pickle.load(f)
            except Exception:
                pass
            
            for fila in rows_a_mostrar:
                issue = next((i for i in issues if i["key"] == fila["Clave"]), None)
                if issue and issue["fields"].get("subtasks"):
                    subtasks = issue["fields"]["subtasks"]
                    total = len(subtasks)
                    hechas = 0
                    
                    for stask in subtasks:
                        st_key = stask["key"]
                        
                        # Usar cache si está disponible
                        if st_key in subtareas_cache:
                            st_status = subtareas_cache[st_key]
                        else:
                            try:
                                st_info = jira._get_json(f'issue/{st_key}?fields=status')
                                st_status = st_info["fields"]["status"]["name"]
                                subtareas_cache[st_key] = st_status  # Guardar en cache
                            except Exception:
                                st_status = "Unknown"
                                subtareas_cache[st_key] = st_status
                        
                        if st_status.lower() in ESTADOS_EN_PROCESO or st_status.lower() == ESTADO_LISTO_PARA_IMPLEMENTAR:
                            hechas += 1
                    fila["Porcentaje avance"] = f"{round(100 * hechas / total, 1)} %"
                else:
                    fila["Porcentaje avance"] = "Sin subtareas"
            
            # Guardar cache de subtareas
            try:
                with open(cache_file_subtareas, 'wb') as f:
                    pickle.dump(subtareas_cache, f)
            except Exception:
                pass

        df = pd.DataFrame(rows_a_mostrar)
        st.dataframe(df, use_container_width=True)