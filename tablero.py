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

# ============= DICCIONARIOS Y FUNCIÓN PARA TEMPO (antes de las pestañas) =============

MAPEO_TEM = {
    "TEM-1":  ("CORE-TECH",      "TECH LAB - INTERNO"),
    "TEM-2":  ("CORE-TECH",      "TECH LAB - INTERNO"),
    "TEM-5":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF POSVENTA"),
    "TEM-7":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS"),
    "TEM-8":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO ATI"),
    "TEM-9":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO TALLER"),
    "TEM-28": ("CORE-TECH",      "TECH LAB - INTERNO"),
    "TEM-30": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF ATI"),
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
    issue = str(row.get('Issue', '') or '')
    proyecto_raw = str(row.get('Proyecto', '') or '').strip()

    # Normalización para cargas NO TEM (por si viene CORETECH/Core Tech/etc.)
    def normalizar_proyecto(p):
        p_norm = p.upper().replace(" ", "")
        if p_norm in {"CORETECH", "CORE-TECH", "TECHLAB", "TECH-LAB", "CORETECHLAB", "CORE-TECHLAB"}:
            return "TECH LAB - INTERNO"
        return p

    # Antes de junio 2025: ignorar nuevas filas TEMPO WORKLOAD, resto usar proyecto normalizado
    if fecha < pd.Timestamp("2025-06-01"):
        if proyecto_raw == "TEMPO WORKLOAD":
            return None
        return normalizar_proyecto(proyecto_raw)

    # Desde junio 2025: si es TEM-, usar el mapeo
    if issue.startswith("TEM-"):
        cuenta, resumen = MAPEO_TEM.get(issue, ("", ""))
        if cuenta == "CORE-TECH":
            # Todo CORE-TECH (que no tenga un caso especial) va a interno
            return "TECH LAB - INTERNO"
        elif cuenta == "MP-MAIPU-SUMMA":
            return RESUMEN_A_PROYECTO.get(resumen, "OTRO")
        # Si no lo encontramos en el mapeo, caemos al proyecto normalizado
        return normalizar_proyecto(proyecto_raw)

    # Desde junio 2025 y NO es TEM-: usar proyecto normalizado
    return normalizar_proyecto(proyecto_raw)

# Aplica la lógica
df["Proyecto_logico"] = df.apply(obtener_proyecto_logico, axis=1)
df = df[df["Proyecto_logico"].notna()]

# Proyectos por pestaña
PROYECTOS_POSTVENTA = [
    "TALLER - MAIPÚ -",
    "REPUESTOS MAIPU",
    "AFUS",
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

# === PESTAÑA HORAS (Postventas / ATI) ===
if opcion in ["Horas Postventas", "Horas ATI"]:
    from datetime import datetime

    # Constantes de proyectos (igual que antes)
    INTERNAL = "TECH LAB - INTERNO"
    POSTVENTA_NON_INTERNAL = ["TALLER - MAIPÚ -", "REPUESTOS MAIPU", "AFUS"]
    ATI_NON_INTERNAL       = ["AFUs ATI"]

    viendo_post = (opcion == "Horas Postventas")
    proyectos_mostrar = (POSTVENTA_NON_INTERNAL + [INTERNAL]) if viendo_post else (ATI_NON_INTERNAL + [INTERNAL])

    MESES_ES = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    if not df.empty:
        cols = st.columns(3)

        with cols[0]:
            years = sorted(df["Fecha"].apply(lambda x: str(x)[:4]).unique())
            year = st.selectbox("Año", options=years, index=len(years) - 1, key=f"horas_{opcion}_anio")

        with cols[1]:
            meses_numeros = list(MESES_ES.keys())
            meses_nombres = [MESES_ES[m] for m in meses_numeros]
            mes_nom = st.selectbox("Mes", options=meses_nombres, index=datetime.now().month - 1, key=f"horas_{opcion}_mes")
            mes_real = meses_numeros[meses_nombres.index(mes_nom)]

        with cols[2]:
            usuarios_lista = ["Todos"] + sorted([u for u in df["Usuario"].dropna().unique() if str(u).strip() != ""])
            usuario_seleccionado = st.selectbox("Usuario", usuarios_lista, index=0, key=f"horas_{opcion}_usuario")

        # ---- Función auxiliar para armar el texto "Usuario (TEM-1, TEM-2); Otro (TEM-5)"
        def _usuarios_y_tems_string(df_alert):
            pares = []
            for usuario, g in df_alert.groupby("Usuario"):
                tems = sorted(g["Issue"].astype(str).unique(), key=lambda x: (len(x), x))
                if str(usuario).strip():
                    pares.append(f"{usuario} ({', '.join(tems)})")
            return "; ".join(pares)

        # ============ VISTA "TODOS" ============
        if usuario_seleccionado == "Todos":
            # 1) Filtro por año/mes (sin filtrar proyecto aún)
            df_mes = df[df["Fecha"].str.startswith(str(year))]
            df_mes = df_mes[df_mes["Fecha"].str[5:7] == mes_real]

            # 2) Usuarios que cargaron no-internal por área (en ese mes)
            users_post = set(df_mes[df_mes["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL)]["Usuario"])
            users_ati  = set(df_mes[df_mes["Proyecto_logico"].isin(ATI_NON_INTERNAL)]["Usuario"])
            users_both = users_post & users_ati

            # 3) Armar vista según pestaña
            if viendo_post:
                # POSTVENTAS:
                # - Usuarios BOTH: TODAS sus filas (ATI + POST + INTERNO)
                # - Usuarios solo POST: filas POST + INTERNO
                df_vista = df_mes[
                    (df_mes["Usuario"].isin(users_both)) |
                    (
                        df_mes["Usuario"].isin(users_post) &
                        (df_mes["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL + [INTERNAL]))
                    )
                ]
            else:
                # ATI:
                # - Usuarios BOTH: TODAS sus filas (ATI + POST + INTERNO)
                # - Usuarios solo ATI: filas ATI + INTERNO
                df_vista = df_mes[
                    (df_mes["Usuario"].isin(users_both)) |
                    (
                        df_mes["Usuario"].isin(users_ati) &
                        (df_mes["Proyecto_logico"].isin(ATI_NON_INTERNAL + [INTERNAL]))
                    )
                ]

            # === ALERTA: TEM NO MAPEADAS (solo mes/año seleccionados, solo usuarios mapeados y de la vista) ===
            if not df_vista.empty:
                # Trabajar únicamente con usuarios mapeados a nombre (JSON aplicado previamente)
                df_mes_alerta = df_mes[df_mes["Usuario"].notna()].copy()

                # TEM no mapeada = Issue arranca "TEM-" y NO está en MAPEO_TEM
                mask_tem_no_mapeada = (
                    df_mes_alerta["Issue"].astype(str).str.startswith("TEM-", na=False) &
                    (~df_mes_alerta["Issue"].isin(list(MAPEO_TEM.keys())))
                )

                # Limitar a usuarios que realmente aparecen en la vista (y están mapeados)
                usuarios_vista = set(df_vista["Usuario"].dropna().unique())
                df_tem_no_mapeada = df_mes_alerta[mask_tem_no_mapeada & df_mes_alerta["Usuario"].isin(usuarios_vista)].copy()

                if not df_tem_no_mapeada.empty:
                    usuarios_y_tems = _usuarios_y_tems_string(df_tem_no_mapeada)
                    st.error(f"⚠️ **TEM no mapeadas** en {MESES_ES[mes_real]} {year}. {usuarios_y_tems}")
                    cols_alerta = ["Usuario", "Fecha", "Issue", "Proyecto", "Horas"]
                    for c in cols_alerta:
                        if c not in df_tem_no_mapeada.columns:
                            df_tem_no_mapeada[c] = ""
                    st.dataframe(
                        df_tem_no_mapeada[cols_alerta].sort_values(["Usuario", "Fecha"]),
                        use_container_width=True, hide_index=True
                    )

            if df_vista.empty:
                st.warning("No hay horas cargadas para el mes, año y usuario seleccionados.")
            else:
                # 4) Pivot por usuario x proyecto
                tabla_pivot = pd.pivot_table(
                    df_vista,
                    values='Horas',
                    index='Usuario',
                    columns='Proyecto_logico',
                    aggfunc='sum',
                    fill_value=0
                )
                # asegurar columnas en el orden esperado
                for col in proyectos_mostrar:
                    if col not in tabla_pivot.columns:
                        tabla_pivot[col] = 0
                tabla_pivot = tabla_pivot[proyectos_mostrar]

                tabla_pivot["Total"] = tabla_pivot.sum(axis=1)
                totales = tabla_pivot.sum(axis=0)
                tabla_final = pd.concat([tabla_pivot, pd.DataFrame([totales], index=["Total general"])])

                mostrar_detalle = st.checkbox("Mostrar detalle por proyecto", value=False, key=f"horas_{opcion}_detalle")
                tabla_mostrar = tabla_final if mostrar_detalle else tabla_final[["Total"]]

                st.dataframe(
                    tabla_mostrar.reset_index().style.format({
                        c: "{:,.2f}".format for c in tabla_mostrar.columns if c != "Usuario"
                    }),
                    use_container_width=True,
                    hide_index=True
                )

        # ============ VISTA POR USUARIO ============
        else:
            # Universo del usuario (para gráficos/tabla) — igual que antes
            fecha_ref = datetime(int(year), int(mes_real), 1)
            fecha_inicio = (fecha_ref - pd.DateOffset(months=5)).replace(day=1)

            df_user = df[df["Usuario"] == usuario_seleccionado].copy()
            df_user["Fecha_dt"] = pd.to_datetime(df_user["Fecha"], errors="coerce")
            df_user = df_user[
                (df_user["Fecha_dt"] >= fecha_inicio) &
                (df_user["Fecha_dt"] <= fecha_ref + pd.offsets.MonthEnd(0))
            ]
            df_user["anio_mes"] = df_user["Fecha_dt"].dt.strftime("%Y-%m")

            # Para la vista, incluir INTERNAL solo si trabajó en el área ese mes
            meses_ultimos = pd.date_range(start=fecha_inicio, end=fecha_ref, freq="MS").strftime("%Y-%m").tolist()
            bolsas = []
            for ym in meses_ultimos:
                df_m = df_user[df_user["anio_mes"] == ym]
                if df_m.empty:
                    continue

                has_post = df_m["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL).any()
                has_ati  = df_m["Proyecto_logico"].isin(ATI_NON_INTERNAL).any()

                if has_post and has_ati:
                    bolsas.append(df_m)  # si trabajó en ambas, mostrar todo
                elif viendo_post and has_post:
                    bolsas.append(df_m[df_m["Proyecto_logico"].isin(POSTVENTA_NON_INTERNAL + [INTERNAL])])
                elif (not viendo_post) and has_ati:
                    bolsas.append(df_m[df_m["Proyecto_logico"].isin(ATI_NON_INTERNAL + [INTERNAL])])

            df_user_vista = pd.concat(bolsas, ignore_index=True) if bolsas else pd.DataFrame(columns=df_user.columns)

            # === ALERTA: TEM NO MAPEADAS (solo mes/año seleccionados, usuario mapeado) ===
            df_user_mes = df[
                (df["Fecha"].str.startswith(str(year))) &
                (df["Fecha"].str[5:7] == mes_real) &
                (df["Usuario"] == usuario_seleccionado)
            ].copy()

            if not df_user_mes.empty and pd.notna(usuario_seleccionado):
                mask_tem_no_mapeada_user = (
                    df_user_mes["Issue"].astype(str).str.startswith("TEM-", na=False) &
                    (~df_user_mes["Issue"].isin(list(MAPEO_TEM.keys())))
                )
                df_tem_no_mapeada_user = df_user_mes[mask_tem_no_mapeada_user].copy()
                if not df_tem_no_mapeada_user.empty:
                    usuarios_y_tems = _usuarios_y_tems_string(df_tem_no_mapeada_user)
                    # en vista por usuario, el string tendrá un solo usuario
                    st.error(f"⚠️ **TEM no mapeadas** en {MESES_ES[mes_real]} {year}. {usuarios_y_tems}")
                    cols_alerta = ["Usuario", "Fecha", "Issue", "Proyecto", "Horas"]
                    for c in cols_alerta:
                        if c not in df_tem_no_mapeada_user.columns:
                            df_tem_no_mapeada_user[c] = ""
                    st.dataframe(
                        df_tem_no_mapeada_user[cols_alerta].sort_values(["Fecha"]),
                        use_container_width=True, hide_index=True
                    )

            # Resumen por mes (últimos 6)
            if df_user_vista.empty:
                st.subheader(f"Horas cargadas por {usuario_seleccionado} (últimos 6 meses)")
                st.info("Sin datos para mostrar con los criterios actuales.")
            else:
                resumen_meses = df_user_vista.groupby("anio_mes")["Horas"].sum().reset_index()
                resumen_meses = resumen_meses.set_index("anio_mes").reindex(meses_ultimos, fill_value=0).reset_index()
                resumen_meses["Mes"] = resumen_meses["anio_mes"].apply(lambda x: MESES_ES[x[5:]] + " " + x[:4])

                st.subheader(f"Horas cargadas por {usuario_seleccionado} (últimos 6 meses)")
                st.dataframe(resumen_meses[["Mes", "Horas"]], hide_index=True, use_container_width=True)
                st.bar_chart(resumen_meses.set_index("anio_mes")["Horas"], use_container_width=True)
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
# === BUGS POSTVENTAS (Proyecto BUG) ===
# === BUGS POSTVENTAS (Proyecto BUG) ===
if opcion == "BUGS Postventas":
    from jira_conexion import jira
    import pandas as pd
    import unicodedata
    import re

    st.subheader("Bugs creados por Mes – Proyecto BUG")

    # ----------------------------
    # Helpers
    # ----------------------------
    def traer_todas_las_issues(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
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

    def get_issue_type(key, cache):
        """Devuelve issuetype.name para una KEY (usa caché)."""
        if key in cache:
            return cache[key]
        try:
            data = jira._get_json(f'issue/{key}?fields=issuetype')
            tname = ((data.get("fields") or {}).get("issuetype") or {}).get("name") or ""
        except Exception:
            tname = ""
        cache[key] = tname
        return tname

    def get_issue_links(key, cache):
        """Devuelve issuelinks para una KEY (usa caché)."""
        if key in cache:
            return cache[key]
        try:
            data = jira._get_json(f'issue/{key}?fields=issuelinks')
            links = (data.get("fields") or {}).get("issuelinks") or []
        except Exception:
            links = []
        cache[key] = links
        return links

    def get_issue_summary(key, cache):
        """Devuelve summary para una KEY (usa caché)."""
        if key in cache:
            return cache[key]
        try:
            data = jira._get_json(f'issue/{key}?fields=summary')
            s = (data.get("fields") or {}).get("summary") or ""
        except Exception:
            s = ""
        cache[key] = s
        return s

    def detectar_campo_epic_link():
        """
        Descubre el id/clave del campo 'Epic Link' en esta instancia.
        Devuelve algo tipo 'customfield_10014' o '' si no encuentra.
        """
        try:
            fields = jira._get_json("field")
            candidatos = []
            for f in fields:
                name = (f.get("name") or "").strip().lower()
                key  = (f.get("key") or f.get("id") or "").strip()
                if any(x in name for x in ["epic link", "enlace épico", "enlace epico", "epik link"]):
                    candidatos.append(key)
            # preferir customfield_*
            for c in candidatos:
                if c.startswith("customfield_"):
                    return c
            return candidatos[0] if candidatos else ""
        except Exception:
            return ""

    MESES_ES = {
        1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
        7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"
    }
    PRIORIDADES_ORDEN = ["Muy alta", "Alta", "Media", "Baja", "Muy baja"]
    PROYECTOS_VALIDOS = ["Taller", "Repuestos", "ATI"]

    def _strip(s: str) -> str:
        """lowercase sin acentos."""
        s = s or ""
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
        return s.lower().strip()

    def normalizar_prioridad(name: str) -> str:
        p = re.sub(r"[\s_\-]+", " ", _strip(name))
        if re.search(r"\b(p0|p1)\b", p): return "Muy alta"
        if re.search(r"\bp2\b", p):      return "Alta"
        if re.search(r"\bp3\b", p):      return "Media"
        if re.search(r"\bp4\b", p):      return "Baja"
        if re.search(r"\bp5\b", p):      return "Muy baja"
        if any(k in p for k in ["critical","critica","highest","muy alta"]): return "Muy alta"
        if "lowest" in p or "muy baja" in p: return "Muy baja"
        if "high" in p or "alta" in p:       return "Alta"
        if "low" in p or "baja" in p:        return "Baja"
        if "medium" in p or "media" in p or "normal" in p: return "Media"
        return "Media"

    def es_bug_type(name: str) -> bool:
        """Detecta tipos de bug en ES/EN (Bug/Error/Defecto/Incidencia)."""
        n = _strip(name)
        return any(k in n for k in ["bug", "error", "defecto", "incidencia"])

    def proyecto_por_prefijo_key(key: str) -> str:
        k = (key or "").upper()
        if k.startswith("TAL-"): return "Taller"
        if k.startswith("REP-"): return "Repuestos"
        if k.startswith("ATI-"): return "ATI"
        return ""

    def proyecto_por_prefijo_summary(summary: str) -> str:
        """Detecta [REP]/[TAL]/[ATI] al inicio del summary."""
        m = re.match(r"^\s*\[\s*(REP|TAL|ATI)\s*\]", (summary or ""), flags=re.IGNORECASE)
        if not m: return ""
        tag = m.group(1).upper()
        return {"REP": "Repuestos", "TAL": "Taller", "ATI": "ATI"}[tag]

    # ----------------------------
    # UI: filtros
    # ----------------------------
    col1, col2 = st.columns([1,1])
    with col1:
        proyecto_filtro = st.selectbox(
            "Proyecto",
            options=["Todos"] + PROYECTOS_VALIDOS,
            index=0,
            key="bugs_proyecto_filtro",
        )

    # ----------------------------
    # Detecto el campo Epic Link y consulto a Jira (solo 2025+)
    # ----------------------------
    EPIC_FIELD = detectar_campo_epic_link()
    jql = 'project = BUG AND created >= "2025-01-01"'
    fields = "key,created,priority,issuetype,issuelinks,summary" + (f",{EPIC_FIELD}" if EPIC_FIELD else "")

    try:
        issues = traer_todas_las_issues(jira, jql, fields)
    except Exception as e:
        st.error(f"Error consultando Jira: {e}")
        issues = []

    # ----------------------------
    # Clasificación FINAL (como acordamos):
    # 1) Si tiene BUG vinculado => Tipo="Bug" (cuenta por prioridad).
    #    Proyecto = HU(s) de esos BUG(s) vinculados;
    #    si no hay HU, intento prefijo [REP]/[TAL]/[ATI] en summary de los BUG(s) vinculados;
    #    si tampoco, intento prefijo en el summary del propio bug.
    # 2) Si NO tiene BUG y SÍ tiene HU => Tipo="Mejora" (proyecto por HU propias).
    # 3) Si NO tiene BUG ni HU pero el summary empieza [REP]/[TAL]/[ATI] => Tipo="Bug" (proyecto por prefijo).
    # 4) Si nada de lo anterior o proyecto ambiguo/fuera de ATI/Taller/Repuestos => Excluir y advertir.
    #
    # Además: guardamos Epic = valor de Epic Link (si existe).
    # ----------------------------
    type_cache, links_cache, summary_cache = {}, {}, {}
    rows, excluidos = [], []

    for it in issues:
        f = it.get("fields") or {}
        itype = ((f.get("issuetype") or {}).get("name") or "")
        if not es_bug_type(itype):
            continue  # sólo bugs reales del proyecto BUG

        created_dt = pd.to_datetime(f.get("created"), errors="coerce")
        if pd.isna(created_dt):
            continue

        prio = normalizar_prioridad((f.get("priority") or {}).get("name"))
        summary = f.get("summary") or ""

        # Epic (Epic Link) del propio issue, si está disponible
        epic_val = ""
        if EPIC_FIELD:
            v = f.get(EPIC_FIELD)
            if isinstance(v, str):
                epic_val = v.strip().upper()
            elif isinstance(v, dict):
                epic_val = ((v.get("key") or v.get("id") or "") or "").upper()

        # vínculos directos
        direct_bug_keys, direct_story_keys = set(), set()
        for lk in (f.get("issuelinks") or []):
            for side in ("inwardIssue", "outwardIssue"):
                other = lk.get(side)
                if not other:
                    continue
                okey = (other.get("key") or "").upper()
                ot = ((other.get("fields") or {}).get("issuetype") or {}).get("name")
                if not ot:
                    ot = get_issue_type(okey, type_cache)

                if es_bug_type(ot) or okey.startswith("BUG-"):
                    direct_bug_keys.add(okey)

                ot_l = _strip(ot)
                if ("story" in ot_l) or ("historia" in ot_l) or proyecto_por_prefijo_key(okey):
                    direct_story_keys.add(okey)

        tiene_bug = len(direct_bug_keys) > 0
        tiene_hu  = len(direct_story_keys) > 0

        tipo_final, proyecto = None, ""

        if tiene_bug:
            # 1º intento: proyecto por HU de los BUG(s) vinculados
            proyectos_via_bug = set()
            for bkey in direct_bug_keys:
                for lk2 in get_issue_links(bkey, links_cache):
                    for side2 in ("inwardIssue", "outwardIssue"):
                        other2 = lk2.get(side2)
                        if not other2:
                            continue
                        k2 = (other2.get("key") or "").upper()
                        t2 = ((other2.get("fields") or {}).get("issuetype") or {}).get("name")
                        if not t2:
                            t2 = get_issue_type(k2, type_cache)
                        t2_l = _strip(t2)
                        if ("story" in t2_l) or ("historia" in t2_l) or proyecto_por_prefijo_key(k2):
                            pj = proyecto_por_prefijo_key(k2)
                            if pj:
                                proyectos_via_bug.add(pj)

            if len(proyectos_via_bug) == 1:
                proyecto = list(proyectos_via_bug)[0]
                tipo_final = "Bug"
            else:
                # 2º intento: prefijo del summary de los BUG(s) vinculados
                proyectos_by_bugname = set()
                for bkey in direct_bug_keys:
                    sum_b = get_issue_summary(bkey, summary_cache)
                    pj_b = proyecto_por_prefijo_summary(sum_b)
                    if pj_b:
                        proyectos_by_bugname.add(pj_b)

                if len(proyectos_by_bugname) == 1:
                    proyecto = list(proyectos_by_bugname)[0]
                    tipo_final = "Bug"
                else:
                    # 3º intento: prefijo del summary del bug actual
                    pj_by_name = proyecto_por_prefijo_summary(summary)
                    if pj_by_name:
                        proyecto = pj_by_name
                        tipo_final = "Bug"
                    else:
                        tipo_final = "Excluir"

        elif tiene_hu:
            # MEJORA (sin bug vinculado)
            proyectos_de_hu = {proyecto_por_prefijo_key(k) for k in direct_story_keys}
            proyectos_de_hu.discard("")
            if len(proyectos_de_hu) == 1:
                proyecto = list(proyectos_de_hu)[0]
                tipo_final = "Mejora"
            else:
                tipo_final = "Excluir"

        else:
            # Sin bug ni HU → intento por nombre [REP]/[TAL]/[ATI] ⇒ BUG
            pj_by_name = proyecto_por_prefijo_summary(summary)
            if pj_by_name:
                proyecto = pj_by_name
                tipo_final = "Bug"
            else:
                tipo_final = "Excluir"

        if (tipo_final == "Excluir") or (proyecto not in PROYECTOS_VALIDOS):
            excluidos.append(it.get("key", ""))
            continue

        anio, mes = int(created_dt.year), int(created_dt.month)
        rows.append({
            "Clave": it.get("key", ""),
            "Creado": created_dt,
            "AñoMes": f"{anio}-{mes:02d}",
            "Mes": f"{MESES_ES[mes]} {anio}",
            "Prioridad": prio,
            "Proyecto": proyecto,    # Taller / Repuestos / ATI
            "Tipo": tipo_final,      # Bug / Mejora
            "Summary": summary,
            "Epic": epic_val,        # <- Epic Link del issue (si existe)
        })

    # Advertencia por excluidos
    if excluidos:
        preview = ", ".join(sorted(excluidos[:80]))
        extra = f" (+{len(excluidos)-80} más)" if len(excluidos) > 80 else ""
        st.warning(
            f"Se excluyeron {len(excluidos)} issues por no tener vínculos válidos (Bug/HU) o proyecto ambiguo/fuera de ATI-Taller-Repuestos: {preview}{extra}"
        )

    if not rows:
        st.info("No hay datos para mostrar con las condiciones actuales.")
    else:
        df_all = pd.DataFrame(rows).sort_values("AñoMes")

        # lookup Mes para selector
        meses_disp = df_all[["AñoMes","Mes"]].drop_duplicates().sort_values("AñoMes")
        mes_lookup = meses_disp.copy()

        # Filtro por proyecto
        if proyecto_filtro != "Todos":
            df_all = df_all[df_all["Proyecto"] == proyecto_filtro]

        # Selector de Mes (detalle opcional)
        opciones_mes = ["(sin detalle)"] + meses_disp["Mes"].tolist()
        mes_detalle = col2.selectbox(
            "Mes (detalle opcional)",
            options=opciones_mes,
            index=0,
            key="bugs_mes_detalle"
        )

        # Split final
        df_bugs    = df_all[df_all["Tipo"] == "Bug"].copy()       # cuenta por prioridad
        df_mejoras = df_all[df_all["Tipo"] == "Mejora"].copy()    # columna "Mejoras"

        # ---- Conteos por Mes y Prioridad (solo BUGS) ----
        if df_bugs.empty:
            tabla_pivot = pd.DataFrame(columns=["AñoMes"] + PRIORIDADES_ORDEN)
        else:
            tabla = (
                df_bugs
                .groupby(["AñoMes", "Prioridad"], as_index=False)["Clave"]
                .count()
                .rename(columns={"Clave": "Cantidad"})
            )
            tabla_pivot = tabla.pivot_table(
                index=["AñoMes"],
                columns="Prioridad",
                values="Cantidad",
                aggfunc="sum",
                fill_value=0
            ).reset_index()

        # Asegurar todas las prioridades
        for p in PRIORIDADES_ORDEN:
            if p not in tabla_pivot.columns:
                tabla_pivot[p] = 0

        # ---- Columna Mejoras (por Mes) ----
        if df_mejoras.empty:
            mejoras_por_mes = pd.DataFrame(columns=["AñoMes", "Mejoras"])
            claves_mejoras = pd.DataFrame(columns=["AñoMes", "__claves_mejoras__"])
        else:
            mejoras_por_mes = (
                df_mejoras.groupby(["AñoMes"], as_index=False)["Clave"]
                .count()
                .rename(columns={"Clave": "Mejoras"})
            )
            claves_mejoras = (
                df_mejoras.groupby("AñoMes")["Clave"]
                .apply(lambda s: ", ".join(sorted(s.tolist())))
                .reset_index(name="__claves_mejoras__")
            )

        # ---- Claves de Bugs prioridad Muy alta (solo BUGS) ----
        if df_bugs.empty:
            claves_muy_alta = pd.DataFrame(columns=["AñoMes", "__claves_muyalta__"])
        else:
            df_muy_alta = df_bugs[df_bugs["Prioridad"] == "Muy alta"]
            claves_muy_alta = (
                df_muy_alta.groupby("AñoMes")["Clave"]
                .apply(lambda s: ", ".join(sorted(s.tolist())))
                .reset_index(name="__claves_muyalta__")
            )

        # Merge y columnas finales
        out = tabla_pivot.merge(mejoras_por_mes, on="AñoMes", how="outer")
        out = out.merge(claves_mejoras, on="AñoMes", how="left")
        out = out.merge(claves_muy_alta, on="AñoMes", how="left")
        out = out.merge(mes_lookup, on="AñoMes", how="left")  # agrega nombre de Mes

        out["Mejoras"] = out["Mejoras"].fillna(0).astype(int)
        out["__claves_mejoras__"] = out["__claves_mejoras__"].fillna("")
        out["__claves_muyalta__"] = out["__claves_muyalta__"].fillna("")

        def _combinar_claves(row):
            parts = []
            if row["__claves_mejoras__"]:
                parts.append(f"Mejoras: {row['__claves_mejoras__']}")
            if row["__claves_muyalta__"]:
                parts.append(f"Muy alta: {row['__claves_muyalta__']}")
            return " · ".join(parts)

        out["Claves (Mejoras + Muy alta)"] = out.apply(_combinar_claves, axis=1)
        out["Total"] = out[PRIORIDADES_ORDEN].sum(axis=1) + out["Mejoras"]

        out = out[["AñoMes", "Mes"] + PRIORIDADES_ORDEN + ["Mejoras", "Total", "Claves (Mejoras + Muy alta)"]]
        out = out.sort_values("AñoMes").reset_index(drop=True)

        st.markdown("### Tabla de Bugs creados por Mes")
        st.dataframe(
            out[["Mes"] + PRIORIDADES_ORDEN + ["Mejoras", "Total", "Claves (Mejoras + Muy alta)"]],
            use_container_width=True,
            hide_index=True
        )

        # =========================
        # DETALLE POR MES (opcional)
        # =========================
        if mes_detalle != "(sin detalle)":
            inv = dict(zip(meses_disp["Mes"], meses_disp["AñoMes"]))
            am_sel = inv.get(mes_detalle)
            if am_sel:
                st.markdown(f"### Detalle de {mes_detalle}")

                df_mes = df_all[df_all["AñoMes"] == am_sel].copy()
                df_mes_bugs = df_mes[df_mes["Tipo"] == "Bug"].copy()
                df_mes_mej  = df_mes[df_mes["Tipo"] == "Mejora"].copy()

                # --- Bugs: resumen por prioridad
                if not df_mes_bugs.empty:
                    resumen_prio = (
                        df_mes_bugs.groupby("Prioridad", as_index=False)["Clave"]
                        .count()
                        .rename(columns={"Clave": "Cantidad"})
                        .sort_values("Cantidad", ascending=False)
                    )
                    st.markdown("**Bugs — Resumen por Prioridad**")
                    st.dataframe(resumen_prio, use_container_width=True, hide_index=True)

                # --- Funciones de "nombre base" para agrupar por palabras del summary
                STOP_ES = {
                    "de","la","el","y","en","para","por","con","del","al","los","las","un","una","unos","unas",
                    "a","se","que","no","si","es","son","como","esta","este","esto","estas","estos","su","sus",
                    "lo","ya","hay","más","mas","cuando","donde","entre","sobre","sin","o","u","pero","muy",
                    "the","and","of","to","in","on","for","by","from"
                }
                def tokens_summary(summary: str):
                    s = _strip(summary)
                    toks = re.split(r"[^a-z0-9áéíóúñ]+", s)
                    toks = [t for t in toks if t and len(t) >= 4 and t not in STOP_ES and not t.isdigit()]
                    return toks
                def key_nombre_base(summary: str, max_tokens=3):
                    toks = tokens_summary(summary)
                    return " ".join(toks[:max_tokens]) if toks else "(otros)"

                # --- Bugs: agrupación por “Nombre base”
                if not df_mes_bugs.empty:
                    df_nb = df_mes_bugs.copy()
                    df_nb["Nombre base"] = df_nb["Summary"].apply(key_nombre_base)
                    grupo_nb = (
                        df_nb.groupby("Nombre base")["Clave"]
                        .apply(lambda s: (len(s), ", ".join(sorted(s.tolist()))))
                        .reset_index()
                    )
                    grupo_nb[["Cantidad","Claves"]] = pd.DataFrame(grupo_nb["Clave"].tolist(), index=grupo_nb.index)
                    grupo_nb = grupo_nb.drop(columns=["Clave"]).sort_values("Cantidad", ascending=False)
                    st.markdown("**Bugs — Agrupados por “Nombre base” (palabras clave)**")
                    st.dataframe(grupo_nb[["Nombre base","Cantidad","Claves"]], use_container_width=True, hide_index=True)

                # --- Bugs: agrupación por Épica (USANDO EPIC LINK)
                if not df_mes_bugs.empty:
                    df_ep = df_mes_bugs.copy()
                    df_ep["Épica"] = df_ep["Epic"].apply(lambda x: x if x else "(Sin épica)")
                    grupo_ep = (
                        df_ep.groupby("Épica")["Clave"]
                        .apply(lambda s: (len(s), ", ".join(sorted(s.tolist()))))
                        .reset_index()
                    )
                    grupo_ep[["Cantidad","Claves"]] = pd.DataFrame(grupo_ep["Clave"].tolist(), index=grupo_ep.index)
                    grupo_ep = grupo_ep.drop(columns=["Clave"]).sort_values("Cantidad", ascending=False)
                    st.markdown("**Bugs — Agrupados por Épica (Epic Link)**")
                    st.dataframe(grupo_ep[["Épica","Cantidad","Claves"]], use_container_width=True, hide_index=True)

                # --- Mejoras: agrupación por “Nombre base”
                if not df_mes_mej.empty:
                    dfm_nb = df_mes_mej.copy()
                    dfm_nb["Nombre base"] = dfm_nb["Summary"].apply(key_nombre_base)
                    grupo_nb_m = (
                        dfm_nb.groupby("Nombre base")["Clave"]
                        .apply(lambda s: (len(s), ", ".join(sorted(s.tolist()))))
                        .reset_index()
                    )
                    grupo_nb_m[["Cantidad","Claves"]] = pd.DataFrame(grupo_nb_m["Clave"].tolist(), index=grupo_nb_m.index)
                    grupo_nb_m = grupo_nb_m.drop(columns=["Clave"]).sort_values("Cantidad", ascending=False)
                    st.markdown("**Mejoras — Agrupadas por “Nombre base”**")
                    st.dataframe(grupo_nb_m[["Nombre base","Cantidad","Claves"]], use_container_width=True, hide_index=True)

                # --- Mejoras: agrupación por Épica (USANDO EPIC LINK)
                if not df_mes_mej.empty:
                    df_ep_m = df_mes_mej.copy()
                    df_ep_m["Épica"] = df_ep_m["Epic"].apply(lambda x: x if x else "(Sin épica)")
                    grupo_ep_m = (
                        df_ep_m.groupby("Épica")["Clave"]
                        .apply(lambda s: (len(s), ", ".join(sorted(s.tolist()))))
                        .reset_index()
                    )
                    grupo_ep_m[["Cantidad","Claves"]] = pd.DataFrame(grupo_ep_m["Clave"].tolist(), index=grupo_ep_m.index)
                    grupo_ep_m = grupo_ep_m.drop(columns=["Clave"]).sort_values("Cantidad", ascending=False)
                    st.markdown("**Mejoras — Agrupadas por Épica (Epic Link)**")
                    st.dataframe(grupo_ep_m[["Épica","Cantidad","Claves"]], use_container_width=True, hide_index=True)





#Historico postventas
# === PESTAÑA HISTÓRICO POSTVENTA (COMPLETA) ===
if opcion == "Histórico postventa":
    from jira_conexion import jira
    import unicodedata
    import pandas as pd

    # ------------------ Helpers ------------------
    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    def _status_norm(s: str) -> str:
        return (s or "").strip().lower()

    def traer_todos_los_issues(jira, jql, fields, max_results=100):
        issues = []
        start_at = 0
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
        """Trae BUGS con expand=changelog para medir tiempos."""
        issues = []
        start_at = 0
        while True:
            endpoint = (
                f'search?jql={jql}&fields={fields}'
                f'&expand=changelog&startAt={start_at}&maxResults={max_results}'
            )
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    def _bug_resolution_hours(bug_issue) -> float | None:
        """
        Demora (hs) desde la PRIMERA vez que el bug pasa a 'Haciendo' (o 'In Progress')
        hasta la PRIMERA vez que pasa a 'Hecha/Resuelto/Resuelta/Done'.
        Si no hay 'Haciendo', usa fecha de creación como inicio.
        """
        f = bug_issue.get("fields", {}) or {}
        created = pd.to_datetime(f.get("created"), errors="coerce")

        start_dt = None
        end_dt = None

        histories = (bug_issue.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))

        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            for it in hist.get("items", []) or []:
                if _status_norm(it.get("field")) == "status":
                    to_str = _status_norm(it.get("toString"))
                    if start_dt is None and to_str in ("haciendo", "in progress"):
                        start_dt = h_created
                    if end_dt is None and to_str in ("hecha", "resuelto", "resuelta", "done"):
                        end_dt = h_created

        if start_dt is None:
            start_dt = created
        if pd.isna(start_dt) or end_dt is None or pd.isna(end_dt):
            return None

        return float((end_dt - start_dt).total_seconds() / 3600.0)

    def _bugs_por_hu(bugs_issues) -> dict:
        """
        Dict { HU_KEY: {"bugs": [bug_key,...], "hrs": [resol_horas,...]} }
        HU detectada por parent y por cualquier issuelink.
        """
        por_hu = {}
        for iss in bugs_issues:
            f = iss.get("fields", {}) or {}
            itype = _status_norm((f.get("issuetype", {}) or {}).get("name"))
            if itype != "error":
                continue

            bug_key = iss.get("key", "")
            if not bug_key:
                continue

            # HUs candidatas: parent + TODOS los links
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

    # ------------------ Fuente de datos ------------------
    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    # Historias (REP + TAL)
    fields_hist = (
        "key,summary,status,project,issuetype,assignee,parent,"
        "customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated"
    )
    issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields_hist)
    issues_rep = traer_todos_los_issues(jira, 'project = REP AND issuetype = Historia', fields_hist)
    issues = issues_tal + issues_rep

    # Desduplico por key
    issues_unicos = {iss['key']: iss for iss in issues}
    issues = list(issues_unicos.values())

    # BUGS (REP + TAL) con changelog
    fields_bugs = "key,project,issuetype,status,assignee,parent,issuelinks,created"
    bugs_rep = traer_bugs_con_changelog(jira, 'project = REP AND issuetype = Error', fields_bugs)
    bugs_tal = traer_bugs_con_changelog(jira, 'project = TAL AND issuetype = Error', fields_bugs)
    bugs_all = bugs_rep + bugs_tal

    # Mapa HU -> {bugs, hrs}
    mapa_bugs_hu = _bugs_por_hu(bugs_all)

    # ------------------ Agrupar historias por Épica (RN) ------------------
    EPIC_LINK_CAMPO = "customfield_10016"
    epicas = {}
    for issue in issues:
        f = issue.get("fields", {}) or {}

        # Nombre de épica (RN)
        epic_name = None
        parent = f.get("parent")
        if parent:
            # parent.summary directo o dentro de fields
            epic_name = (parent.get("summary")
                         or (parent.get("fields") or {}).get("summary"))

        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epica_custom = f.get(EPIC_LINK_CAMPO, None)
            if isinstance(epica_custom, dict) and epica_custom.get("value"):
                epic_name = epica_custom["value"]
            elif isinstance(epica_custom, str) and epica_custom:
                epic_name = epica_custom

        if not epic_name or epic_name.lower() in ["sin epica", "sin épica", "none", ""]:
            epic_name = "Sin epica"

        summary = f.get("summary", "")
        if "madre" in summary.lower():
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

        slot = epicas.setdefault(epic_name, {"Historias": [], "Mes de entrega": None})
        slot["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,  # normalizado
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos,
        })

    # ------------------ Tabla de histórico (usa tu lista 'epicas_relevantes') ------------------
    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except Exception:
            return 99

    tabla_historico = []
    for epica_rn in epicas_relevantes:  # ← tu lista existente con {"nombre", "mes_entrega"}
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

            # === BUGS por RN (a partir de las HUs del RN) ===
            hu_keys = [h["Clave"] for h in historias if h.get("Clave")]
            bugs_keys = []
            bugs_hrs = []
            for hu in hu_keys:
                info = mapa_bugs_hu.get(hu)
                if not info:
                    continue
                bugs_keys.extend(info.get("bugs", []))
                bugs_hrs.extend(info.get("hrs", []))

            uniq_bugs = sorted(set(bugs_keys))
            bugs_cnt = len(uniq_bugs)
            prom_hrs = round(sum(bugs_hrs) / len(bugs_hrs), 2) if bugs_hrs else None

        else:
            historias = []
            porcentaje_num = 0
            puntos_totales = 0
            uniq_bugs = []
            bugs_cnt = 0
            prom_hrs = None

        tabla_historico.append({
            "Épica": nombre_epica,
            "Mes entrega": mes_entrega,
            "%_num": porcentaje_num,
            "Historias": historias,
            "Puntos totales": puntos_totales,
            # Nuevos campos
            "Bugs_asociados": bugs_cnt,
            "Bugs_asociados_claves": ", ".join(uniq_bugs),
            "Bugs_total_RN": bugs_cnt,
            "Promedio_resolucion_bugs_hs": prom_hrs,
        })

    tabla_historico = sorted(
        tabla_historico,
        key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"])
    )

    # ------------------ UI ------------------
    st.markdown("## Histórico de RNs postventa")
    for row in tabla_historico:
        nombre = row["Épica"]
        mes = row["Mes entrega"]
        porcentaje = row["%_num"]
        puntos_totales = row["Puntos totales"]
        historias = row["Historias"]

        bugs_cnt = row["Bugs_asociados"]
        prom_hrs = row["Promedio_resolucion_bugs_hs"]
        prom_txt = f"{prom_hrs:.2f} hs" if prom_hrs is not None else "-"

        expander_title = (
            f"{nombre} | Avance: {porcentaje:.1f}% | {mes} | "
            f"Puntos: {puntos_totales} | Bugs: {bugs_cnt} | Prom. resolución: {prom_txt}"
        )
        with st.expander(expander_title, expanded=False):
            # Resumen de bugs del RN
            st.markdown(
                f"**Bugs asociados:** {bugs_cnt} &nbsp;|&nbsp; "
                f"**Promedio resolución:** {prom_txt} &nbsp;|&nbsp; "
                f"**Claves:** {row['Bugs_asociados_claves'] or '-'}"
            )
            st.markdown("---")

            # Lista de historias del RN
            if historias:
                for h in historias:
                    estado = h["Estado"]
                    color_estado = (
                        "#39d353" if estado == "lista para implementar"
                        else "#fa4" if estado == "en desarrollo"
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

#velocidad devs
# === PESTAÑA VELOCIDAD DE DEVS ===
if opcion == "Velocidad de devs":
    import json
    from datetime import datetime, timedelta

    import altair as alt
    import pandas as pd
    import streamlit as st

    # Conexión JIRA (si no existe, no rompe)
    try:
        from jira_conexion import jira  # objeto ya autenticado (usa tus variables de entorno)
    except Exception:
        jira = None

    st.header("Velocidad de devs")

    # ------------------ Utilidades ------------------
    def _norm(s):
        return str(s or "").strip()

    def _mes_start(dt):
        if pd.isna(dt):
            return pd.NaT
        return pd.Timestamp(year=dt.year, month=dt.month, day=1)

    def _mes_label(dt):
        if pd.isna(dt):
            return ""
        return dt.strftime("%B %Y")

    def _proy_ok(project_key: str, sel: str) -> bool:
        v = _norm(project_key)
        if sel == "ATI":
            return v == "ATI"
        if sel == "Postventas":
            return v in ("REP", "TAL")
        return True  # 'Todos'

    # ------------------ Mapeo accountId->nombre ------------------
    with open("data/accountid_to_name.json", "r", encoding="utf-8") as f:
        accountid_to_name = json.load(f)
    name_to_acc = {v: k for k, v in accountid_to_name.items()}
    allowed_names = {_norm(v) for v in accountid_to_name.values()}

    # ------------------ Botón refresh ------------------
    if st.button("Forzar actualización ahora"):
        st.session_state["force_refresh"] = True
    else:
        st.session_state["force_refresh"] = st.session_state.get("force_refresh", False)

    # ------------------ Changelog (defensivo) ------------------
    limite_iso = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    @st.cache_data(show_spinner=True)
    def _traer_issues_con_changelog(_jira, _limite_iso, _force_refresh_flag):
        if _jira is None:
            return [], {"last_update": datetime.now().strftime("%d/%m/%Y %H:%M")}

        def traer_todas(jql, fields, max_results=100):
            issues, start_at = [], 0
            while True:
                endpoint = (
                    f'search?jql={jql}&fields={fields}&expand=changelog'
                    f'&startAt={start_at}&maxResults={max_results}'
                )
                data = _jira._get_json(endpoint)
                batch = data.get("issues", [])
                issues.extend(batch)
                if len(batch) < max_results:
                    break
                start_at += max_results
            return issues

        fields_issues = (
            "key,summary,status,project,issuetype,assignee,customfield_10026,"
            "statuscategorychangedate,parent,issuelinks,created"
        )
        jql = (
            f'(project in (REP, TAL, ATI)) AND issuetype in (Historia, Error) '
            f'AND created >= "{_limite_iso}"'
        )
        issues = traer_todas(jql, fields_issues)
        meta = {"last_update": datetime.now().strftime("%d/%m/%Y %H:%M")}
        return issues, meta

    try:
        issues, meta = _traer_issues_con_changelog(
            jira, limite_iso, st.session_state["force_refresh"]
        )
    except Exception:
        issues, meta = [], {"last_update": datetime.now().strftime("%d/%m/%Y %H:%M")}

    st.info(f"📅 Última actualización: {meta.get('last_update', 'desconocida')}")

    # ------------------ Cards de OBJETIVOS con explicación ------------------
    OBJ = {
        "puntos_mes": 16,
        "hs_por_punto": 8,
        "bugs_max": 0,
        "bugs_extra_min": 10,
        "horas_mes": 128,
    }
    PESOS = {"puntos": 0.40, "horas": 0.25, "velocidad": 0.25, "bugs": 0.10}
    BONUS_MAX = 0.05

    RUBRICAS = {
        "puntos": """
**Regla de puntos (mensual):**
- ≥ 20 puntos → **105%**
- 17–19 → **102%**
- **16** → **100%**
- 13–15 → **90%**
- 10–12 → **80%**
- < 10 → **70%**
""",
        "horas": """
**Regla de horas (mensual):**
- ≥ **128 hs** → **100%**
- 100–127 hs → **95%**
- < 100 hs → **70%**
""",
        "velocidad": """
**Velocidad (hs por punto, menor es mejor):**
- ≤ **5** → **110%** · 6–7 → **105%**
- **8** → **100%**
- 8–10 → **95%** · 10–12 → **90%** · >12 → **80%**
""",
        "bugs": """
**Bugs (por mes):**
- **0** → **100%** · 1–3 → **95%**
- 4–5 → **90%** · ≥6 → **80%**
""",
        "bonus": """
**Bono por bugs extra resueltos:**
- 1–5 → **+2%** · 6–10 → **+3%** · >10 → **+5%**
""",
    }

    def _popover(title: str):
        try:
            return st.popover(title, use_container_width=True)
        except Exception:
            return st.expander(title, expanded=False)

    def _card_objetivo(texto: str, color_hex: str, peso: float | None, rubrica_md: str, key: str):
        st.markdown(
            f"""
            <div style="
                background:{color_hex};
                padding:14px 18px;
                border-radius:12px;
                text-align:center;
                font-weight:700;
                color:#fff;
                box-shadow:0 2px 8px rgba(0,0,0,0.12);
                ">
                {texto}
            </div>
            """,
            unsafe_allow_html=True,
        )
        with _popover("¿Cómo se calcula?"):
            if peso is not None:
                st.markdown(f"**Pesa {int(peso*100)}% de la nota final.**")
            else:
                st.markdown(f"**Bono adicional hasta +{int(BONUS_MAX*100)}%** sobre la nota.")
            st.markdown(rubrica_md)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card_objetivo(f"{OBJ['puntos_mes']} puntos / mes", "#1976d2",
                       PESOS["puntos"], RUBRICAS["puntos"], key="card_puntos")
    with c2:
        _card_objetivo(f"{OBJ['hs_por_punto']} hs por punto", "#fb8c00",
                       PESOS["velocidad"], RUBRICAS["velocidad"], key="card_vel")
    with c3:
        _card_objetivo(f"{OBJ['bugs_max']} bugs", "#2e7d32",
                       PESOS["bugs"], RUBRICAS["bugs"], key="card_bugs")
    with c4:
        _card_objetivo(f"Mínimo {OBJ['bugs_extra_min']} bugs extra", "#c62828",
                       None, RUBRICAS["bonus"], key="card_bonus")
    with c5:
        _card_objetivo(f"{OBJ['horas_mes']} hs / mes", "#7e57c2",
                       PESOS["horas"], RUBRICAS["horas"], key="card_horas")

    # ==========================
    #   Filtros de UI
    # ==========================
    col_proj, col_user = st.columns(2)
    with col_proj:
        proyecto_sel = st.selectbox(
            "Seleccioná proyecto", ["Todos", "ATI", "Postventas"], key="vel_proyecto"
        )

    # ------------------ HORAS (CSV histórico) ------------------
    df_horas = pd.read_csv("data/horas_historicas.csv")
    df_horas["Usuario"] = df_horas["Usuario"].astype(str)
    df_horas["Usuario_nombre"] = (
        df_horas["Usuario"].map(accountid_to_name).fillna(df_horas["Usuario"])
    ).apply(_norm)

    if "Fecha" in df_horas.columns:
        df_horas["Fecha"] = pd.to_datetime(df_horas["Fecha"], errors="coerce")
        df_horas["Mes_dt"] = df_horas["Fecha"].apply(lambda d: _mes_start(d) if pd.notna(d) else pd.NaT)
    else:
        df_horas["Mes_dt"] = pd.NaT
    df_horas["Mes"] = df_horas["Mes_dt"].dt.strftime("%B %Y")

    # Sumas de horas (globales) + por proyecto cuando existan
    df_horas_sum_total = (
        df_horas.dropna(subset=["Mes_dt"])
        .groupby(["Usuario_nombre", "Mes_dt"], as_index=False)
        .agg(Horas=("Horas", "sum"))
    )
    df_horas_sum_total["Mes"] = df_horas_sum_total["Mes_dt"].dt.strftime("%B %Y")

    df_horas_sum_proj = pd.DataFrame(columns=["Usuario_nombre", "Mes_dt", "Horas", "Mes"])
    if "Proyecto" in df_horas.columns and proyecto_sel != "Todos":
        df_horas_proj = df_horas[df_horas["Proyecto"].apply(lambda v: _proy_ok(v, proyecto_sel))]
        if not df_horas_proj.empty:
            df_horas_sum_proj = (
                df_horas_proj.dropna(subset=["Mes_dt"])
                .groupby(["Usuario_nombre", "Mes_dt"], as_index=False)
                .agg(Horas=("Horas", "sum"))
            )
            df_horas_sum_proj["Mes"] = df_horas_sum_proj["Mes_dt"].dt.strftime("%B %Y")

    usar_horas_por_proyecto = (proyecto_sel != "Todos") and (not df_horas_sum_proj.empty)
    df_horas_sum = df_horas_sum_proj if usar_horas_por_proyecto else df_horas_sum_total
    if proyecto_sel != "Todos" and not usar_horas_por_proyecto:
        st.caption("ℹ️ No hay horas por proyecto en el CSV (o columna 'Proyecto' inexistente). La **velocidad** se calcula con horas **globales**.")

    # ------------------ Dueño de HU en 1ª vez "En testing" ------------------
    hu_owner_name = {}
    hu_owner_id   = {}

    def _owner_al_momento_testing(iss):
        f = iss.get("fields", {}) or {}
        current_id = (f.get("assignee") or {}).get("accountId")
        current_name = _norm(accountid_to_name.get(current_id) or (f.get("assignee") or {}).get("displayName"))
        histories = (iss.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))
        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            for it in hist.get("items", []) or []:
                if _norm(it.get("field")).lower() == "assignee":
                    new_id = it.get("to")
                    new_name = _norm(it.get("toString"))
                    if new_id:
                        current_id = new_id
                        current_name = _norm(accountid_to_name.get(new_id) or new_name)
                    else:
                        infer_id = name_to_acc.get(new_name)
                        if infer_id:
                            current_id = infer_id
                        current_name = new_name or current_name
            for it in hist.get("items", []) or []:
                if _norm(it.get("field")).lower() == "status" and _norm(it.get("toString")).lower() == "en testing":
                    if pd.notna(h_created):
                        return current_name, current_id, h_created
        return None, None, None

    # Issues (puntos) filtrando por proyecto
    rows_issues = []
    for iss in issues:
        f = iss.get("fields", {}) or {}
        itype = _norm((f.get("issuetype", {}) or {}).get("name")).lower()
        if itype != "historia":
            continue
        proj_key = _norm((f.get("project") or {}).get("key"))
        if not _proy_ok(proj_key, proyecto_sel):
            continue
        key = iss.get("key", "")
        pts = f.get("customfield_10026", 0) or 0
        try:
            pts = float(pts)
        except Exception:
            pts = 0.0
        owner_name, owner_id, first_dt = _owner_al_momento_testing(iss)
        if pd.notna(first_dt) and pts > 0 and owner_name and owner_id:
            hu_owner_name[key] = owner_name
            hu_owner_id[key]   = owner_id
            rows_issues.append(
                {
                    "Issue": key,
                    "Puntos": pts,
                    "Usuario_nombre": owner_name,
                    "Mes": _mes_label(_mes_start(first_dt)),
                    "Proyecto": proj_key,
                }
            )

    df_issues = pd.DataFrame(
        rows_issues, columns=["Issue", "Puntos", "Usuario_nombre", "Mes", "Proyecto"]
    )

    # ------------------ BUGS (regla + filtro proyecto) ------------------
    bug_rows = []
    bugs_extra_rows = []

    hus_validas = set(df_issues["Issue"].unique())

    for iss in issues:
        f = iss.get("fields", {}) or {}
        itype = _norm((f.get("issuetype", {}) or {}).get("name")).lower()
        if itype != "error":
            continue

        bug_key = iss.get("key", "")
        bug_proj = _norm((f.get("project") or {}).get("key"))

        bug_created = pd.to_datetime(f.get("created"), errors="coerce")
        bug_mes_creacion = _mes_label(_mes_start(bug_created)) if pd.notna(bug_created) else None

        estado_bug = _norm((f.get("status", {}) or {}).get("name")).lower()
        fecha_cierre = pd.to_datetime(f.get("statuscategorychangedate", ""), errors="coerce")
        bug_mes_cierre = _mes_label(_mes_start(fecha_cierre)) if pd.notna(fecha_cierre) else None

        assg = f.get("assignee") or {}
        bug_assignee_id = assg.get("accountId")
        bug_assignee_nm = _norm(accountid_to_name.get(bug_assignee_id) or assg.get("displayName"))

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

        hu_duenio_acc = None
        hu_duenio_vis = None
        hu_link_valida = None
        for hu in candidate_hus:
            if hu in hus_validas:
                hu_duenio_acc = hu_owner_id.get(hu)
                hu_duenio_vis = hu_owner_name.get(hu)
                hu_link_valida = hu
                break

        if bug_mes_creacion and hu_duenio_vis and (hu_link_valida in hus_validas):
            bug_rows.append((hu_duenio_vis, bug_mes_creacion, bug_key))

        if (
            bug_assignee_nm
            and bug_mes_cierre
            and estado_bug in ("hecha", "resuelto", "resuelta", "done")
            and (hu_duenio_acc is None or hu_duenio_acc != bug_assignee_id)
            and _proy_ok(bug_proj, proyecto_sel)
        ):
            bugs_extra_rows.append((bug_assignee_nm, bug_mes_cierre, bug_key))

    if bug_rows:
        df_bugs_mes = pd.DataFrame(bug_rows, columns=["Usuario_nombre", "Mes", "Bug_key"])
        df_bugs_mes = (
            df_bugs_mes.groupby(["Usuario_nombre", "Mes"], as_index=False)
            .agg(
                Bug_cnt=("Bug_key", "nunique"),
                Bugs_claves=("Bug_key", lambda x: ", ".join(sorted(set(x)))),
            )
        )
    else:
        df_bugs_mes = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Bug_cnt", "Bugs_claves"])

    if bugs_extra_rows:
        df_bugs_extra = pd.DataFrame(bugs_extra_rows, columns=["Usuario_nombre", "Mes", "Bug_key"])
        df_bugs_extra = (
            df_bugs_extra.groupby(["Usuario_nombre", "Mes"], as_index=False)
            .agg(
                Bugs_resueltos_extra=("Bug_key", "nunique"),
                Bugs_extra_claves=("Bug_key", lambda x: ", ".join(sorted(set(x)))),
            )
        )
    else:
        df_bugs_extra = pd.DataFrame(
            columns=["Usuario_nombre", "Mes", "Bugs_resueltos_extra", "Bugs_extra_claves"]
        )

    # ------------------ Puntos por usuario/mes ------------------
    if not df_issues.empty:
        df_puntos = (
            df_issues.groupby(["Usuario_nombre", "Mes"], as_index=False)
            .agg(
                Puntos=("Puntos", "sum"),
                Claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        )
    else:
        df_puntos = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Puntos", "Claves"])

    # ------------------ BASE unificada y merges ------------------
    df_puntos["_Mes_dt_aux"] = pd.to_datetime(df_puntos["Mes"], format="%B %Y", errors="coerce")
    base_horas = df_horas_sum[["Usuario_nombre", "Mes_dt"]].drop_duplicates() if "Mes_dt" in df_horas_sum.columns else pd.DataFrame(columns=["Usuario_nombre","Mes_dt"])
    base_puntos = df_puntos[["Usuario_nombre", "_Mes_dt_aux"]].rename(columns={"_Mes_dt_aux":"Mes_dt"}).drop_duplicates()
    df_base = pd.concat([base_horas, base_puntos], ignore_index=True).dropna(subset=["Mes_dt"]).drop_duplicates()
    df_base["Mes"] = df_base["Mes_dt"].dt.strftime("%B %Y")

    df_merge = df_base.merge(df_horas_sum[["Usuario_nombre","Mes_dt","Horas"]], on=["Usuario_nombre","Mes_dt"], how="left")
    df_merge = df_merge.merge(df_puntos[["Usuario_nombre","Mes","Puntos","Claves"]], on=["Usuario_nombre","Mes"], how="left")

    if not df_bugs_mes.empty:
        df_merge = df_merge.merge(
            df_bugs_mes.rename(columns={"Bug_cnt": "Bugs"}),
            on=["Usuario_nombre", "Mes"],
            how="left",
        )
    if not df_bugs_extra.empty:
        df_merge = df_merge.merge(df_bugs_extra, on=["Usuario_nombre", "Mes"], how="left")

    for col, fill in [("Horas", 0.0), ("Puntos", 0.0), ("Bugs", 0), ("Bugs_resueltos_extra", 0)]:
        if col in df_merge.columns:
            df_merge[col] = df_merge[col].fillna(fill)
    for col in ["Claves", "Bugs_claves", "Bugs_extra_claves"]:
        if col in df_merge.columns:
            df_merge[col] = df_merge[col].fillna("").astype(str)

    df_merge["Velocidad"] = df_merge.apply(
        lambda r: round(r["Horas"] / r["Puntos"], 4) if r["Puntos"] > 0 else 0, axis=1
    )

    def calcular_nota_final(r):
        p = float(r.get("Puntos", 0.0))
        h = float(r.get("Horas", 0.0))
        b = int(r.get("Bugs", 0))
        v = float(r.get("Velocidad", 0.0))
        bex = int(r.get("Bugs_resueltos_extra", 0))

        if p >= 20: sp = 1.05
        elif 17 <= p <= 19: sp = 1.02
        elif p == 16: sp = 1.00
        elif 13 <= p <= 15: sp = 0.90
        elif 10 <= p <= 12: sp = 0.80
        else: sp = 0.70

        if h >= 128: sh = 1.00
        elif 100 <= h <= 127: sh = 0.95
        else: sh = 0.70

        if b == 0: sb = 1.00
        elif 1 <= b <= 3: sb = 0.95
        elif 4 <= b <= 5: sb = 0.90
        else: sb = 0.80

        if v <= 5: sv = 1.10
        elif 6 <= v <= 7: sv = 1.05
        elif abs(v - 8.0) < 1e-9: sv = 1.00
        elif 8 < v <= 10: sv = 0.95
        elif 10 < v <= 12: sv = 0.90
        else: sv = 0.80

        base = (sp * 0.40) + (sh * 0.25) + (sv * 0.25) + (sb * 0.10)

        if 1 <= bex <= 5: bonus = 0.02
        elif 6 <= bex <= 10: bonus = 0.03
        elif bex > 10: bonus = 0.05
        else: bonus = 0.0

        return round((base + bonus) * 100, 2)

    if not df_merge.empty:
        df_merge["Nota_final"] = df_merge.apply(calcular_nota_final, axis=1)
    else:
        df_merge["Nota_final"] = pd.Series(dtype=float)

    df_merge["Mes_dt"] = pd.to_datetime(df_merge["Mes_dt"], errors="coerce")
    fecha_limite6 = pd.Timestamp.today().normalize() - pd.DateOffset(months=6)
    df_ult6 = df_merge[df_merge["Mes_dt"] >= _mes_start(fecha_limite6)].copy()

    # ==========================
    #   Selector de usuario
    # ==========================
    df_ult6["Usuario_nombre"] = df_ult6["Usuario_nombre"].apply(_norm)
    users_with_points = set(
        df_ult6.loc[df_ult6["Puntos"] > 0, "Usuario_nombre"].dropna().astype(str)
    )
    usuarios_validos = sorted(list(allowed_names & users_with_points))

    with col_user:
        usuario_sel = st.selectbox(
            "Seleccioná usuario", ["Todos"] + usuarios_validos, key="vel_usuario"
        )

    # ==========================
    #   Ranking (últimos 6 meses)
    # ==========================
    df_rank_src = df_ult6[df_ult6["Usuario_nombre"].isin(usuarios_validos)].copy()
    st.subheader("Ranking de devs (últimos 6 meses)")
    if df_rank_src.empty:
        st.info("No hay usuarios con puntos en los últimos 6 meses.")
        df_ranking = pd.DataFrame(
            columns=[
                "Usuario_nombre",
                "Promedio_puntos",
                "Promedio_velocidad",
                "Promedio_bugs",
                "Promedio_bugs_extra",
                "Nota_final",
            ]
        )
    else:
        df_ranking = (
            df_rank_src.groupby("Usuario_nombre", as_index=False)
            .agg(
                Promedio_puntos=("Puntos", "mean"),
                Promedio_velocidad=("Velocidad", "mean"),
                Promedio_bugs=("Bugs", "mean"),
                Promedio_bugs_extra=("Bugs_resueltos_extra", "mean"),
                Nota_final=("Nota_final", "mean"),
            )
            .sort_values("Nota_final", ascending=False)
            .reset_index(drop=True)
        )

    if usuario_sel != "Todos":
        df_ranking = df_ranking[df_ranking["Usuario_nombre"] == usuario_sel]

    st.dataframe(df_ranking, use_container_width=True, hide_index=True)

    # ==========================
    #   Gráficos
    # ==========================
    if usuario_sel == "Todos":
        if not df_rank_src.empty:
            chart_data = (
                df_rank_src.groupby("Usuario_nombre", as_index=False)
                .agg(Velocidad_promedio=("Velocidad", "mean"))
            )
            ch = (
                alt.Chart(chart_data)
                .mark_bar()
                .encode(
                    x=alt.X("Usuario_nombre:N", sort="-y", title="Usuario", axis=alt.Axis(labelAngle=-40)),
                    y=alt.Y("Velocidad_promedio:Q", title="Velocidad promedio"),
                    tooltip=["Usuario_nombre", alt.Tooltip("Velocidad_promedio:Q", format=".2f")],
                )
                .properties(height=280)
            )
            st.altair_chart(ch, use_container_width=True)
    else:
        # Historial del usuario (UN registro por mes) + gráfico de **Velocidad** con línea objetivo roja
        df_user = df_ult6[df_ult6["Usuario_nombre"] == usuario_sel].copy()
        if not df_user.empty:
            def _combinar_claves(series):
                vals = [str(v) for v in series.dropna() if str(v).strip()]
                if not vals:
                    return ""
                planos = ", ".join(vals).split(",")
                planos = [v.strip() for v in planos if v.strip()]
                return ", ".join(sorted(set(planos)))

            df_user = (
                df_user.groupby(["Usuario_nombre", "Mes", "Mes_dt"], as_index=False)
                .agg(
                    Horas=("Horas", "sum"),
                    Puntos=("Puntos", "sum"),
                    Claves=("Claves", _combinar_claves),
                    Velocidad=("Velocidad", "mean"),
                    Bugs=("Bugs", "sum"),
                    Bugs_claves=("Bugs_claves", _combinar_claves),
                    Bugs_resueltos_extra=("Bugs_resueltos_extra", "sum"),
                    Bugs_extra_claves=("Bugs_extra_claves", _combinar_claves),
                    Nota_final=("Nota_final", "mean"),
                )
                .sort_values("Mes_dt")
            )

            st.subheader(f"Historial de {usuario_sel}")
            st.dataframe(
                df_user[
                    [
                        "Usuario_nombre",
                        "Mes",
                        "Horas",
                        "Puntos",
                        "Claves",
                        "Velocidad",
                        "Bugs",
                        "Bugs_claves",
                        "Bugs_resueltos_extra",
                        "Bugs_extra_claves",
                        "Nota_final",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

            # -------- Gráfico: Velocidad por mes (único por mes) + línea objetivo --------
            df_user_plot = (
                df_user[["Mes_dt", "Velocidad"]]
                .dropna()
                .groupby("Mes_dt", as_index=False)
                .agg(Velocidad=("Velocidad", "mean"))
                .sort_values("Mes_dt")
            )
            df_user_plot["Mes_lbl"] = df_user_plot["Mes_dt"].dt.strftime("%b %Y")

            linea_usuario = (
                alt.Chart(df_user_plot)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Mes_dt:T", title="Mes", axis=alt.Axis(format="%b %Y")),
                    y=alt.Y("Velocidad:Q", title="Velocidad (hs/punto)"),
                    tooltip=[
                        alt.Tooltip("Mes_lbl:N", title="Mes"),
                        alt.Tooltip("Velocidad:Q", format=".2f", title="Velocidad"),
                    ],
                )
            )

            linea_objetivo = (
                alt.Chart(pd.DataFrame({"y": [OBJ["hs_por_punto"]]}))
                .mark_rule(color="red", strokeWidth=2)
                .encode(y="y:Q")
            )

            ch_u = (linea_usuario + linea_objetivo).properties(height=260)
            st.altair_chart(ch_u, use_container_width=True)
        else:
            st.info("No hay datos del usuario en los últimos 6 meses.")


#GANTT
# === PESTAÑA GANTT (CSV de Google Sheets) ===
if opcion == "Gantt":
    import pandas as pd
    import plotly.express as px
    from datetime import datetime

    # --- URLs de los CSV ---
    link_postventas = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTRvUazuzfWjGl5VWuZJUJslZEf-PpYyHZ_5G2SXwPtu16R71mPSKVQTYjen9UBwQ/pub?gid=865145678&single=true&output=csv"
    link_ati        = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6s9qMzmA_sJRko5EDggumO4sybGVq3n-uOmZOMj8CJDnHo9AWZeZOXZGz7cTg4XoqeiPDIgQP3QER/pub?output=csv"
    link_afupost    = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR3rrcWGJWtEbowD_8bJ35lbziZ208DFGdo1JkHKhMvRK9SBjxxlTolXjeoKVMu4v447yfgQn0tUjsT/pub?output=csv"
    link_afuati     = "https://docs.google.com/spreadsheets/d/e/2PACX-1vThHnFUDJm9AlT-rODLiPhLSTqH1O12_yz0Z_0SJJ3EAtS84GH6lptWpr2eSMPuyv50ShS3ysozwsKe/pub?output=csv"

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

    def cargar_datos_gantt(link: str, tipo: str = "postventas") -> pd.DataFrame:
        df = pd.read_csv(link)
        # Normalizar headers y tipos
        df.columns = df.columns.str.strip().str.lower()
        df['rn'] = df['rn'].astype(str).str.strip()

        # Parseo de fechas (acepta dd/mm/aaaa)
        for col in ['inicio', 'fin']:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['inicio', 'fin'])

        # Mes de entrega
        if 'mes' in df.columns:
            df['mes de entrega'] = df['mes']
        else:
            df['mes de entrega'] = df['fin'].dt.to_period('M').astype(str)

        # Truncar RN para el eje Y
        df['rn_trunc'] = df['rn'].apply(lambda x: x if len(x) <= 30 else x[:27] + '...')

        # Columna opcional
        if 'afu asignado' not in df.columns:
            df['afu asignado'] = 'Sin asignar'

        # Normalizar 'estado' (por si hay mayúsculas/acentos/espacios)
        if 'estado' in df.columns:
            df['estado'] = df['estado'].astype(str).str.strip()

        return df

    st.markdown("## Gantt - SUMMA")
    gantt_proyecto = st.radio(
        "Seleccioná el Gantt que querés ver:",
        ("Desarrollo Postventas", "Desarrollo ATI", "AFUs Postventas", "AFUs ATI"),
        horizontal=True,
        key="gantt_proyecto_main"
    )

    # Selección de dataset y filtros disponibles
    if gantt_proyecto == "Desarrollo Postventas":
        df_gantt = cargar_datos_gantt(link_postventas, tipo="postventas")
        filtros = ['mes de entrega', 'estado']
    elif gantt_proyecto == "Desarrollo ATI":
        df_gantt = cargar_datos_gantt(link_ati, tipo="ati")
        filtros = ['mes de entrega', 'estado']
    elif gantt_proyecto == "AFUs Postventas":
        df_gantt = cargar_datos_gantt(link_afupost, tipo="afupost")
        filtros = ['mes de entrega', 'estado', 'afu asignado']
    else:  # "AFUs ATI"
        df_gantt = cargar_datos_gantt(link_afuati, tipo="afuati")
        filtros = ['mes de entrega', 'estado', 'afu asignado']

    # Filtros dinámicos
    cols = st.columns(len(filtros))
    filtros_seleccionados = {}
    for i, filtro in enumerate(filtros):
        opciones = ['Todos'] + sorted([o for o in df_gantt[filtro].dropna().unique()])
        filtros_seleccionados[filtro] = cols[i].selectbox(
            filtro.replace("_", " ").title(),
            opciones,
            key=f"gantt_{gantt_proyecto}_{filtro}"
        )

    # Aplicar filtros
    df_filtrado = df_gantt.copy()
    for filtro, valor in filtros_seleccionados.items():
        if valor != 'Todos':
            df_filtrado = df_filtrado[df_filtrado[filtro] == valor]

    # Orden visual
    df_filtrado = df_filtrado.sort_values('inicio', ascending=True)
    df_filtrado['rn_trunc'] = pd.Categorical(
        df_filtrado['rn_trunc'],
        categories=df_filtrado['rn_trunc'].unique(),
        ordered=True
    )

    # Render
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
