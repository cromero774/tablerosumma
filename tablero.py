import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import os
import json
from dateutil.relativedelta import relativedelta

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

st.set_page_config(page_title="Tablero SUMMA", layout="wide")

with open("data/epicas_relevantes.json", "r", encoding="utf-8") as f:
    epicas_relevantes = json.load(f)

rns_relevantes = [epica["rn"] for epica in epicas_relevantes]

hist_path = "data/horas_historicas.csv"
actual_path = "data/horas_con_proyecto.csv"

if os.path.exists(hist_path):
    df_hist = pd.read_csv(hist_path)
    df_actual = pd.read_csv(actual_path)
    min_fecha_actual = pd.to_datetime(df_actual["Fecha"], errors="coerce").min()
    df_hist["Fecha_dt"] = pd.to_datetime(df_hist["Fecha"], errors="coerce")
    df_hist = df_hist[df_hist["Fecha_dt"] < min_fecha_actual]
    df_hist = df_hist.drop(columns="Fecha_dt")
    df = pd.concat([df_hist, df_actual], ignore_index=True)
else:
    df = pd.read_csv(actual_path)

with open("data/accountid_to_name.json", "r", encoding="utf-8") as f:
    accountid_to_name = json.load(f)

df["Usuario"] = df["Usuario"].map(accountid_to_name)

# ============= DICCIONARIOS Y FUNCIÓN PARA TEMPO (Agregar antes de las pestañas) =============

MAPEO_TEM = {
    "TEM-5": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF POSVENTA"),
    "TEM-7": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS"),
    "TEM-8": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO ATI"),
    "TEM-9": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO TALLER"),
    "TEM-30": ("CORE-TECH", "MAIPU - SUMMA - ESCRITURA RF ATI"),
    # Agregá más si aparecen
}

RESUMEN_A_PROYECTO = {
    "MAIPU - SUMMA - ESCRITURA RF POSVENTA": "AFUS",
    "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS": "REPUESTOS MAIPU",
    "MAIPU - SUMMA - DESARROLLO MODULO TALLER": "TALLER - MAIPÚ -",
    "MAIPU - SUMMA - DESARROLLO ATI": "AFUs ATI",
    "MAIPU - SUMMA - ESCRITURA RF ATI": "AFUs ATI",
    "": "TECH LAB - INTERNO"
}

def obtener_proyecto_logico(row):
    fecha = pd.to_datetime(row['Fecha'], errors='coerce')
    issue = str(row.get('Issue', ''))
    proyecto = str(row.get('Proyecto', ''))
    # Antes de junio 2025: solo sumar horas si NO es del método nuevo
    if fecha < pd.Timestamp("2025-06-01"):
        if proyecto == "TEMPO WORKLOAD":
            return None   # Ignorar estas filas nuevas antes de junio
        return proyecto
    # Desde junio 2025: mapping TEM solo si Issue es TEM-
    if issue.startswith("TEM-"):
        cuenta, resumen = MAPEO_TEM.get(issue, ("", ""))
        if cuenta == "CORE-TECH":
            if resumen == "MAIPU - SUMMA - ESCRITURA RF ATI":
                return "AFUs ATI"
            else:
                return "TECH LAB - INTERNO"
        elif cuenta == "MP-MAIPU-SUMMA":
            return RESUMEN_A_PROYECTO.get(resumen, "OTRO")
    # Desde junio 2025, para todo lo que no sea TEM-: usar Proyecto
    return proyecto

# Aplica la lógica
df["Proyecto_logico"] = df.apply(obtener_proyecto_logico, axis=1)
# Elimina filas que deben ignorarse (None)
df = df[df["Proyecto_logico"].notna()]



# Actualizar los proyectos para los filtros/postventa/ATI si querés que siempre se usen los nuevos nombres:
PROYECTOS_POSTVENTA = [
    "TALLER - MAIPÚ -",
    "REPUESTOS MAIPU",
    "AFUS",  # Usá "AFUS" en vez de "AFU´S"
    "TECH LAB - INTERNO"
]
PROYECTOS_ATI = [
    "AFUs ATI",
    "TECH LAB - INTERNO"
]


opciones_menu = ["Horas Postventas", "Horas ATI", "Desarrollo Postventas", "Entregables postventas","BUGS Postventas","Histórico postventa","Velocidad de devs","Gantt"]
opcion = st.sidebar.radio("Seleccioná opción", opciones_menu)

if opcion == "Horas Postventas":
    proyectos_mostrar = PROYECTOS_POSTVENTA
    titulo = "Horas - Postventas"
elif opcion == "Horas ATI":
    proyectos_mostrar = PROYECTOS_ATI
    titulo = "Horas - ATI"
elif opcion == "Desarrollo Postventas":
    titulo = "Desarrollo Postventas - Estados de Historias de Usuario en Sprints Activos"
elif opcion == "Entregables postventas":
    titulo = "Entregables Postventas"
elif opcion == "BUGS Postventas":
    titulo = "BUGS Postventas"
elif opcion == "Histórico postventas":
    titulo = "Histórico postventas"
elif opcion == "Velocidad de devs":
    titulo = "Velocidad de devs"
elif opcion == "Gantt":
    titulo = "Gantt"
