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

MESES_ES = {
    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
    "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
    "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
}

PROYECTOS_POSTVENTA = [
    "TALLER - MAIPÚ -",
    "REPUESTOS MAIPU",
    "AFU´S",
    "TECH LAB - INTERNO"
]
PROYECTOS_ATI = [
    "AJUSTES TIMM - INTEGRACIONES",
    "AFUs ATI",
    "TECH LAB - INTERNO"
]

opciones_menu = ["Horas Postventas", "Horas ATI", "Desarrollo Postventas", "Entregables postventas","BUGS Postventas","Histórico postventa"]
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

# === PESTAÑAS HORAS ===
if opcion in ["Horas Postventas", "Horas ATI"]:
    if not df.empty:
        cols = st.columns(3)
        with cols[0]:
            years = sorted(df["Fecha"].apply(lambda x: str(x)[:4]).unique())
            year = st.selectbox("Año", options=years, index=len(years) - 1, key=f"anio_{opcion}")
        with cols[1]:
            meses_numeros = list(MESES_ES.keys())
            meses_nombres = [MESES_ES[m] for m in meses_numeros]
            mes_num = st.selectbox("Mes", options=meses_nombres, index=datetime.now().month - 1, key=f"mes_{opcion}")
            mes_real = meses_numeros[meses_nombres.index(mes_num)]
        with cols[2]:
            usuarios_lista = ["Todos"] + sorted([u for u in df["Usuario"].dropna().unique() if u != ""])
            usuario_seleccionado = st.selectbox("Usuario", usuarios_lista, index=0, key=f"user_{opcion}")

        if usuario_seleccionado == "Todos":
            df_filtrado = df[df["Fecha"].str.startswith(str(year))]
            df_filtrado = df_filtrado[df_filtrado["Fecha"].str[5:7] == mes_real]

            usuario_proyectos = df_filtrado.groupby("Usuario")["Proyecto"].apply(set)
            usuarios_equipo = []
            usuarios_techlab_puros = []

            for usuario, proyectos in usuario_proyectos.items():
                if opcion == "Horas ATI":
                    # Excluir si tiene horas en TALLER o REPUESTOS, salvo que sea solo TECH LAB INTERNO
                    proyectos_sin_techlab = {p for p in proyectos if p != "TECH LAB - INTERNO"}
                    if not any(p in PROYECTOS_POSTVENTA for p in proyectos_sin_techlab):
                        if proyectos == {"TECH LAB - INTERNO"}:
                            usuarios_techlab_puros.append(usuario)
                        else:
                            usuarios_equipo.append(usuario)

                elif opcion == "Horas Postventas":
                    if proyectos.issubset(set(PROYECTOS_POSTVENTA)):
                        if proyectos == {"TECH LAB - INTERNO"}:
                            usuarios_techlab_puros.append(usuario)
                        else:
                            usuarios_equipo.append(usuario)

            df_equipo = df_filtrado[
                (df_filtrado["Usuario"].isin(usuarios_equipo)) &
                (df_filtrado["Proyecto"].isin(proyectos_mostrar))
            ]

            if df_equipo.empty:
                st.warning("No hay horas cargadas para el mes, año y usuario seleccionados.")
            else:
                tabla_pivot = pd.pivot_table(
                    df_equipo,
                    values='Horas',
                    index='Usuario',
                    columns='Proyecto',
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

                if usuarios_techlab_puros:
                    st.markdown("### Usuarios que SOLO cargan horas en Tech Lab Interno")
                    df_solo_techlab = df_filtrado[
                        (df_filtrado["Usuario"].isin(usuarios_techlab_puros)) &
                        (df_filtrado["Proyecto"] == "TECH LAB - INTERNO")
                    ]
                    tabla_solo = df_solo_techlab.groupby("Usuario")["Horas"].sum().reset_index()
                    tabla_solo = tabla_solo.rename(columns={"Horas": "Horas Tech Lab Interno"})
                    st.dataframe(
                        tabla_solo.style.format({"Horas Tech Lab Interno": "{:,.2f}".format}),
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Usuario": st.column_config.Column(width="small"),
                        }
                    )
        else:
            st.markdown(f"## Horas mensuales de {usuario_seleccionado} (todos los proyectos)")

            df_user = df[df["Usuario"] == usuario_seleccionado].copy()
            if df_user.empty:
                st.info("No hay datos de horas para este usuario.")
            else:
                df_user["Fecha"] = pd.to_datetime(df_user["Fecha"], errors='coerce')
                df_user = df_user.dropna(subset=["Fecha"])
                df_user["Año-Mes"] = df_user["Fecha"].dt.to_period("M")
                max_period = df_user["Año-Mes"].max()
                max_date = max_period.to_timestamp()
                ultimos_6 = [(max_date - relativedelta(months=i)).to_period('M') for i in reversed(range(6))]
                ultimos_6_labels = [f"{MESES_ES[p.strftime('%m')]} {p.strftime('%Y')}" for p in ultimos_6]
                resumen_6m = (
                    df_user.groupby("Año-Mes")["Horas"]
                    .sum()
                    .reindex(ultimos_6, fill_value=0)
                    .reset_index()
                )
                resumen_6m["Mes"] = ultimos_6_labels
                resumen_6m["Horas"] = resumen_6m["Horas"].round(2)
                resumen_6m = resumen_6m[["Mes", "Horas"]]
                resumen_6m = resumen_6m[resumen_6m["Horas"] > 0]

                MESES_NUM = {
                    "Enero": "01", "Febrero": "02", "Marzo": "03", "Abril": "04",
                    "Mayo": "05", "Junio": "06", "Julio": "07", "Agosto": "08",
                    "Septiembre": "09", "Octubre": "10", "Noviembre": "11", "Diciembre": "12"
                }
                resumen_6m["Mes_dt"] = pd.to_datetime(
                    resumen_6m["Mes"].str.extract(r'(\w+)\s(\d{4})').apply(
                        lambda x: f"{x[1]}-{MESES_NUM[x[0]]}-01", axis=1
                    )
                )
                resumen_6m = resumen_6m.sort_values("Mes_dt")
                resumen_6m = resumen_6m.reset_index(drop=True)

                st.dataframe(
                    resumen_6m[["Mes", "Horas"]].style.format({"Horas": "{:,.2f}".format}),
                    use_container_width=True,
                    hide_index=True,
                )

                total_6m = resumen_6m["Horas"].sum()
                st.markdown(f"**Total de horas en los últimos 6 meses: {total_6m:.2f}**")

                st.markdown("### Gráfico de horas cargadas por mes")
                orden_meses = list(resumen_6m["Mes"])
                resumen_6m["Mes"] = pd.Categorical(resumen_6m["Mes"], categories=orden_meses, ordered=True)

                fig = px.bar(
                    resumen_6m,
                    x="Mes",
                    y="Horas",
                    category_orders={"Mes": orden_meses},
                    labels={"Mes": "Mes", "Horas": "Horas cargadas"},
                    text_auto=True,
                )
                fig.update_layout(xaxis_title=None, yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos para el período seleccionado.")

# === PESTAÑA DESARROLLO POSTVENTAS ===
if opcion == "Desarrollo Postventas":
    from jira_conexion import jira
    import pandas as pd
    import time
    from datetime import datetime

    ESTADOS_HECHOS = [
        "hecha", "hecho", "finalizado", "closed", "done",
        "en testing", "listo", "implementado", "cerrado"
    ]

    jql = 'project in (TAL, REP) AND Sprint in openSprints() AND issuetype = Historia'
    max_results = 200

    endpoint = f'search?jql={jql}&fields=key,summary,status,project,sprint,issuetype,assignee,parent,statuscategorychangedate,duedate,subtasks,customfield_10016,customfield_10026&expand=changelog&maxResults={max_results}'
    data = jira._get_json(endpoint)
    issues = data.get("issues", [])

    # ----------- FILTRO POR USUARIO ASIGNADO -----------
    usuarios_asignados = sorted(list({i["fields"]["assignee"]["displayName"]
                                      for i in issues if i["fields"].get("assignee")}))
    usuarios_seleccionados = st.multiselect(
        "Filtrar por usuario asignado (podés elegir uno o más)", 
        usuarios_asignados,
        default=usuarios_asignados,
        key="filtra_user_dev"
    )

    st.subheader("Cantidad de historias de usuario por estado (sprints activos)")

    rows = []
    rows_en_desarrollo = []
    for issue in issues:
        estado = issue["fields"]["status"]["name"]
        # Epica: buscamos por todos los métodos posibles
        epic_name = None
        # 1. Parent > summary
        if "parent" in issue["fields"] and issue["fields"]["parent"]:
            parent = issue["fields"]["parent"]
            # Puede venir como dict plano o anidado en fields
            if "summary" in parent:
                epic_name = parent["summary"]
            elif "fields" in parent and "summary" in parent["fields"]:
                epic_name = parent["fields"]["summary"]
        # 2. Campo custom (a veces viene solo el key)
        if not epic_name or epic_name == "Sin épica":
            epica_custom = issue["fields"].get("customfield_10016", None)
            if epica_custom and isinstance(epica_custom, dict) and "value" in epica_custom:
                epic_name = epica_custom["value"]
            elif epica_custom:
                epic_name = str(epica_custom)
        # 3. Fallback
        if not epic_name:
            epic_name = "Sin épica"

        puntos = issue["fields"].get("customfield_10026", "")
        if puntos is None:
            puntos = ""

        fila = {
            "Clave": issue["key"],
            "Resumen": issue["fields"]["summary"],
            "Estado": estado,
            "Proyecto": issue["fields"]["project"]["name"],
            "Epica": epic_name,
            "Asignado": None,
            "Fecha en que la tomó": None,
            "Fecha finalización": "Sin fecha de fin",
            "Porcentaje avance": "Sin calcular",
            "Puntos": puntos
        }

        if issue["fields"].get("assignee"):
            fila["Asignado"] = issue["fields"]["assignee"]["displayName"]

        if "statuscategorychangedate" in issue["fields"] and issue["fields"]["statuscategorychangedate"]:
            fila["Fecha en que la tomó"] = issue["fields"]["statuscategorychangedate"][:10]

        if "duedate" in issue["fields"] and issue["fields"]["duedate"]:
            fila["Fecha finalización"] = issue["fields"]["duedate"]

        rows.append(fila)
        if estado.lower() == "en desarrollo":
            rows_en_desarrollo.append(fila)

    # -------- Métricas por estado (según filtro) --------
    if usuarios_seleccionados:
        rows_filtrados = [r for r in rows if r["Asignado"] in usuarios_seleccionados]
        rows_en_desarrollo_filtrados = [r for r in rows_en_desarrollo if r["Asignado"] in usuarios_seleccionados]
    else:
        rows_filtrados = rows
        rows_en_desarrollo_filtrados = rows_en_desarrollo

    estados = {}
    for fila in rows_filtrados:
        estado = fila["Estado"]
        estados[estado] = estados.get(estado, 0) + 1
    estado_names = sorted(estados.keys())
    cols = st.columns(len(estado_names))
    for col, estado in zip(cols, estado_names):
        col.metric(label=estado, value=estados[estado])

    # ==========================
    # ALERTAS VISUALES AGREGADAS
    # ==========================

    # Alertas solo para historias EN DESARROLLO
    alerta_liberacion = []
    alerta_vencimiento = []
    hoy = datetime.now().date()

    for fila in rows_en_desarrollo_filtrados:
        fecha_vto_str = fila["Fecha finalización"]
        asignado = fila.get("Asignado", "")
        clave = fila.get("Clave", "")
        resumen = fila.get("Resumen", "")
        estado = fila.get("Estado", "")

        # Solo consideramos si tiene fecha válida
        if fecha_vto_str and fecha_vto_str != "Sin fecha de fin":
            try:
                fecha_vto = datetime.strptime(fecha_vto_str[:10], "%Y-%m-%d").date()
                dias_restantes = (fecha_vto - hoy).days
            except Exception:
                continue

            # Alerta 1: usuario se libera en 2 días
            if asignado and dias_restantes == 2:
                alerta_liberacion.append({
                    "Usuario": asignado,
                    "Clave": clave,
                    "Resumen": resumen,
                    "Fecha vencimiento": fecha_vto_str
                })
            # Alerta 2: historia vencida o por vencer
            if dias_restantes < 0:
                alerta_vencimiento.append({
                    "Alerta": "Vencida",
                    "Clave": clave,
                    "Resumen": resumen,
                    "Asignado": asignado,
                    "Fecha vencimiento": fecha_vto_str,
                    "Estado": estado
                })
            elif dias_restantes in [0, 1]:
                alerta_vencimiento.append({
                    "Alerta": "Por vencer",
                    "Clave": clave,
                    "Resumen": resumen,
                    "Asignado": asignado,
                    "Fecha vencimiento": fecha_vto_str,
                    "Estado": estado
                })

    # Mostramos las alertas (si hay)
    if alerta_liberacion:
        st.warning("🔔 *Usuarios que se liberan de tarea en 2 días*")
        st.dataframe(
            pd.DataFrame(alerta_liberacion)[["Usuario", "Clave", "Resumen", "Fecha vencimiento"]],
            use_container_width=True,
            hide_index=True
        )

    if alerta_vencimiento:
        st.markdown(
            "<div style='padding: 10px; background-color: #b30000; color: #fff; font-weight: bold; border-radius: 5px; margin-bottom: 8px;'>⚠️ Historias vencidas o por vencer</div>",
            unsafe_allow_html=True
        )
        df_alertas = pd.DataFrame(alerta_vencimiento)[["Alerta", "Clave", "Resumen", "Asignado", "Fecha vencimiento", "Estado"]]

        def color_alerta(row):
            if row["Alerta"] == "Vencida":
                return ['background-color: #b30000; color: #fff; font-weight:bold']*len(row)
            elif row["Alerta"] == "Por vencer":
                return ['background-color: #ffd500; color: #000; font-weight:bold']*len(row)
            else:
                return ['']*len(row)

        st.dataframe(
            df_alertas.style.apply(color_alerta, axis=1),
            use_container_width=True,
            hide_index=True
        )

    # ==========================
    # FIN ALERTAS VISUALES
    # ==========================

    # Checkbox para mostrar el detalle de todas las historias en el sprint
    mostrar_todas = st.checkbox("Mostrar detalle de historias de usuario (todas las del sprint)", value=False)

    if mostrar_todas:
        df_todas = pd.DataFrame(rows_filtrados)
        st.dataframe(
            df_todas[["Clave", "Resumen", "Epica", "Puntos", "Asignado", "Fecha en que la tomó", "Fecha finalización", "Estado"]],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.markdown("### Historias de usuario EN DESARROLLO")

    if not rows_en_desarrollo_filtrados:
        st.info("No hay historias de usuario en estado En Desarrollo.")
    else:
        calcular_avance = st.checkbox("Mostrar % de avance de subtareas (puede demorar)", value=False)
        if calcular_avance:
            for fila in rows_en_desarrollo_filtrados:
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
                            if st_status.lower() in ESTADOS_HECHOS:
                                hechas += 1
                        except Exception:
                            pass
                        time.sleep(0.03)
                    fila["Porcentaje avance"] = f"{round(100 * hechas / total, 1)} %"
                else:
                    fila["Porcentaje avance"] = "Sin subtareas"
        else:
            for fila in rows_en_desarrollo_filtrados:
                fila["Porcentaje avance"] = "Sin calcular"

        df_desarrollo = pd.DataFrame(rows_en_desarrollo_filtrados)
        st.dataframe(
            df_desarrollo[["Clave", "Resumen", "Epica", "Puntos", "Asignado", "Fecha en que la tomó", "Fecha finalización", "Porcentaje avance"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption('Nota: "% de avance" se calcula por subtareas solo si tildás la opción, así la carga es mucho más rápida.')

    # === GANTT para historias con fecha de vencimiento ===
    st.markdown("---")
    st.subheader("Gantt: Historias con fecha de vencimiento (solo las que tienen fecha definida)")
    gantt_rows = [
        fila for fila in rows_filtrados
        if fila["Fecha finalización"] != "Sin fecha de fin"
        and (fila["Estado"].lower() == "en desarrollo")
    ]
    gantt_df = pd.DataFrame(gantt_rows)
    if not gantt_df.empty:
        # Convertir fechas a datetime
        gantt_df["Inicio"] = pd.to_datetime(gantt_df["Fecha en que la tomó"], errors="coerce")
        gantt_df["Fin"] = pd.to_datetime(gantt_df["Fecha finalización"], errors="coerce")
        # Filtrar solo las filas válidas
        gantt_df = gantt_df[gantt_df["Inicio"].notnull() & gantt_df["Fin"].notnull()]
        if gantt_df.empty:
            st.info("No hay historias con fechas válidas para mostrar en el Gantt.")
        else:
            fig = px.timeline(
                gantt_df,
                x_start="Inicio",
                x_end="Fin",
                y="Clave",
                color="Asignado",
                hover_data=["Resumen", "Puntos", "Estado"]
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(title='Historias con Fecha de Vencimiento (Gantt)')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay historias con fecha de vencimiento para mostrar en el Gantt.")

# === ENTREGABLES POSTVENTAS ===
if opcion == "Entregables postventas":
    from jira_conexion import jira
    import pandas as pd
    import unicodedata
    from datetime import datetime

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
        # --- IGNORAR historias que tengan MADRE en el nombre ---
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
            "Puntos": puntos,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate
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
            puntos_totales = sum(float(h["Puntos"] or 0) for h in historias)
        else:
            historias = []
            pendientes = 0
            en_proceso = 0
            porcentaje_num = 0
            porcentaje_avance = "0%"
            porcentaje_proceso = "0.0% 🔴"
            puntos_totales = 0

        # Alerta: mes actual o mes siguiente con pendientes
        mes_actual_idx = datetime.now().month - 1
        mes_siguiente_idx = (mes_actual_idx + 1) % 12
        alerta = ""
        if (mes_entrega == meses_orden[mes_actual_idx] or mes_entrega == meses_orden[mes_siguiente_idx]) and pendientes > 0:
            alerta = "⚠️ Entrega próxima con pendientes"

        tabla_prioridad.append({
            "Épica": nombre_epica,
            "Mes entrega": mes_entrega,
            "Avance": f"{porcentaje_avance} " + ("🟢" if porcentaje_num == 100 else "🟡" if porcentaje_num >= 50 else "🔴"),
            "% En proceso": porcentaje_proceso,
            "Pendientes": pendientes,
            "Puntos totales": int(puntos_totales) if puntos_totales == int(puntos_totales) else puntos_totales,
            "Alerta": alerta,
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

    # --- Mostrar tabla incompletas ---
    df_tabla = pd.DataFrame(tabla_incompletas)
    if not df_tabla.empty:
        st.markdown("## Prioridades actuales")
        st.dataframe(
            df_tabla[["Épica", "Mes entrega", "Avance", "% En proceso", "Pendientes", "Puntos totales", "Alerta"]],
            hide_index=True,
            use_container_width=True
        )

    # --- Mostrar tabla completas abajo ---
    if tabla_completas:
        df_completas = pd.DataFrame(tabla_completas)
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

#Bugsmaipu
if opcion == "BUGS Postventas":
    from jira_conexion import jira
    import pandas as pd
    import unicodedata
    import json
    from datetime import datetime
    import streamlit as st

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

    # Eliminar duplicados por key
    issues_unicos = {}
    for issue in issues:
        issues_unicos[issue['key']] = issue
    issues = list(issues_unicos.values())

    # --- Agrupar historias por épica ---
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
            if epica_custom and isinstance(epica_custom, dict) and "value" in epica_custom and epica_custom["value"]:
                epic_name = epica_custom["value"]
            elif epica_custom and isinstance(epica_custom, str) and epica_custom:
                epic_name = epica_custom
        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epic_name = "Sin epica"

        summary = issue["fields"]["summary"]
        if "madre" in summary.lower():
            continue  # No contar historias MADRE

        estado = (issue["fields"]["status"]["name"] or "").strip().lower()
        asignado = issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else ""
        key = issue["key"]
        puntos = issue["fields"].get("customfield_10026") or 0  # <= CAMPO PUNTOS (Story Points)
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
            "Puntos": puntos,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate
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
            puntos_totales = sum(float(h["Puntos"] or 0) for h in historias)
            porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
        else:
            historias = []
            puntos_totales = 0
            porcentaje_num = 0
        tabla_historico.append({
            "Épica": nombre_epica,
            "Mes entrega": mes_entrega,
            "%_num": porcentaje_num,
            "Puntos totales": puntos_totales,
            "Historias": historias
        })

    tabla_historico = sorted(tabla_historico, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    st.markdown("## Histórico de RNs postventa")
    for row in tabla_historico:
        nombre = row["Épica"]
        mes = row["Mes entrega"]
        porcentaje = row["%_num"]
        puntos_totales = row["Puntos totales"]
        historias = row["Historias"]

        expander_title = f"{nombre} | Porcentaje de avance: {porcentaje:.1f}% | Total de puntos: {puntos_totales} | {mes}"
        with st.expander(expander_title, expanded=False):
            if historias:
                for h in historias:
                    color_estado = "#39d353" if h["Estado"]=="lista para implementar" else "#fa4" if h["Estado"]=="en desarrollo" else "#bbb"
                    st.markdown(
                        f"- **{h['Clave']}** — {h['Nombre']} | <span style='color:{color_estado}'>{h['Estado'].capitalize()}</span> | Puntos: {h['Puntos']} | {h['Asignado'] if h['Asignado'] else '<i>Sin asignar</i>'}",
                        unsafe_allow_html=True
                    )
            else:
                st.markdown("*Sin historias cargadas*", unsafe_allow_html=True)





































































































