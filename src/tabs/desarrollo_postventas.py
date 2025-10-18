"""
Pestaña de Desarrollo Postventas
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import re
import os
import pickle
from src.jira_conexion import get_jira
from src.utils.configuracion import cache_path

def traer_todas_las_issues(jira, jql, fields, max_results=100):
    """Función para traer todas las issues de Jira con paginación"""
    issues = []
    start_at = 0
    while True:
        endpoint = (
            f'search?jql={jql}&fields={fields}&startAt={start_at}&maxResults={max_results}'
        )
        data = jira._get_json(endpoint)
        batch = data.get("issues", [])
        issues.extend(batch)
        if len(batch) < max_results:
            break
        start_at += max_results
    return issues

def obtener_sprint(issue):
    """Extraer el sprint de una issue"""
    sprint = issue["fields"].get("customfield_10021")
    if isinstance(sprint, list) and sprint:
        if isinstance(sprint[-1], dict):
            return sprint[-1].get("name", "Sin Sprint")
        elif isinstance(sprint[-1], str):
            return sprint[-1]
    elif isinstance(sprint, dict):
        return sprint.get("name", "Sin Sprint")
    elif isinstance(sprint, str):
        return sprint
    return "Sin Sprint"

def obtener_version(issue):
    """Extraer la versión de una issue"""
    fix = issue["fields"].get("fixVersions", [])
    if isinstance(fix, list) and fix:
        return fix[-1].get("name", "")
    return ""

def mostrar_desarrollo_postventas(issues_jira):
    """Mostrar la pestaña de Desarrollo Postventas"""
    
    # Obtener conexión a Jira
    jira = get_jira()
    
    # Estados definidos
    ESTADOS_EN_PROCESO = [
        "en desarrollo", "en testing", "en corrección", "por corregir",
        "requiere validación", "en análisis", "sin refinar", "pausada", "en correccion"
    ]
    ESTADO_LISTO_PARA_IMPLEMENTAR = "lista para implementar"
    ESTADO_LISTA_PARA_DESARROLLAR = "lista para desarrollar"

    fields = "key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,fixVersions,customfield_10021,updated,subtasks"
    
    # Cargar historias SIN límite de 6 meses (eliminado según solicitud)
    progress_bar = st.progress(0)
    issues_tal = traer_todas_las_issues(jira, 'project = TAL AND issuetype = Historia', fields)
    progress_bar.progress(0.5)
    issues_rep = traer_todas_las_issues(jira, 'project = REP AND issuetype = Historia', fields)
    progress_bar.progress(1.0)
    issues = issues_tal + issues_rep

    # ---- FILTRO: excluir historias "MADRE" ----
    issues = [i for i in issues if "madre" not in i["fields"].get("summary", "").lower()]

    for issue in issues:
        issue["fields"]["Sprint"] = obtener_sprint(issue)
        issue["fields"]["Version"] = obtener_version(issue)
        issue["fields"]["Proyecto"] = issue["fields"]["project"]["name"]

    regex_version = re.compile(r"\bv\d+\.\d+\b", re.IGNORECASE)
    sprints_con_version = sorted({i["fields"]["Sprint"] for i in issues if i["fields"]["Sprint"] and regex_version.search(i["fields"]["Sprint"])})
    versiones_unicas = sorted({i["fields"]["Version"] for i in issues if i["fields"]["Version"]})

    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        sprint_sel = st.selectbox(
            "Filtrar por sprint (solo sprints con versión)",
            ["Todos"] + sprints_con_version,
            key="filtro_sprint_velocidad"
        )
    with col2:
        version_sel = st.selectbox(
            "Filtrar por versión",
            ["Todas"] + versiones_unicas,
            key="filtro_version_velocidad"
        )
    with col3:
        usuarios_asignados = sorted(list({i["fields"]["assignee"]["displayName"]
                                      for i in issues if i["fields"].get("assignee")}))
        usuarios_asignados = ["Todos"] + usuarios_asignados
        usuario_seleccionado = st.selectbox(
            "Usuario asignado",
            usuarios_asignados,
            index=0,
            key="usuario_asignado_dev_velocidad"
        )
    with col4:
        # Botón para forzar actualización
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="desarrollo_postventas_actualizar"):
            # Limpiar todos los caches relacionados con desarrollo postventas
            cache_keys_to_clear = [
                "desarrollo_tal_issues",
                "desarrollo_rep_issues", 
                "desarrollo_bugs_rep",
                "desarrollo_bugs_tal",
                "desarrollo_bugs_uat"
            ]
            
            # También limpiar cache de subtareas
            import glob
            subtareas_cache_files = glob.glob("cache/desarrollo_subtareas_*.pkl")
            for cache_file in subtareas_cache_files:
                try:
                    os.remove(cache_file)
                except Exception:
                    pass
            
            for cache_key in cache_keys_to_clear:
                cache_file = cache_path(cache_key, 'pkl')
                if os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                    except Exception:
                        pass
            
            st.success("✅ Cache limpiado. Recargando datos...")
            st.rerun()

    # ---- FILTROS ----
    if sprint_sel == "Todos":
        issues_filtradas = [i for i in issues if i["fields"]["Sprint"] and regex_version.search(i["fields"]["Sprint"])]
    else:
        issues_filtradas = [i for i in issues if i["fields"]["Sprint"] == sprint_sel]
    if version_sel != "Todas":
        issues_filtradas = [i for i in issues_filtradas if i["fields"]["Version"] == version_sel]
    if usuario_seleccionado != "Todos":
        issues_filtradas = [i for i in issues_filtradas if i["fields"].get("assignee") and i["fields"]["assignee"]["displayName"] == usuario_seleccionado]

    # ==== CONTADORES DE PORCENTAJE ====
    if version_sel != "Todas":
        historias_version = [i for i in issues if i["fields"]["Version"] == version_sel and "madre" not in i["fields"].get("summary", "").lower()]
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

    for issue in issues_filtradas:
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

    # -- Construcción de filas --
    rows = []
    for issue in issues_filtradas:
        estado = issue["fields"]["status"]["name"]
        epic_name = None
        if "parent" in issue["fields"] and issue["fields"]["parent"]:
            parent = issue["fields"]["parent"]
            if "summary" in parent:
                epic_name = parent["summary"]
            elif "fields" in parent and "summary" in parent["fields"]:
                epic_name = parent["fields"]["summary"]
        if not epic_name:
            epica_custom = issue["fields"].get("customfield_10016", None)
            if epica_custom and isinstance(epica_custom, dict) and "value" in epica_custom:
                epic_name = epica_custom["value"]
            elif epica_custom:
                epic_name = str(epica_custom)
        if not epic_name:
            epic_name = "Sin épica"

        puntos = issue["fields"].get("customfield_10026", "")
        try:
            puntos = float(puntos)
        except (TypeError, ValueError):
            puntos = 0

        fila = {
            "Clave": issue["key"],
            "Resumen": issue["fields"]["summary"],
            "Estado": estado,
            "Proyecto": issue["fields"]["Proyecto"],
            "Epica": epic_name,
            "Asignado": None,
            "Sprint": issue["fields"]["Sprint"],
            "Version": issue["fields"]["Version"],
            "Fecha en que la tomó": issue["fields"].get("statuscategorychangedate", "")[:10] if issue["fields"].get("statuscategorychangedate") else "",
            "Fecha finalización": issue["fields"].get("duedate", "Sin fecha de fin"),
            "Porcentaje avance": "Sin calcular",
            "Puntos": puntos
        }

        if issue["fields"].get("assignee"):
            fila["Asignado"] = issue["fields"]["assignee"]["displayName"]

        rows.append(fila)

    mostrar_todas = st.checkbox("Mostrar todas las historias filtradas (no solo las que están en desarrollo)", value=False)

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
        calcular_avance = st.checkbox("Mostrar % de avance de subtareas (puede demorar)", value=False, key="avance_subtareas_velocidad")
        if calcular_avance:
            st.info("⏳ Calculando avance de subtareas... Esto puede tomar unos momentos.")
            # Cache para estados de subtareas
            cache_key_subtareas = f"desarrollo_subtareas_{sprint_sel}_{version_sel}_{usuario_seleccionado}"
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
                if not issue:
                    fila["Porcentaje avance"] = "Sin subtareas"
                    continue
                subtasks = issue["fields"].get("subtasks", [])
                if subtasks:
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
        else:
            for fila in rows_a_mostrar:
                fila["Porcentaje avance"] = "Sin calcular"

        df_tabla = pd.DataFrame(rows_a_mostrar)
        df_tabla["Puntos"] = pd.to_numeric(df_tabla["Puntos"], errors="coerce").fillna(0).astype(float)
        st.dataframe(
            df_tabla[["Clave", "Resumen", "Epica", "Puntos", "Asignado", "Sprint", "Proyecto", "Version", "Fecha en que la tomó", "Fecha finalización", "Porcentaje avance", "Estado"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption('Nota: "% de avance" se calcula por subtareas solo si tildás la opción, así la carga es mucho más rápida.')

    # ========== GANTT ==========
    st.markdown("---")
    st.subheader("Gantt: Historias EN DESARROLLO (con fechas válidas)")

    gantt_rows = [
        fila for fila in rows
        if fila["Estado"].strip().lower() == "en desarrollo" and fila["Fecha finalización"] != "Sin fecha de fin"
    ]
    gantt_df = pd.DataFrame(gantt_rows)
    if not gantt_df.empty:
        gantt_df["Inicio"] = pd.to_datetime(gantt_df["Fecha en que la tomó"], errors="coerce")
        gantt_df["Fin"] = pd.to_datetime(gantt_df["Fecha finalización"], errors="coerce")
        gantt_df["Puntos"] = pd.to_numeric(gantt_df["Puntos"], errors="coerce").fillna(0).astype(float)
        gantt_df = gantt_df[gantt_df["Inicio"].notnull() & gantt_df["Fin"].notnull()]
        if gantt_df.empty:
            st.info("No hay historias con fechas válidas para mostrar en el Gantt.")
        else:
            import plotly.express as px
            fig = px.timeline(
                gantt_df,
                x_start="Inicio",
                x_end="Fin",
                y="Clave",
                color="Asignado",
                hover_data=["Resumen", "Puntos", "Sprint", "Proyecto", "Version"]
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(title='Historias EN DESARROLLO (Gantt)')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay historias en desarrollo con fecha de vencimiento para mostrar en el Gantt.")