# === PESTAÑAS HORAS ===
if opcion in ["Horas Postventas", "Horas ATI"]:
    if not df.empty:
        cols = st.columns(3)
        with cols[0]:
            years = sorted(df["Fecha"].apply(lambda x: str(x)[:4]).unique())
            year = st.selectbox("Año", options=years, index=len(years) - 1, key=f"anio_{opcion}")
        with cols[1]:
            MESES_ES = {
                "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
                "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
                "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
            }
            meses_numeros = list(MESES_ES.keys())
            meses_nombres = [MESES_ES[m] for m in meses_numeros]
            mes_num = st.selectbox("Mes", options=meses_nombres, index=datetime.now().month - 1, key=f"mes_{opcion}")
            mes_real = meses_numeros[meses_nombres.index(mes_num)]
        with cols[2]:
            usuarios_lista = ["Todos"] + sorted([u for u in df["Usuario"].dropna().unique() if u != ""])
            usuario_seleccionado = st.selectbox("Usuario", usuarios_lista, index=0, key=f"user_{opcion}")

        if opcion == "Horas Postventas":
            proyectos_mostrar = PROYECTOS_POSTVENTA
        elif opcion == "Horas ATI":
            proyectos_mostrar = PROYECTOS_ATI

        if usuario_seleccionado == "Todos":
            # ---- Vista general por mes y usuario
            df_filtrado = df[df["Fecha"].str.startswith(str(year))]
            df_filtrado = df_filtrado[df_filtrado["Fecha"].str[5:7] == mes_real]
            df_filtrado = df_filtrado[df_filtrado["Proyecto_logico"].isin(proyectos_mostrar)]

            if df_filtrado.empty:
                st.warning("No hay horas cargadas para el mes, año y usuario seleccionados.")
            else:
                tabla_pivot = pd.pivot_table(
                    df_filtrado,
                    values='Horas',
                    index='Usuario',
                    columns='Proyecto_logico',
                    aggfunc='sum',
                    fill_value=0
                )
                for col in proyectos_mostrar:
                    if col not in tabla_pivot.columns:
                        tabla_pivot[col] = 0
                tabla_pivot = tabla_pivot[proyectos_mostrar]
                tabla_pivot["Total"] = tabla_pivot.sum(axis=1)
                totales = tabla_pivot.sum(axis=0)
                totales_row = pd.DataFrame([totales], index=["Total general"])
                tabla_final = pd.concat([tabla_pivot, totales_row])

                mostrar_detalle = st.checkbox("Mostrar detalle por proyecto", value=False)
                if mostrar_detalle:
                    tabla_mostrar = tabla_final
                else:
                    tabla_mostrar = tabla_final[["Total"]]

                tabla_mostrar.index.name = "Usuario"
                df_show = tabla_mostrar.reset_index()

                st.dataframe(
                    df_show.style.format({
                        col: "{:,.2f}".format if col != "Usuario" else "{}" for col in df_show.columns
                    }),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Usuario": st.column_config.Column(width="small"),
                        "Total": st.column_config.Column(width="small", help="Total de horas"),
                    }
                )
        else:
            # ---- Vista usuario: últimos 6 meses (tabla y gráfico ORDENADO)
            fecha_ref = datetime(int(year), int(mes_real), 1)
            fecha_inicio = (fecha_ref - pd.DateOffset(months=5)).replace(day=1)
            df_user = df[(df["Usuario"] == usuario_seleccionado)].copy()
            df_user["Fecha_dt"] = pd.to_datetime(df_user["Fecha"], errors="coerce")
            df_user = df_user[
                (df_user["Fecha_dt"] >= fecha_inicio) &
                (df_user["Fecha_dt"] <= fecha_ref + pd.offsets.MonthEnd(0))
            ]
            df_user["anio_mes"] = df_user["Fecha_dt"].dt.strftime("%Y-%m")
            resumen_meses = df_user.groupby("anio_mes")["Horas"].sum().reset_index()
            meses_ultimos = pd.date_range(start=fecha_inicio, end=fecha_ref, freq="MS").strftime("%Y-%m").tolist()
            resumen_meses = resumen_meses.set_index("anio_mes").reindex(meses_ultimos, fill_value=0).reset_index()
            resumen_meses["Mes"] = resumen_meses["anio_mes"].apply(lambda x: MESES_ES[x[5:]] + " " + x[:4])

            st.subheader(f"Horas cargadas por {usuario_seleccionado} (últimos 6 meses)")
            st.dataframe(resumen_meses[["Mes", "Horas"]], hide_index=True, use_container_width=True)

            # ---- Gráfico de barras, meses SIEMPRE ordenados
            resumen_meses_plot = resumen_meses.set_index("anio_mes")["Horas"]
            st.bar_chart(resumen_meses_plot, use_container_width=True)

    else:
        st.warning("No hay datos para el período seleccionado.")
# === PESTAÑA DESARROLLO POSTVENTAS ===
if opcion == "Desarrollo Postventas":
    from jira_conexion import jira
    import pandas as pd
    import time
    from datetime import datetime, timedelta
    import re

    def traer_todas_las_issues(jira, jql, fields, max_results=100):
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
    issues_tal = traer_todas_las_issues(jira, 'project = TAL AND issuetype = Historia', fields)
    issues_rep = traer_todas_las_issues(jira, 'project = REP AND issuetype = Historia', fields)
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

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        sprint_sel = st.selectbox(
            "Filtrar por sprint (solo sprints con versión)",
            ["Todos"] + sprints_con_version,
            key="filtro_sprint"
        )
    with col2:
        version_sel = st.selectbox(
            "Filtrar por versión",
            ["Todas"] + versiones_unicas,
            key="filtro_version"
        )
    with col3:
        usuarios_asignados = sorted(list({i["fields"]["assignee"]["displayName"]
                                      for i in issues if i["fields"].get("assignee")}))
        usuarios_asignados = ["Todos"] + usuarios_asignados
        usuario_seleccionado = st.selectbox(
            "Usuario asignado",
            usuarios_asignados,
            index=0,
            key="usuario_asignado_dev"
        )

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
        calcular_avance = st.checkbox("Mostrar % de avance de subtareas (puede demorar)", value=False, key="avance_subtareas")
        if calcular_avance:
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
                        try:
                            st_info = jira._get_json(f'issue/{st_key}?fields=status')
                            st_status = st_info["fields"]["status"]["name"]
                            if st_status.lower() in ESTADOS_EN_PROCESO or st_status.lower() == ESTADO_LISTO_PARA_IMPLEMENTAR:
                                hechas += 1
                        except Exception:
                            pass
                        time.sleep(0.03)
                    fila["Porcentaje avance"] = f"{round(100 * hechas / total, 1)} %"
                else:
                    fila["Porcentaje avance"] = "Sin subtareas"
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




