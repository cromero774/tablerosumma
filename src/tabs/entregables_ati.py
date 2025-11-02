"""
Pestaña Entregables ATI - Tablero SUMMA
Implementa la lógica completa de los entregables ATI
"""

import streamlit as st
import pandas as pd
import unicodedata
import re
from datetime import datetime, timedelta
from src.utils.configuracion import cargar_epicas_relevantes
from src.utils.database_helper import DatabaseHelper

def mostrar_entregables_ati(epicas_relevantes, issues_jira):
    """Mostrar la pestaña de Entregables ATI"""
    
    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    EPIC_LINK_CAMPO = "customfield_10016"

    def _safe_issue_key(iss) -> str:
        return (iss.get("key") or iss.get("id") or "") if isinstance(iss, dict) else ""

    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    # Filtrar épicas de ATI
    epicas_ati = [e for e in epicas_relevantes if e["rn"].startswith("ATI-")]
    meses_entrega = sorted({epica["mes_entrega"] for epica in epicas_ati}, key=lambda m: meses_orden.index(m))

    # ---- Filtros en columnas ----
    cols = st.columns([1, 1])
    with cols[0]:
        proyecto_seleccionado = st.selectbox("Filtrar por proyecto", ["Todos", "ATI"], key="ati_proyecto")
    with cols[1]:
        mes_seleccionado = st.selectbox("Filtrar por mes de entrega", ["Todos"] + meses_entrega, key="ati_mes")

    # Cargar historias desde la base de datos
    db = DatabaseHelper()
    db.conectar()
    
    if proyecto_seleccionado == "Todos" or proyecto_seleccionado == "ATI":
        historias_db = db.obtener_historias_con_transiciones(["ATI"], fecha_desde='2020-01-01', incluir_sin_puntos=True)  # Jira-like dicts
    else:
        historias_db = []
    
    db.cerrar()
    
    issues = historias_db

    # Eliminar duplicados
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())
    
    # Mapeo auxiliar desde clave de épica (ATI-xxx) a nombre de RN
    epicas_relevantes_all = cargar_epicas_relevantes()
    epic_key_to_name = {e.get("rn", ""): e.get("nombre", "") for e in epicas_relevantes_all}

    # Filtrar épicas relevantes (solo ATI)
    if mes_seleccionado != "Todos":
        epicas_relevantes_filtradas = [e for e in epicas_ati if e["mes_entrega"] == mes_seleccionado]
    else:
        epicas_relevantes_filtradas = epicas_ati

    nombres_relevantes = [normalize(epica["nombre"]) for epica in epicas_relevantes_filtradas]
    rns_relevantes = [normalize(epica["rn"]) for epica in epicas_relevantes_filtradas]
    
    # Crear mapeo RN -> nombre épica para todas las épicas relevantes
    rn_to_nombre_epica = {e.get("rn", ""): e.get("nombre", "") for e in epicas_relevantes_filtradas}

    # Agrupación por épica - PRIMERO por parent_key (RN), luego mapeamos al nombre
    epicas = {}  # {nombre_epica: {"Historias": [...]}}
    for issue in issues:
        f = issue.get("fields", {}) or {}
        issue_key = issue.get("key", "")
        # Buscar epic_name
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
            ep_ref = f.get(EPIC_LINK_CAMPO)
            if isinstance(ep_ref, dict):
                # Algunos tableros guardan {key: ATI-123, name: \n}
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
        # Si tenemos parent_key (RN), usar ese para agrupar (más confiable que el nombre)
        rn_key_encontrado = None
        if parent_key and normalize(parent_key) in rns_relevantes:
            rn_key_encontrado = parent_key
            # Si encontramos RN, usar el nombre de épica del mapeo
            if parent_key in rn_to_nombre_epica:
                epic_name = rn_to_nombre_epica[parent_key]
        
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            # Si tenemos RN pero no nombre, intentar con el nombre del mapeo
            if rn_key_encontrado and rn_key_encontrado in rn_to_nombre_epica:
                epic_name = rn_to_nombre_epica[rn_key_encontrado]
            else:
                epic_name = "Sin epica"

        # Filtrar: solo incluir si el nombre coincide O si el RN coincide
        if not (normalize(epic_name) in nombres_relevantes or (rn_key_encontrado and normalize(rn_key_encontrado) in rns_relevantes)):
            continue

        puntos = f.get("customfield_10026") or f.get("story_points") or 0
        try:
            puntos = float(puntos)
        except (TypeError, ValueError):
            puntos = 0

        summary = f.get("summary", "")
        if "madre" in (summary or "").lower():
            continue

        estado = ((f.get("status") or {}).get("name") or "").strip().lower()
        asignado = ((f.get("assignee") or {}).get("displayName") or "") if f.get("assignee") else ""
        key = issue.get("key", "")
        fecha_estado = f.get("statuscategorychangedate") or f.get("updated") or ""
        duedate = f.get("duedate") or ""

        # Si encontramos RN, asegurarnos de usar el nombre correcto de la épica
        if rn_key_encontrado and rn_key_encontrado in rn_to_nombre_epica:
            epic_name_final = rn_to_nombre_epica[rn_key_encontrado]
        else:
            epic_name_final = epic_name

        if epic_name_final not in epicas:
            epicas[epic_name_final] = {
                "Historias": [],
                "Mes de entrega": None
            }
        epicas[epic_name_final]["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos
        })

    # ---- Resumen para tabla de prioridades ----
    # Construir mapeo inverso: clave RN -> nombre épica para fallback
    rn_to_nombre = {e.get("rn", ""): e.get("nombre", "") for e in epicas_relevantes_filtradas}
    
    tabla_prioridad = []
    for epica_rn in epicas_relevantes_filtradas:
        nombre_epica = epica_rn.get("nombre", "")
        rn_key = epica_rn.get("rn", "")
        mes_entrega = epica_rn.get("mes_entrega", "")
        # Intentar match por nombre primero
        epic_match = next((epic for epic in epicas if normalize(nombre_epica) == normalize(epic)), None)
        # Si no hay match, intentar por clave RN
        if not epic_match and rn_key:
            # Buscar épicas que tengan historias con parent_key igual a rn_key
            for epic_name, epic_data in epicas.items():
                historias_epic = epic_data.get("Historias", [])
                # Verificar si alguna historia tiene parent_key igual a rn_key
                for h in historias_epic:
                    issue_key = h.get("Clave", "")
                    # Buscar el issue original para obtener parent_key
                    for issue in issues:
                        if issue.get("key") == issue_key:
                            f = issue.get("fields", {}) or {}
                            parent = f.get("parent")
                            if parent:
                                parent_key = (parent.get("key") or (parent.get("fields") or {}).get("key"))
                                if parent_key and normalize(parent_key) == normalize(rn_key):
                                    epic_match = epic_name
                                    break
                    if epic_match:
                        break
                if epic_match:
                    break
        
        if epic_match:
            data = epicas[epic_match]
            historias = data["Historias"]
            total = len(historias)
            
            # Normalizar estados para comparación robusta
            listas_para_implementar = sum(1 for h in historias if normalize(h["Estado"]) == normalize("lista para implementar"))
            pendientes = sum(
                1 for h in historias 
                if normalize(h["Estado"]) == normalize("lista para desarrollar") and not h["Asignado"]
            )
            estados_en_proceso = [
                "en desarrollo", "en testing", "en corrección", "por corregir",
                "requiere validación", "en análisis", "sin refinar", "pausada",
                "en correccion"  # variante sin tilde
            ]
            estados_en_proceso_normalizados = [normalize(e) for e in estados_en_proceso]
            en_proceso = sum(
                1 for h in historias 
                if normalize(h["Estado"]) in estados_en_proceso_normalizados
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
            match = re.search(r'(\d+\.?\d*)', str(avance_str))
            return float(match.group(1)) if match else 0.0
        
        def extraer_porcentaje_proceso(proceso_str):
            """Extrae el número del string de proceso que puede contener emojis"""
            if pd.isna(proceso_str):
                return 0.0
            if isinstance(proceso_str, (int, float)):
                return float(proceso_str)
            # Buscar el primer número en el string
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
            if normalize(h["Estado"]) == normalize("lista para desarrollar") and not h["Asignado"]
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

    # --- Mostrar tabla completas abajo ---
    if tabla_completas:
        df_completas = pd.DataFrame(tabla_completas)
        st.markdown("## Entregas completadas")
        st.dataframe(
            df_completas[["Épica", "Mes entrega", "% Con ok QA", "% En desarrollo", "Q de HU pendientes", "Puntos totales"]],
            hide_index=True,
            use_container_width=True
        )