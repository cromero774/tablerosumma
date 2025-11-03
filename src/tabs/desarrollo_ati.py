"""
Pestaña Desarrollo ATI - Tablero SUMMA
Implementa la lógica completa del desarrollo ATI
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from src.utils.database_helper import DatabaseHelper

def mostrar_desarrollo_ati(issues_jira):
    """Mostrar la pestaña de Desarrollo ATI"""
    
    # Mostrar fecha de última actualización
    db = DatabaseHelper()
    db.conectar()
    fecha_actualizacion = db.obtener_fecha_ultima_actualizacion()
    db.cerrar()
    st.caption(f"🕒 **Última actualización:** {fecha_actualizacion}")
    
    # Inicializar DatabaseHelper
    db = DatabaseHelper()
    
    ESTADOS_EN_PROCESO = [
        "en desarrollo", "en testing", "en corrección", "por corregir",
        "requiere validación", "en análisis", "sin refinar", "pausada", "en correccion"
    ]
    ESTADO_LISTO_PARA_IMPLEMENTAR = "lista para implementar"
    ESTADO_LISTA_PARA_DESARROLLAR = "lista para desarrollar"

    # Cargar historias desde la base de datos
    progress_bar = st.progress(0)
    issues = db.obtener_historias_con_transiciones(proyectos=["ATI"], fecha_desde='2020-01-01', incluir_sin_puntos=True)
    progress_bar.progress(1.0)

    # ---- FILTRO: excluir historias "MADRE" ----
    issues = [i for i in issues if "madre" not in i["fields"].get("summary", "").lower()]
    
    # Agregar campos Sprint y Version para compatibilidad
    for issue in issues:
        issue["fields"]["Sprint"] = issue["fields"].get("sprint") or "Sin Sprint"
        issue["fields"]["Version"] = issue["fields"].get("version") or ""
    
    def get_fix_version(issue):
        """Obtener versión desde el campo version almacenado en BD"""
        return issue["fields"].get("Version", "") or ""

    # ==== FILTROS ====
    st.subheader("Filtros")
    cols = st.columns(3)
    
    with cols[0]:
        versiones_unicas = sorted(set(get_fix_version(i) for i in issues if get_fix_version(i)))
        version_sel = st.selectbox("Versión", ["Todas"] + versiones_unicas, key="ati_version")
    with cols[1]:
        usuarios_asignados = sorted(list({
            i["fields"]["assignee"]["displayName"]
            for i in issues 
            if i["fields"].get("assignee") and i["fields"]["assignee"].get("displayName")
        }))
        usuario_seleccionado = st.selectbox("Usuario", ["Todos"] + usuarios_asignados, key="ati_usuario")
    with cols[2]:
        estados_unicos = sorted(set(i["fields"]["status"]["name"] for i in issues))
        estado_sel = st.selectbox("Estado", ["Todos"] + estados_unicos, key="ati_estado")

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
        asignado = ""
        if issue["fields"].get("assignee") and issue["fields"]["assignee"].get("displayName"):
            asignado = issue["fields"]["assignee"]["displayName"]
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
        issues_filtradas = [
            i for i in issues_filtradas 
            if i["fields"].get("assignee") 
            and i["fields"]["assignee"].get("displayName")
            and i["fields"]["assignee"]["displayName"] == usuario_seleccionado
        ]
    
    if estado_sel != "Todos":
        issues_filtradas = [i for i in issues_filtradas if i["fields"]["status"]["name"] == estado_sel]

    # ==== PROCESAMIENTO DE DATOS ====
    rows = []
    for issue in issues_filtradas:
        puntos = issue["fields"].get("customfield_10026", 0) or 0
        try:
            puntos = float(puntos)
        except (TypeError, ValueError):
            puntos = 0
        
        asignado = "Sin asignar"
        if issue["fields"].get("assignee") and issue["fields"]["assignee"].get("displayName"):
            asignado = issue["fields"]["assignee"]["displayName"]
        
        # Obtener fecha en que la tomó (statuscategorychangedate)
        fecha_tomo = issue["fields"].get("statuscategorychangedate", "")
        if fecha_tomo:
            fecha_tomo = fecha_tomo[:10]  # Tomar solo la fecha (YYYY-MM-DD)
        
        fila = {
            "Clave": issue["key"],
            "Resumen": issue["fields"]["summary"],
            "Estado": issue["fields"]["status"]["name"],
            "Proyecto": issue["fields"]["project"]["key"],
            "Asignado": asignado,
            "Duedate": issue["fields"].get("duedate", "Sin fecha de fin"),
            "Version": get_fix_version(issue),
            "Puntos": puntos,
            "Fecha en que la tomó": fecha_tomo,
            "Porcentaje avance": "Sin subtareas"
        }

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
            st.info("⏳ Calculando avance de subtareas... Esto puede tomar unos momentos.")
            
            # Recolectar todas las claves de subtareas
            all_subtask_keys = []
            issue_to_subtasks = {}
            
            for fila in rows_a_mostrar:
                issue = next((i for i in issues if i["key"] == fila["Clave"]), None)
                if not issue:
                    fila["Porcentaje avance"] = "Sin subtareas"
                    continue
                    
                subtasks = issue["fields"].get("subtasks", [])
                if subtasks:
                    subtask_keys = [stask.get("key") if isinstance(stask, dict) else stask for stask in subtasks]
                    # Filtrar None y strings vacíos
                    subtask_keys = [key for key in subtask_keys if key]
                    issue_to_subtasks[fila["Clave"]] = subtask_keys
                    all_subtask_keys.extend(subtask_keys)
                else:
                    fila["Porcentaje avance"] = "Sin subtareas"
            
            # Obtener estados de todas las subtareas de una vez desde la BD
            if all_subtask_keys:
                estados_subtareas = db.obtener_estados_subtareas(all_subtask_keys)
                
                # Calcular porcentaje de avance para cada historia
                for fila in rows_a_mostrar:
                    if fila["Clave"] in issue_to_subtasks:
                        subtask_keys = issue_to_subtasks[fila["Clave"]]
                        total = len(subtask_keys)
                        hechas = 0
                        
                        for st_key in subtask_keys:
                            st_status = estados_subtareas.get(st_key, "Unknown")
                            if st_status.lower() in ESTADOS_EN_PROCESO or st_status.lower() == ESTADO_LISTO_PARA_IMPLEMENTAR:
                                hechas += 1
                        
                        fila["Porcentaje avance"] = f"{round(100 * hechas / total, 1)} %"
        else:
            for fila in rows_a_mostrar:
                fila["Porcentaje avance"] = "Sin calcular"

        df = pd.DataFrame(rows_a_mostrar)
        st.dataframe(df, use_container_width=True)
        st.caption('Nota: "% de avance" se calcula por subtareas solo si tildás la opción, así la carga es mucho más rápida.')

    # ========== GANTT ==========
    st.markdown("---")
    st.subheader("Gantt: Historias EN DESARROLLO (con fechas válidas)")

    gantt_rows = [
        fila for fila in rows
        if fila["Estado"].strip().lower() == "en desarrollo" and fila["Duedate"] != "Sin fecha de fin"
    ]
    gantt_df = pd.DataFrame(gantt_rows)
    if not gantt_df.empty:
        gantt_df["Inicio"] = pd.to_datetime(gantt_df["Fecha en que la tomó"], errors="coerce")
        gantt_df["Fin"] = pd.to_datetime(gantt_df["Duedate"], errors="coerce")
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
                hover_data=["Resumen", "Puntos", "Proyecto", "Version"]
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(title='Historias EN DESARROLLO (Gantt)')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay historias en desarrollo con fecha de vencimiento para mostrar en el Gantt.")