# === ENTREGABLES POSTVENTAS ===
if opcion == "Entregables postventas":
    from jira_conexion import jira
    import pandas as pd
    import unicodedata
    from datetime import datetime, timedelta

    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    EPIC_LINK_CAMPO = "customfield_10016"

    def traer_todos_los_issues(jira, jql, fields, max_results=100):
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

    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    meses_entrega = sorted({epica["mes_entrega"] for epica in epicas_relevantes}, key=lambda m: meses_orden.index(m))

    # ---- Filtros en columnas ----
    cols = st.columns([1, 1])
    with cols[0]:
        proyecto_seleccionado = st.selectbox("Filtrar por proyecto", ["Todos", "Taller", "Repuestos"])
    with cols[1]:
        mes_seleccionado = st.selectbox("Filtrar por mes de entrega", ["Todos"] + meses_entrega)

    fields = "key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated"

    issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
    issues_rep = traer_todos_los_issues(jira, 'project = REP AND issuetype = Historia', fields)

    if proyecto_seleccionado == "Todos":
        issues = issues_tal + issues_rep
    elif proyecto_seleccionado == "Taller":
        issues = issues_tal
    elif proyecto_seleccionado == "Repuestos":
        issues = issues_rep
    else:
        issues = []

    # Eliminar duplicados
    issues_unicos = {}
    for issue in issues:
        issues_unicos[issue['key']] = issue
    issues = list(issues_unicos.values())

    # Filtrar épicas relevantes
    if mes_seleccionado != "Todos":
        epicas_relevantes_filtradas = [e for e in epicas_relevantes if e["mes_entrega"] == mes_seleccionado]
    else:
        epicas_relevantes_filtradas = epicas_relevantes

    nombres_relevantes = [normalize(epica["nombre"]) for epica in epicas_relevantes_filtradas]
    rns_relevantes = [normalize(epica["rn"]) for epica in epicas_relevantes_filtradas]

    # Agrupación por épica
    epicas = {}
    for issue in issues:
        # Buscar epic_name
        epic_name = None
        if "parent" in issue["fields"] and issue["fields"]["parent"]:
            parent = issue["fields"]["parent"]
            if "summary" in parent and parent["summary"]:
                epic_name = parent["summary"]
            elif "fields" in parent and "summary" in parent["fields"]:
                epic_name = parent["fields"]["summary"]
        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epica_custom = issue["fields"].get(EPIC_LINK_CAMPO, None)
            if epica_custom and isinstance(epica_custom, dict) and "value" in epica_custom and epica_custom["value"]:
                epic_name = epica_custom["value"]
            elif epica_custom and isinstance(epica_custom, str) and epica_custom:
                epic_name = epica_custom
        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epic_name = "Sin epica"

        if not (normalize(epic_name) in nombres_relevantes or normalize(epic_name) in rns_relevantes):
            continue

        puntos = issue["fields"].get("customfield_10026")
        try:
            puntos = float(puntos)
        except (TypeError, ValueError):
            puntos = 0

        summary = issue["fields"]["summary"]
        if "madre" in summary.lower():
            continue

        estado = (issue["fields"]["status"]["name"] or "").strip().lower()
        asignado = issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else ""
        key = issue["key"]
        fecha_estado = issue["fields"].get("statuscategorychangedate") or issue["fields"].get("updated") or ""
        duedate = issue["fields"].get("duedate") or ""

        if epic_name not in epicas:
            epicas[epic_name] = {
                "Historias": [],
                "Mes de entrega": None
            }
        epicas[epic_name]["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos
        })

    # ---- Resumen para tabla de prioridades ----
    tabla_prioridad = []
    for epica_rn in epicas_relevantes_filtradas:
        nombre_epica = epica_rn.get("nombre", "")
        mes_entrega = epica_rn.get("mes_entrega", "")
        epic_match = next((epic for epic in epicas if normalize(nombre_epica) == normalize(epic)), None)
        if epic_match:
            data = epicas[epic_match]
            historias = data["Historias"]
            total = len(historias)
            listas_para_implementar = sum(1 for h in historias if h["Estado"] == "lista para implementar")
            pendientes = sum(
                1 for h in historias 
                if h["Estado"] == "lista para desarrollar" and not h["Asignado"]
            )
            en_proceso = sum(
                1 for h in historias 
                if h["Estado"] in [
                    "en desarrollo", "en testing", "en corrección", "por corregir",
                    "requiere validación", "en análisis", "sin refinar", "pausada"
                ] or (h["Estado"] == "lista para desarrollar" and h["Asignado"])
            )
            porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
            porcentaje_avance = f"{porcentaje_num:.1f}%"
            porcentaje_proceso_num = (en_proceso / total * 100) if total > 0 else 0
            color_proc = "🟢" if porcentaje_proceso_num == 100 else "🟡" if porcentaje_proceso_num >= 50 else "🔴"
            porcentaje_proceso = f"{porcentaje_proceso_num:.1f}% {color_proc}"
            puntos_totales = sum(h.get("Puntos", 0) or 0 for h in historias)
        else:
            historias = []
            pendientes = 0
            en_proceso = 0
            porcentaje_num = 0
            porcentaje_avance = "0%"
            porcentaje_proceso = "0.0% 🔴"
            puntos_totales = 0
        tabla_prioridad.append({
            "Épica": nombre_epica,
            "Mes entrega": mes_entrega,
            "Avance": f"{porcentaje_avance} " + ("🟢" if porcentaje_num == 100 else "🟡" if porcentaje_num >= 50 else "🔴"),
            "% En proceso": porcentaje_proceso,
            "Pendientes": pendientes,
            "Puntos totales": puntos_totales,
            "Historias": historias,
            "%_num": porcentaje_num
        })

    # Ordenar: primero por mes de entrega, luego por % avance (menor arriba)
    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except:
            return 99
    tabla_incompletas = [r for r in tabla_prioridad if r["%_num"] < 100]
    tabla_completas = [r for r in tabla_prioridad if r["%_num"] == 100]
    tabla_incompletas = sorted(tabla_incompletas, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))
    tabla_completas = sorted(tabla_completas, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    # ---- ALERTA: solo para el mes más próximo con historias pendientes y sin 100% ----
    alerta_mes = ""
    for m in meses_orden:
        mes_tiene_alerta = any((r["Mes entrega"] == m and r["Pendientes"] > 0 and r["%_num"] < 100) for r in tabla_incompletas)
        if mes_tiene_alerta:
            alerta_mes = m
            break

    # --- Mostrar tabla incompletas ---
    df_tabla = pd.DataFrame(tabla_incompletas)
    if not df_tabla.empty:
        st.markdown("## Prioridades actuales")
        def gen_alerta(row):
            if row["Mes entrega"] == alerta_mes and row["Pendientes"] > 0:
                return "⚠️ Entrega próxima con pendientes"
            else:
                return ""
        df_tabla["Alerta"] = df_tabla.apply(gen_alerta, axis=1)
        st.dataframe(
            df_tabla[["Épica", "Mes entrega", "Avance", "% En proceso", "Pendientes", "Puntos totales", "Alerta"]],
            hide_index=True,
            use_container_width=True
        )

    # --- Mostrar tabla completas abajo ---
    if tabla_completas:
        df_completas = pd.DataFrame(tabla_completas)
        # Calcular la fecha de entrega (última fecha de las historias en lista para implementar)
        fechas_entrega = []
        for fila in tabla_completas:
            fechas_hu = []
            for h in fila["Historias"]:
                if h["Estado"] == "lista para implementar":
                    fecha = h.get("Fecha_estado") or ""
                    fechas_hu.append(fecha)
            if fechas_hu:
                fecha_entrega = max(fechas_hu)
                if fecha_entrega:
                    try:
                        fecha_entrega = pd.to_datetime(fecha_entrega).strftime("%d/%m/%Y")
                    except:
                        pass
            else:
                fecha_entrega = ""
            fechas_entrega.append(fecha_entrega)
        df_completas["Fecha de entrega"] = fechas_entrega

        st.markdown("## RN entregado")
        st.dataframe(
            df_completas[["Épica", "Mes entrega", "Avance", "% En proceso", "Pendientes", "Puntos totales", "Fecha de entrega"]],
            hide_index=True,
            use_container_width=True
        )

    # ---- HISTORIAS PRIORITARIAS A TOMAR (CARDS) ----

    # ---- Agrupar historias pendientes (no tomadas) por mes de entrega ----
    pendientes_por_mes = {}
    for epica_rn in epicas_relevantes_filtradas:
        nombre_epica = epica_rn.get("nombre", "")
        mes_entrega = epica_rn.get("mes_entrega", "")
        epic_match = next((epic for epic in epicas if normalize(nombre_epica) == normalize(epic)), None)
        if not epic_match:
            continue
        historias = epicas[epic_match]["Historias"]
        pendientes = [
            h for h in historias
            if h["Estado"] == "lista para desarrollar" and not h["Asignado"]
        ]
        if pendientes:
            pendientes_por_mes.setdefault(mes_entrega, []).extend([
                {
                    **h,
                    "Epica": nombre_epica,
                    "Mes entrega": mes_entrega
                } for h in pendientes
            ])

    # ---- Determinar el mes prioritario (primero que tenga pendientes) ----
    mes_prioritario = None
    historias_prioritarias = []
    for m in meses_orden:
        if m in pendientes_por_mes:
            mes_prioritario = m
            historias_prioritarias = pendientes_por_mes[m]
            break

    # ---- Mapear devs que trabajaron en cada RN (afinidad) ----
    dev_hist_epica = {}
    for epica_rn in epicas_relevantes_filtradas:
        nombre_epica = epica_rn.get("nombre", "")
        epic_match = next((epic for epic in epicas if normalize(nombre_epica) == normalize(epic)), None)
        if not epic_match:
            continue
        historias = epicas[epic_match]["Historias"]
        for h in historias:
            if h["Asignado"]:
                dev_hist_epica.setdefault(h["Asignado"], set()).add(nombre_epica)

    # Carga de cada dev (para sugerencia por menor carga)
    dev_carga = {d: 0 for d in dev_hist_epica}
    for epica in epicas.values():
        for h in epica["Historias"]:
            if h["Asignado"]:
                dev_carga[h["Asignado"]] += 1

    st.markdown("## Historias prioritarias a tomar")
    if mes_prioritario and historias_prioritarias:
        st.markdown(f"**Mes prioritario:** <span style='color:gold; font-weight:bold;'>{mes_prioritario}</span>", unsafe_allow_html=True)
        cols_cards = st.columns(2)
        for idx, h in enumerate(historias_prioritarias):
            # Sugerir devs por afinidad y menor carga (hasta 3), mostrando fecha en que se liberan y cambiando color de fondo
            candidatos = [d for d, epics in dev_hist_epica.items() if h["Epica"] in epics]
            todos_devs = list(dev_carga.keys())
            if candidatos:
                candidatos_ordenados = sorted(candidatos, key=lambda d: dev_carga.get(d, 0))
            else:
                candidatos_ordenados = sorted(todos_devs, key=lambda d: dev_carga.get(d, 0)) if todos_devs else []
            devs_detalle = []
            fondo_card = "#20232a"
            for i, d in enumerate(candidatos_ordenados[:3]):
                # Buscar la HU en proceso con due date más próxima para ese dev
                hu_proceso = []
                for epica in epicas.values():
                    for hu_asig in epica["Historias"]:
                        if hu_asig["Asignado"] == d and hu_asig["Duedate"]:
                            try:
                                fecha_lib = pd.to_datetime(hu_asig["Duedate"])
                                hu_proceso.append((fecha_lib, hu_asig["Clave"]))
                            except:
                                pass
                if hu_proceso:
                    prox_fecha = min(hu_proceso)[0]
                    fecha_texto = prox_fecha.strftime('%d/%m/%Y')
                    dev_texto = f"{d} ({fecha_texto})"
                    if i == 0:
                        dias_restantes = (prox_fecha.date() - datetime.now().date()).days
                        if dias_restantes <= 1:
                            fondo_card = "#174e1a"  # verde
                        elif dias_restantes <= 5:
                            fondo_card = "#1a4666"  # azul oscuro
                else:
                    dev_texto = f"{d} (Disponible)"
                    if i == 0:
                        fondo_card = "#174e1a"  # verde
                devs_detalle.append(dev_texto)
            devs_sugeridos = ", ".join(devs_detalle)
            afinidad = "Sí" if candidatos else "No"
            with cols_cards[idx % 2]:
                st.markdown(
                    f"""
                    <div style="border-radius:14px; background:{fondo_card}; padding:18px; margin-bottom:16px; box-shadow:0 2px 8px #0001;">
                        <div style="font-size:1.1em; font-weight:bold; color:#fff; margin-bottom:4px;">
                            🟡 {h['Clave']} - {h['Nombre']}
                        </div>
                        <div>
                            <b>RN:</b> {h['Epica']}<br>
                            <b>Mes de entrega:</b> <span style="color:gold;">{h['Mes entrega']}</span>
                        </div>
                        <div style="margin-top:8px;">
                            <span style="font-size:1em; color:#bcbcff; font-weight:bold;">Devs sugeridos:</span> <br>
                            <span style="font-size:1em; font-weight:bold; color:#9fffca;">{devs_sugeridos}</span>
                            <br>
                            <span style="font-size:0.95em; color:#ffd580;">Afinidad: {afinidad}</span>
                        </div>
                        <div style="margin-top:6px; color:orange;">
                            <b>⚠️ Prioridad alta para cumplir con el entregable del mes</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        st.success("¡No hay historias prioritarias pendientes a tomar para este mes!")



#Bugsmaipu
if opcion == "BUGS Postventas":
    from jira_conexion import jira
    import pandas as pd
    import unicodedata
    import json
    from datetime import datetime
    import streamlit as st
    st.warning("⚠️ Pestaña en construcción. Pronto habrá más detalles.")
    def normalize(s):
        if not s:
            return ""
        s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
        return s.lower().strip()

    # Cargar el JSON con los usuarios del equipo (accountId => nombre)
    with open("data/accountid_to_name.json", "r", encoding="utf-8") as f:
        equipo_accountid_to_name = json.load(f)
    equipo_account_ids = set(equipo_accountid_to_name.keys())

    # Lista de palabras de RN (cada palabra única de cada RN, normalizada)
    rns_palabras = set()
    for rn in epicas_relevantes:
        nombre = normalize(rn.get('nombre', ''))
        for palabra in nombre.split():
            if palabra:
                rns_palabras.add(palabra)

    st.header("Bugs Postventas - Bugs reportados por Maipú")

    jql = (
        'project in (REP, TAL) AND issuetype = Error '
        'AND Sprint = "BUGS REPORTADOS POR MAIPU" '
        'ORDER BY created ASC'
    )

    max_results = 200
    endpoint = (
        f'search?jql={jql}&fields=key,summary,priority,status,project,sprint,issuetype,assignee,parent,created,customfield_10008&maxResults={max_results}'
    )
    data = jira._get_json(endpoint)
    issues = data.get("issues", [])

    rows_equipo = []
    rows_devuelto = []

    for issue in issues:
        fields = issue["fields"]
        prioridad = fields["priority"]["name"] if fields.get("priority") else "Sin Prioridad"
        fecha_creacion = fields["created"][:10]
        resumen = fields.get("summary", "")
        resumen_norm = normalize(resumen)
        epica = ""
        if fields.get("parent") and fields["parent"].get("fields", {}).get("summary"):
            epica = fields["parent"]["fields"]["summary"]
        elif fields.get("customfield_10008"):
            epica = fields.get("customfield_10008")
        else:
            epica = "Sin épica"

        responsable_id = None
        responsable = "Sin asignar"
        if fields.get("assignee") and fields["assignee"].get("accountId"):
            responsable_id = fields["assignee"]["accountId"]
            responsable = equipo_accountid_to_name.get(responsable_id, fields["assignee"].get("displayName", "Sin asignar"))

        estado = fields["status"]["name"] if fields.get("status") else ""
        mes = fecha_creacion[:7]  # YYYY-MM

        # Visual de prioridad igual a Jira
        if prioridad.lower() == "muy alta":
            icono = "🔺🔺"
        elif prioridad.lower() == "alta":
            icono = "🔺"
        elif prioridad.lower() == "media":
            icono = "🟡"
        elif prioridad.lower() == "baja":
            icono = "🔵⬇️"
        elif prioridad.lower() == "muy baja":
            icono = "🔵⬇️⬇️"
        else:
            icono = ""

        accion = "Resolver dentro del próximo mes"
        if prioridad.lower() == "muy alta":
            accion = "Resolver en menos de 24/48hs (bloqueante para el cliente)"
        dias_abierto = (datetime.now() - datetime.strptime(fecha_creacion, "%Y-%m-%d")).days
        if dias_abierto > 30 and prioridad.lower() not in ["muy alta"]:
            accion = "Revisar: abierto hace más de un mes"

        bug_row = {
            "Mes": mes,
            "Prioridad": prioridad,
            "Icono": icono,
            "Epica": epica,
            "ID": issue["key"],
            "Título": resumen,
            "Título_norm": resumen_norm,
            "Fecha de carga": fecha_creacion,
            "Responsable": responsable,
            "Estado": estado,
            "Acción sugerida": accion
        }

        # Separar bugs según si están asignados al equipo o no
        if responsable_id and responsable_id in equipo_account_ids:
            rows_equipo.append(bug_row)
        elif responsable_id:  # Asignado pero NO es del equipo
            rows_devuelto.append(bug_row)

    df_bugs = pd.DataFrame(rows_equipo)
    df_devuelto = pd.DataFrame(rows_devuelto)

    hoy = datetime.now()
    mes_actual = hoy.strftime("%Y-%m")
    bugs_total = len(df_bugs)
    bugs_mes = df_bugs[df_bugs["Mes"] == mes_actual]
    n_bugs_mes = len(bugs_mes)
    n_bugs_devueltos = len(df_devuelto)
    n_bugs_pendientes_mes = len(df_bugs[
        (df_bugs["Mes"] == mes_actual) &
        (~df_bugs["Estado"].str.lower().str.contains("cerrado|resuelto|descartado|hecha"))
    ])
    n_bugs_prioritarios = 0  # Contamos luego
    n_bugs_hecho = len(df_bugs[df_bugs["Estado"].str.lower() == "hecha"])

    # --- LÓGICA de priorización: prioritario si prioridad muy alta o si el título contiene alguna palabra de RN ---
    def es_prioritario(row):
        if row["Prioridad"].lower() == "muy alta":
            return True
        for palabra in rns_palabras:
            if palabra and palabra in row["Título_norm"]:
                return True
        return False

    if not df_bugs.empty:
        df_bugs["Prioritario"] = df_bugs.apply(es_prioritario, axis=1)
        n_bugs_prioritarios = df_bugs["Prioritario"].sum()
    else:
        df_bugs["Prioritario"] = False

    # --- CARDS GRANDES de contadores ---
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("🟦 Bugs activos", bugs_total)
    col2.metric("🗓️ Mes actual", n_bugs_mes)
    col3.metric("🦾 Devueltos a Maipú", n_bugs_devueltos)
    col4.metric("🕑 Pend. mes", n_bugs_pendientes_mes)
    col5.metric("🔴 Prioritarios", int(n_bugs_prioritarios))
    col6.metric("✅ En Hecha", n_bugs_hecho)

    # --- TABLA DE PRIORITARIOS ---
    df_prioritarios = df_bugs[df_bugs["Prioritario"]]
    if not df_prioritarios.empty:
        st.subheader("🔴 Bugs prioritarios (bloqueantes o de entregable)")
        st.dataframe(
            df_prioritarios[["Icono", "Prioridad", "ID", "Título", "Epica", "Fecha de carga", "Responsable", "Estado", "Acción sugerida"]],
            hide_index=True, use_container_width=True
        )

    # --- TABLA DEL RESTO DE LOS BUGS agrupados SOLO por mes de carga ---
    df_no_prio = df_bugs[~df_bugs["Prioritario"]]
    if not df_no_prio.empty:
        for mes, grupo in df_no_prio.groupby("Mes"):
            st.markdown(f"### Bugs reportados en {mes}")
            st.dataframe(
                grupo[["Icono", "Prioridad", "ID", "Título", "Epica", "Fecha de carga", "Responsable", "Estado", "Acción sugerida"]],
                hide_index=True, use_container_width=True
            )

    # --- TABLA DE BUGS DEVUELTOS A MAIPÚ ---
    if not df_devuelto.empty:
        st.subheader("🟦 Bugs devueltos a Maipú (asignados fuera del equipo)")
        st.dataframe(
            df_devuelto[["Icono", "Prioridad", "ID", "Título", "Epica", "Fecha de carga", "Responsable", "Estado", "Acción sugerida"]],
            hide_index=True, use_container_width=True
        )



#Historico postventas
if opcion == "Histórico postventa":
    from jira_conexion import jira
    import unicodedata
    import pandas as pd

    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    def traer_todos_los_issues(jira, jql, fields, max_results=100):
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

    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    fields = "key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated"
    issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
    issues_rep = traer_todos_los_issues(jira, 'project = REP AND issuetype = Historia', fields)
    issues = issues_tal + issues_rep

    issues_unicos = {}
    for issue in issues:
        issues_unicos[issue['key']] = issue
    issues = list(issues_unicos.values())

    EPIC_LINK_CAMPO = "customfield_10016"
    epicas = {}
    for issue in issues:
        epic_name = None
        if "parent" in issue["fields"] and issue["fields"]["parent"]:
            parent = issue["fields"]["parent"]
            if "summary" in parent and parent["summary"]:
                epic_name = parent["summary"]
            elif "fields" in parent and "summary" in parent["fields"]:
                epic_name = parent["fields"]["summary"]
        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epica_custom = issue["fields"].get(EPIC_LINK_CAMPO, None)
            if epica_custom and isinstance(epica_custom, dict) and epica_custom.get("value"):
                epic_name = epica_custom["value"]
            elif epica_custom and isinstance(epica_custom, str):
                epic_name = epica_custom
        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epic_name = "Sin epica"

        summary = issue["fields"]["summary"]
        if "madre" in summary.lower():
            continue

        estado = (issue["fields"]["status"]["name"] or "").strip().lower()
        asignado = issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else ""
        puntos = issue["fields"].get("customfield_10026", 0)
        try:
            puntos = float(puntos)
        except Exception:
            puntos = 0
        key = issue["key"]
        fecha_estado = issue["fields"].get("statuscategorychangedate") or issue["fields"].get("updated") or ""
        duedate = issue["fields"].get("duedate") or ""

        if epic_name not in epicas:
            epicas[epic_name] = {
                "Historias": [],
                "Mes de entrega": None
            }
        epicas[epic_name]["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos
        })

    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except:
            return 99

    tabla_historico = []
    for epica_rn in epicas_relevantes:
        nombre_epica = epica_rn.get("nombre", "")
        mes_entrega = epica_rn.get("mes_entrega", "")
        epic_match = next((epic for epic in epicas if normalize(nombre_epica) == normalize(epic)), None)
        if epic_match:
            data = epicas[epic_match]
            historias = data["Historias"]
            total = len(historias)
            listas_para_implementar = sum(1 for h in historias if h["Estado"] == "lista para implementar")
            porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
            puntos_totales = sum(h.get("Puntos", 0) or 0 for h in historias)
        else:
            historias = []
            porcentaje_num = 0
            puntos_totales = 0
        tabla_historico.append({
            "Épica": nombre_epica,
            "Mes entrega": mes_entrega,
            "%_num": porcentaje_num,
            "Historias": historias,
            "Puntos totales": puntos_totales
        })

    tabla_historico = sorted(tabla_historico, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    st.markdown("## Histórico de RNs postventa")
    for row in tabla_historico:
        nombre = row["Épica"]
        mes = row["Mes entrega"]
        porcentaje = row["%_num"]
        puntos_totales = row["Puntos totales"]
        historias = row["Historias"]
        completado = porcentaje == 100

        expander_title = f"{nombre} | Porcentaje de avance: {porcentaje:.1f}% | {mes} | Puntos totales: {puntos_totales}"
        with st.expander(expander_title, expanded=False):
            if historias:
                for h in historias:
                    color_estado = "#39d353" if h["Estado"]=="lista para implementar" else "#fa4" if h["Estado"]=="en desarrollo" else "#bbb"
                    st.markdown(
                        f"- **{h['Clave']}** — {h['Nombre']} | <span style='color:{color_estado}'>{h['Estado'].capitalize()}</span> | {h['Asignado'] if h['Asignado'] else '<i>Sin asignar</i>'} | <b>Puntos:</b> {h['Puntos']}",
                        unsafe_allow_html=True
                    )
            else:
                st.markdown("*Sin historias cargadas*", unsafe_allow_html=True)
#velocidad devs

# Pestaña Velocidad de devs

if opcion == "Velocidad de devs":
    import pandas as pd
    import streamlit as st
    import json
    from jira_conexion import jira

    st.header("Velocidad de devs")
    st.warning("⚠️ Esta pestaña está en construcción. Los datos y cálculos pueden no ser definitivos.")
    # Mapping usuarios
    with open("data/accountid_to_name.json", "r", encoding="utf-8") as f:
        accountid_to_name = json.load(f)

    # Cargar horas históricas
    df_horas = pd.read_csv("data/horas_historicas.csv")
    df_horas["Usuario_nombre"] = df_horas["Usuario"].map(accountid_to_name).fillna(df_horas["Usuario"])

    # Traer historias de Jira (TAL, REP, ATI)
    fields = "key,summary,status,project,issuetype,assignee,customfield_10026,statuscategorychangedate"
    def traer_todas_las_issues(jira, jql, fields, max_results=100):
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

    issues_tal = traer_todas_las_issues(jira, 'project = TAL AND issuetype = Historia', fields)
    issues_rep = traer_todas_las_issues(jira, 'project = REP AND issuetype = Historia', fields)
    issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia', fields)
    issues = issues_tal + issues_rep + issues_ati

    # Dataframe de historias
    rows_issues = []
    for issue in issues:
        key = issue["key"]
        puntos = issue["fields"].get("customfield_10026", 0)
        try:
            puntos = float(puntos)
        except Exception:
            puntos = 0
        estado = (issue["fields"]["status"]["name"] or "").strip().lower()
        asignado = issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else ""
        fecha_estado = issue["fields"].get("statuscategorychangedate", "")
        proyecto = issue["fields"]["project"]["key"] if issue["fields"].get("project") else ""
        rows_issues.append({
            "Issue": key,
            "Puntos": puntos,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Proyecto": proyecto
        })
    df_issues = pd.DataFrame(rows_issues)
    df_issues["Fecha_estado"] = pd.to_datetime(df_issues["Fecha_estado"], errors="coerce").dt.tz_localize(None)

    # Filtrar historias "quemadas" y asignadas desde marzo 2025
    estados_quemados = ["lista para implementar", "en testing"]
    fecha_limite = pd.to_datetime("2025-03-01")
    df_issues = df_issues[
        (df_issues["Puntos"] > 0)
        & (df_issues["Estado"].isin(estados_quemados))
        & (df_issues["Fecha_estado"] >= fecha_limite)
    ].copy()

    # Traer bugs asociados (tipo "Error" en Jira)
    bug_fields = "key,issuetype,project,parent,assignee"
    bugs_tal = traer_todas_las_issues(jira, 'project = TAL AND issuetype = Error', bug_fields)
    bugs_rep = traer_todas_las_issues(jira, 'project = REP AND issuetype = Error', bug_fields)
    bugs_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Error', bug_fields)
    bugs = bugs_tal + bugs_rep + bugs_ati
    bug_map = {}
    for bug in bugs:
        parent = bug["fields"].get("parent", {})
        parent_key = parent.get("key")
        if parent_key:
            bug_map.setdefault(parent_key, 0)
            bug_map[parent_key] += 1

    # Unir historias con horas cargadas
    df_velocidad = pd.merge(df_horas, df_issues, on="Issue", how="inner")
    df_velocidad = df_velocidad[
        (df_velocidad["Horas"] > 0) &
        (df_velocidad["Usuario_nombre"] == df_velocidad["Asignado"])
    ].copy()

    # Quitar usuarios no mapeados (que quedan como IDs)
    usuarios_validos = sorted([u for u in df_velocidad["Usuario_nombre"].dropna().unique() if " " in u or "." in u])
    usuario_sel = st.selectbox("Seleccioná usuario", ["Todos"] + usuarios_validos)

    # ========== FILTRO POR USUARIO ==========
    if usuario_sel != "Todos":
        df_user = df_velocidad[df_velocidad["Usuario_nombre"] == usuario_sel].copy()
        if not df_user.empty:
            # Armamos la tabla histórica de historias (por historia, por usuario)
            df_user["Mes_dt"] = pd.to_datetime(df_user["Fecha"], errors="coerce")
            df_user["Mes"] = df_user["Mes_dt"].dt.strftime("%B %Y")
            tabla_hist = (
                df_user.groupby(["Mes", "Mes_dt", "Issue", "Puntos", "Estado"], as_index=False)
                .agg({"Horas": "sum"})
                .sort_values(["Mes_dt", "Issue"])
            )
            tabla_hist["Velocidad"] = (tabla_hist["Horas"] / tabla_hist["Puntos"]).apply(lambda x: int(-(-x // 1)) if pd.notnull(x) else 0)
            tabla_hist["Bugs"] = tabla_hist["Issue"].map(lambda k: bug_map.get(k, 0))
            tabla_hist = tabla_hist.rename(columns={
                "Mes": "Mes",
                "Issue": "Clave",
                "Puntos": "Puntos",
                "Horas": "Horas",
                "Velocidad": "Velocidad",
                "Estado": "Estado",
                "Bugs": "Bugs"
            })

            # ---- PROMEDIOS SOLO SOBRE TABLA HISTÓRICA ----
            resumen = pd.DataFrame([{
                "Usuario_nombre": usuario_sel,
                "Promedio_puntos": tabla_hist["Puntos"].mean(),
                "Promedio_horas": tabla_hist["Horas"].mean(),
                "Historias_quemadas": tabla_hist.shape[0],
                "Velocidad": int(-(-tabla_hist["Horas"].mean() // tabla_hist["Puntos"].mean())) if tabla_hist["Puntos"].mean() > 0 else 0,
                "Bugs": tabla_hist["Bugs"].sum()
            }])

            st.subheader("Velocidad promedio por dev")
            st.dataframe(resumen, hide_index=True)

            # ---- TABLA HISTÓRICA POR HISTORIA ----
            st.markdown("### Velocidad por historia")
            st.dataframe(tabla_hist[["Mes", "Clave", "Puntos", "Horas", "Velocidad", "Bugs", "Estado"]], hide_index=True, use_container_width=True)

            # ---- GRÁFICO DE VELOCIDAD MENSUAL ORDENADO POR FECHA ----
            vel_mensual = tabla_hist.groupby(["Mes", "Mes_dt"])["Velocidad"].mean().reset_index()
            vel_mensual = vel_mensual.sort_values("Mes_dt")
            st.markdown("#### Velocidad promedio mensual")
            st.line_chart(vel_mensual.set_index("Mes")["Velocidad"])

        else:
            st.warning("No hay datos con las condiciones seleccionadas.")

    else:
        # Si selecciona TODOS, mostramos promedios de todos (como antes, pero ordenados)
        resumen = (
            df_velocidad.groupby("Usuario_nombre")
            .agg(
                Promedio_puntos=("Puntos", "mean"),
                Promedio_horas=("Horas", "mean"),
                Historias_quemadas=("Issue", "count"),
                Bugs=("Issue", lambda x: sum([bug_map.get(k, 0) for k in x])),
            )
            .reset_index()
        )
        resumen["Velocidad"] = (resumen["Promedio_horas"] / resumen["Promedio_puntos"]).apply(lambda x: int(-(-x // 1)) if pd.notnull(x) else 0)
        resumen = resumen.sort_values("Velocidad")
        resumen = resumen[["Usuario_nombre", "Promedio_puntos", "Promedio_horas", "Historias_quemadas", "Velocidad", "Bugs"]]
        st.subheader("Velocidad promedio por dev")
        st.dataframe(resumen, hide_index=True)

#ganttentregables

if opcion == "Gantt":
    import pandas as pd
    import plotly.express as px
    from datetime import datetime

    # --- URLs de los CSV ---
    link_postventas = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTRvUazuzfWjGl5VWuZJUJslZEf-PpYyHZ_5G2SXwPtu16R71mPSKVQTYjen9UBwQ/pub?gid=865145678&single=true&output=csv"
    link_ati = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6s9qMzmA_sJRko5EDggumO4sybGVq3n-uOmZOMj8CJDnHo9AWZeZOXZGz7cTg4XoqeiPDIgQP3QER/pub?output=csv"
    link_afupost = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR3rrcWGJWtEbowD_8bJ35lbziZ208DFGdo1JkHKhMvRK9SBjxxlTolXjeoKVMu4v447yfgQn0tUjsT/pub?output=csv"
    link_afuati = "https://docs.google.com/spreadsheets/d/e/2PACX-1vThHnFUDJm9AlT-rODLiPhLSTqH1O12_yz0Z_0SJJ3EAtS84GH6lptWpr2eSMPuyv50ShS3ysozwsKe/pub?output=csv"

    # --- Paleta de colores por estado ---
    color_estado = {
        'Entregado': '#2ecc71',
        'En desarrollo': '#1abc9c',
        'Backlog': '#f1c40f',
        'Para refinar': '#f5d76e',
        'Escribiendo': '#e67e22',
        'Para escribir': '#e74c3c',
        'En análisis': '#9b59b6',
        'Cancelado': '#95a5a6',
        'Error': '#e74c3c'
    }

    def cargar_datos_gantt(link, tipo="postventas"):
        df = pd.read_csv(link)
        df.columns = df.columns.str.strip().str.lower()
        df['rn'] = df['rn'].astype(str).str.strip()
        # Fechas
        for col in ['inicio', 'fin']:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['inicio', 'fin'])
        # Mes de entrega
        if 'mes' in df.columns:
            df['mes de entrega'] = df['mes']
        else:
            df['mes de entrega'] = df['fin'].dt.to_period('M').astype(str)
        # Truncar RN para mejor visual
        df['rn_trunc'] = df['rn'].apply(lambda x: x if len(x) <= 30 else x[:27] + '...')
        # Por si no está la columna 'afu asignado'
        if 'afu asignado' not in df.columns:
            df['afu asignado'] = 'Sin asignar'
        return df

    st.markdown("## Gantt - SUMMA")
    gantt_proyecto = st.radio(
        "Seleccioná el Gantt que querés ver:",
        ("Desarrollo Postventas", "Desarrollo ATI", "AFUs Postventas", "AFUs ATI"),
        horizontal=True,
        key="gantt_proyecto"
    )

    if gantt_proyecto == "Desarrollo Postventas":
        df_gantt = cargar_datos_gantt(link_postventas, tipo="postventas")
        filtros = ['mes de entrega', 'estado']
    elif gantt_proyecto == "Desarrollo ATI":
        df_gantt = cargar_datos_gantt(link_ati, tipo="ati")
        filtros = ['mes de entrega', 'estado']
    elif gantt_proyecto == "AFUs Postventas":
        df_gantt = cargar_datos_gantt(link_afupost, tipo="afupost")
        filtros = ['mes de entrega', 'estado', 'afu asignado']
    elif gantt_proyecto == "AFUs ATI":
        df_gantt = cargar_datos_gantt(link_afuati, tipo="afuati")
        filtros = ['mes de entrega', 'estado', 'afu asignado']

    # --- Filtros dinámicos según el gantt seleccionado ---
    cols = st.columns(len(filtros))
    filtros_seleccionados = {}
    for i, filtro in enumerate(filtros):
        opciones = ['Todos'] + sorted(df_gantt[filtro].dropna().unique())
        valor = cols[i].selectbox(filtro.replace("_", " ").title(), opciones, key=f"{gantt_proyecto}_{filtro}")
        filtros_seleccionados[filtro] = valor

    # --- Aplicar filtros ---
    df_filtrado = df_gantt.copy()
    for filtro, valor in filtros_seleccionados.items():
        if valor != 'Todos':
            df_filtrado = df_filtrado[df_filtrado[filtro] == valor]

    # --- Orden visual igual que en el dash ---
    df_filtrado = df_filtrado.sort_values('inicio', ascending=True)
    df_filtrado['rn_trunc'] = pd.Categorical(df_filtrado['rn_trunc'], categories=df_filtrado['rn_trunc'].unique(), ordered=True)

    # --- Gantt ---
    if not df_filtrado.empty:
        fig = px.timeline(
            df_filtrado,
            x_start="inicio",
            x_end="fin",
            y="rn_trunc",
            color="estado",
            color_discrete_map=color_estado,
            hover_data=[c for c in df_filtrado.columns if c not in ["inicio", "fin", "rn_trunc"]],
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            height=600,
            xaxis_title="Fecha",
            legend_title="Estado",
            margin=dict(l=200, r=50, t=60, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos para los filtros seleccionados.")










































































































