"""
Pestaña de Entregables Postventas
"""

import streamlit as st
import pandas as pd
import unicodedata
import pickle
import os
from datetime import datetime, timedelta
from src.jira_conexion import get_jira
from src.utils.configuracion import cache_path

def normalize(s):
    """Normalizar texto para comparaciones"""
    if not s:
        return ""
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

def traer_todos_los_issues(jira, jql, fields, max_results=100):
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

def _unwrap_issue(issue):
    """Helper para extraer datos de issue"""
    return issue

def _safe_issue_key(issue):
    """Helper para obtener key segura de issue"""
    try:
        return issue.get("key", "")
    except:
        return ""

def mostrar_entregables_postventas(epicas_relevantes, issues_jira):
    """Mostrar la pestaña de Entregables Postventas"""
    
    # Obtener conexión a Jira
    jira = get_jira()
    
    EPIC_LINK_CAMPO = "customfield_10016"

    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    meses_entrega = sorted({epica["mes_entrega"] for epica in epicas_relevantes}, key=lambda m: meses_orden.index(m))

    # ---- Filtros en columnas ----
    cols = st.columns([1, 1, 1])
    with cols[0]:
        proyecto_seleccionado = st.selectbox("Filtrar por proyecto", ["Todos", "Taller", "Repuestos"])
    with cols[1]:
        mes_seleccionado = st.selectbox("Filtrar por mes de entrega", ["Todos"] + meses_entrega)
    with cols[2]:
        # Botón para forzar actualización
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="entregable_actualizar"):
            # Limpiar todos los caches relacionados con entregable postventa
            cache_keys_to_clear = [
                "entregable_tal_issues",
                "entregable_rep_issues"
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

    fields = "key,summary,status,project,issuetype,assignee,parent,customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated"

    # Cache para issues de TAL y REP en Entregable Postventa
    cache_key_tal_entregable = "entregable_tal_issues"
    cache_key_rep_entregable = "entregable_rep_issues"
    cache_file_tal_entregable = cache_path(cache_key_tal_entregable, 'pkl')
    cache_file_rep_entregable = cache_path(cache_key_rep_entregable, 'pkl')
    
    try:
        if os.path.exists(cache_file_tal_entregable):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_tal_entregable))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_tal_entregable, 'rb') as f:
                    issues_tal = pickle.load(f)
            else:
                progress_bar = st.progress(0)
                issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
                progress_bar.progress(0.5)
                with open(cache_file_tal_entregable, 'wb') as f:
                    pickle.dump(issues_tal, f)
        else:
            progress_bar = st.progress(0)
            issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
            progress_bar.progress(0.5)
            with open(cache_file_tal_entregable, 'wb') as f:
                pickle.dump(issues_tal, f)
    except Exception:
        issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
    
    try:
        if os.path.exists(cache_file_rep_entregable):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_rep_entregable))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_rep_entregable, 'rb') as f:
                    issues_rep = pickle.load(f)
            else:
                issues_rep = traer_todos_los_issues(jira, 'project = REP AND issuetype = Historia', fields)
                progress_bar.progress(1.0)
                with open(cache_file_rep_entregable, 'wb') as f:
                    pickle.dump(issues_rep, f)
        else:
            issues_rep = traer_todos_los_issues(jira, 'project = REP AND issuetype = Historia', fields)
            progress_bar.progress(1.0)
            with open(cache_file_rep_entregable, 'wb') as f:
                pickle.dump(issues_rep, f)
    except Exception:
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
    issues = [_unwrap_issue(iss) for iss in issues]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # Filtrar épicas relevantes (solo postventas: REP y TAL, excluir ATI)
    epicas_postventas = [e for e in epicas_relevantes if e["rn"].startswith(("REP-", "TAL-"))]
    
    if mes_seleccionado != "Todos":
        epicas_relevantes_filtradas = [e for e in epicas_postventas if e["mes_entrega"] == mes_seleccionado]
    else:
        epicas_relevantes_filtradas = epicas_postventas

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
                ]
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
            "% Con ok QA": f"{porcentaje_avance} " + ("🟢" if porcentaje_num == 100 else "🟡" if porcentaje_num >= 50 else "🔴"),
            "% En desarrollo": porcentaje_proceso,
            "Q de HU pendientes": pendientes,
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
        mes_tiene_alerta = any((r["Mes entrega"] == m and r["Q de HU pendientes"] > 0 and r["%_num"] < 100) for r in tabla_incompletas)
        if mes_tiene_alerta:
            alerta_mes = m
            break

    # --- Mostrar tabla incompletas ---
    df_tabla = pd.DataFrame(tabla_incompletas)
    if not df_tabla.empty:
        st.markdown("## Prioridades actuales")
        def gen_alerta(row):
            if row["Mes entrega"] == alerta_mes and row["Q de HU pendientes"] > 0:
                return "⚠️ Entrega próxima con pendientes"
            else:
                return ""
        df_tabla["Alerta"] = df_tabla.apply(gen_alerta, axis=1)
        
        # Calcular %Faltante = 100% - %En proceso - %Avance
        # Extraer números de las columnas que contienen strings con emojis
        def extraer_porcentaje_avance(avance_str):
            """Extrae el número del string de avance que contiene emojis"""
            if pd.isna(avance_str) or not isinstance(avance_str, str):
                return 0.0
            # Buscar el primer número en el string (antes del espacio y emoji)
            import re
            match = re.search(r'(\d+\.?\d*)', str(avance_str))
            return float(match.group(1)) if match else 0.0
        
        def extraer_porcentaje_proceso(proceso_str):
            """Extrae el número del string de proceso que puede contener emojis"""
            if pd.isna(proceso_str):
                return 0.0
            if isinstance(proceso_str, (int, float)):
                return float(proceso_str)
            # Buscar el primer número en el string
            import re
            match = re.search(r'(\d+\.?\d*)', str(proceso_str))
            return float(match.group(1)) if match else 0.0
        
        # Aplicar las funciones de extracción
        avance_numerico = df_tabla["% Con ok QA"].apply(extraer_porcentaje_avance)
        proceso_numerico = df_tabla["% En desarrollo"].apply(extraer_porcentaje_proceso)
        
        # Calcular %Faltante con formato y colores semáforo
        faltante_numerico = (100 - proceso_numerico - avance_numerico).round(1)
        
        # Aplicar colores semáforo: 🔴 >=70%, 🟡 20-70%, 🟢 <20%
        def aplicar_color_semaforo(valor):
            if valor >= 70:
                return f"{valor}% 🔴"
            elif valor >= 20:
                return f"{valor}% 🟡"
            else:
                return f"{valor}% 🟢"
        
        df_tabla["%Faltante"] = faltante_numerico.apply(aplicar_color_semaforo)
        
        st.dataframe(
            df_tabla[["Épica", "Mes entrega", "% Con ok QA", "% En desarrollo", "%Faltante", "Q de HU pendientes", "Puntos totales", "Alerta"]],
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
            df_completas[["Épica", "Mes entrega", "% Con ok QA", "% En desarrollo", "Q de HU pendientes", "Puntos totales", "Fecha de entrega"]],
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
                    f"""\n                    <div style="border-radius:14px; background:{fondo_card}; padding:18px; margin-bottom:16px; box-shadow:0 2px 8px #0001;">\n                        <div style="font-size:1.1em; font-weight:bold; color:#fff; margin-bottom:4px;">\n                            🟡 {h['Clave']} - {h['Nombre']}\n                        </div>\n                        <div>\n                            <b>RN:</b> {h['Epica']}<br>\n                            <b>Mes de entrega:</b> <span style="color:gold;">{h['Mes entrega']}</span>\n                        </div>\n                        <div style="margin-top:8px;">\n                            <span style="font-size:1em; color:#bcbcff; font-weight:bold;">Devs sugeridos:</span> <br>\n                            <span style="font-size:1em; font-weight:bold; color:#9fffca;">{devs_sugeridos}</span>\n                            <br>\n                            <span style="font-size:0.95em; color:#ffd580;">Afinidad: {afinidad}</span>\n                        </div>\n                        <div style="margin-top:6px; color:orange;">\n                            <b>⚠️ Prioridad alta para cumplir con el entregable del mes</b>\n                        </div>\n                    </div>\n                    """,
                    unsafe_allow_html=True
                )
    else:
        st.success("¡No hay historias prioritarias pendientes a tomar para este mes!")