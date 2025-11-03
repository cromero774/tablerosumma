"""
Pestaña BUGS - Tablero SUMMA
Implementa la lógica completa del análisis de bugs
"""

import streamlit as st
import pandas as pd
import unicodedata
import re
import json
import os
import time
import pickle
from datetime import datetime, timedelta, date
from src.jira_conexion import get_jira
from src.utils.configuracion import cache_path, cargar_epicas_relevantes
from src.utils.database_helper import DatabaseHelper

def mostrar_bugs(epicas_relevantes, issues_jira):
    """Mostrar la pestaña de BUGS"""
    
    st.header("🐛 Bugs - Análisis por Mes")
    st.caption("📊 Métricas de bugs del proyecto BUG con clasificación por tipo y épicas")
    
    # Mostrar fecha de última actualización
    db_helper = DatabaseHelper()
    db_helper.conectar()
    fecha_actualizacion = db_helper.obtener_fecha_ultima_actualizacion()
    db_helper.cerrar()
    st.caption(f"🕒 **Última actualización:** {fecha_actualizacion}")

    # ==========================
    # FUNCIONES AUXILIARES
    # ==========================
    
    def _strip(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('ASCII').strip()
    
    def detectar_etiqueta_kinetic_mejora(labels):
        if not labels:
            return None
        labels_str = " ".join(labels).upper()
        if "KINETIC" in labels_str:
            return "KINETIC"
        elif "MEJORA" in labels_str:
            return "MEJORA"
        return None
    
    def es_epica_del_json(epic_key):
        if not epic_key:
            return False
        epicas_relevantes = cargar_epicas_relevantes()
        return epic_key in [epic["rn"] for epic in epicas_relevantes]
    
    def es_bloqueante_por_prioridad(priority):
        if not priority:
            return False
        priority_str = _strip(priority).upper()
        return "MUY ALTA" in priority_str or "HIGHEST" in priority_str or "CRITICAL" in priority_str
    
    def _obtener_nombre_epica(epic_key):
        if not epic_key:
            return "Sin épica"
        epicas_relevantes = cargar_epicas_relevantes()
        for epic in epicas_relevantes:
            if epic["rn"] == epic_key:
                return epic.get("nombre", epic_key)
        return epic_key
    
    def _calcular_tiempos_estado(issue):
        """Calcula tiempos de transiciones de estado para bugs bloqueantes"""
        try:
            changelog = issue.get("changelog", {})
            histories = changelog.get("histories", [])
            if not histories:
                return "N/A", "N/A"

            # Utilidades de normalización
            def _norm_upper_no_accents(s):
                try:
                    return unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('ASCII').upper().strip()
                except Exception:
                    return str(s or "").upper().strip()

            iniciales = {"TO DO", "POR HACER"}
            objetivo_validacion = "EN VALIDACION QA"
            objetivo_aprobado = "APROBADO POR QA"

            # Colecciones de eventos para soportar múltiples ciclos
            salidas_iniciales = []
            entradas_validacion = []
            entradas_aprobado = []

            for history in histories:
                created = pd.to_datetime(history.get("created", ""), errors="coerce")
                if pd.isna(created):
                    continue
                for item in history.get("items", []) or []:
                    if item.get("field") != "status":
                        continue
                    from_status = _norm_upper_no_accents(item.get("fromString", ""))
                    to_status = _norm_upper_no_accents(item.get("toString", ""))

                    # Registrar TODAS las salidas reales de estados iniciales (evitando rebotes entre iniciales)
                    if from_status in iniciales:
                        if not (from_status == "POR HACER" and to_status == "TO DO") and not (from_status == "TO DO" and to_status == "POR HACER"):
                            salidas_iniciales.append(created)

                    # Registrar TODAS las entradas a objetivos QA
                    if to_status == objetivo_validacion:
                        entradas_validacion.append(created)
                    if to_status == objetivo_aprobado:
                        entradas_aprobado.append(created)

            # Días laborables contando el mismo día si es hábil (mismo día = 1 si hábil)
            def calcular_dias_laborables(fecha_inicio, fecha_fin):
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

            # Seleccionar ÚLTIMO ciclo válido: última entrada y su salida previa más cercana
            salida_para_validacion = None
            entrada_validacion = max(entradas_validacion) if entradas_validacion else None
            if entrada_validacion and salidas_iniciales:
                salida_para_validacion = max([s for s in salidas_iniciales if s <= entrada_validacion], default=None)

            salida_para_aprobado = None
            entrada_aprobado = max(entradas_aprobado) if entradas_aprobado else None
            if entrada_aprobado and salidas_iniciales:
                salida_para_aprobado = max([s for s in salidas_iniciales if s <= entrada_aprobado], default=None)

            # 1) To Do -> EN VALIDACION QA (último ciclo)
            if salida_para_validacion and entrada_validacion:
                d1 = calcular_dias_laborables(salida_para_validacion, entrada_validacion)
                res1 = f"{d1}d" if d1 > 0 else "N/A"
            else:
                res1 = "N/A"

            # 2) To Do -> APROBADO POR QA (último ciclo)
            if salida_para_aprobado and entrada_aprobado:
                d2 = calcular_dias_laborables(salida_para_aprobado, entrada_aprobado)
                res2 = f"{d2}d" if d2 > 0 else "N/A"
            else:
                res2 = "N/A"

            return res1, res2
        except Exception:
            return "N/A", "N/A"

    # ==========================
    # CARGA DE DATOS
    # ==========================
    
    # Cargar épicas relevantes
    try:
        epicas_relevantes = cargar_epicas_relevantes()
    except Exception as e:
        st.error(f"❌ No se pudo cargar el archivo epicas_relevantes.json: {e}")
        st.stop()
    
    # Cargar bugs desde la base de datos
    db = DatabaseHelper()
    db.conectar()
    issues = db.obtener_bugs_proyecto_bug()
    db.cerrar()
    
    if not issues:
        st.warning("⚠️ No se encontraron bugs")
        st.stop()
    
    st.success(f"✅ Cargados {len(issues)} bugs desde la base de datos")
    
    # ==========================
    # PROCESAMIENTO DE DATOS
    # ==========================
    
    rows = []
    for issue in issues:
        f = issue.get("fields", {}) or {}
        
        # Verificar que sea un bug
        issue_type = (f.get("issuetype", {}) or {}).get("name", "").lower()
        if issue_type != "error":
            continue
        
        # Datos básicos
        key = issue.get("key", "")
        created = f.get("created", "")
        priority = (f.get("priority", {}) or {}).get("name", "")
        summary = f.get("summary", "")
        status = (f.get("status", {}) or {}).get("name", "")
        labels = f.get("labels", [])
        
        # Obtener épica
        parent = f.get("parent", {}) or {}
        epic_key = parent.get("key", "")
        if not epic_key:
            epic_key = f.get("customfield_10016", "")
        
        # Clasificaciones
        tipo_etiqueta = detectar_etiqueta_kinetic_mejora(labels)
        es_epica_json = es_epica_del_json(epic_key)
        es_bloqueante = es_bloqueante_por_prioridad(priority)
        
        # Calcular tiempos para bugs bloqueantes
        tiempo_to_qa, tiempo_qa_approved = _calcular_tiempos_estado(issue) if es_bloqueante else ("N/A", "N/A")
        
        # Fecha de creación para agrupación mensual
        try:
            fecha_creacion = pd.to_datetime(created)
            año_mes = fecha_creacion.strftime("%Y-%m")
            mes_nombre = fecha_creacion.strftime("%B %Y")
        except:
            continue
        
        rows.append({
            "Clave": key,
            "Fecha": created,
            "AñoMes": año_mes,
            "Mes": mes_nombre,
            "Prioridad": priority,
            "Summary": summary,
            "Status": status,
            "Labels": labels,
            "Epic": epic_key,
            "Tipo": "Bug",
            "EsKinetic": tipo_etiqueta == "KINETIC",
            "EsMejora": tipo_etiqueta == "MEJORA",
            "EsEpicaDelJson": es_epica_json,
            "EsBloqueante": es_bloqueante,
            "EpicaNombre": _obtener_nombre_epica(epic_key),
            "TiempoToQA": tiempo_to_qa,
            "TiempoQAApproved": tiempo_qa_approved
        })
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        st.warning("⚠️ No hay datos para mostrar")
        st.stop()
    
    # Filtrar a la ventana activa: Febrero 2025 en adelante
    try:
        df["Fecha_dt"] = pd.to_datetime(df["Fecha"], errors="coerce")
        inicio_filtro = pd.Timestamp(2025, 2, 1)
        df = df[(df["Fecha_dt"] >= inicio_filtro)].copy()
    except Exception:
        pass

    # Salvaguarda adicional por si alguna fila no parsea la fecha: usar AñoMes
    try:
        df = df[df["AñoMes"] >= "2025-02"].copy()
    except Exception:
        pass
    
    # ==========================
    # CÁLCULO DE MÉTRICAS
    # ==========================
    
    # Agrupar por mes
    df_mensual = df.groupby("AñoMes").agg({
        "Clave": "count",
        "EsKinetic": "sum",
        "EsMejora": "sum",
        "EsBloqueante": "sum"
    }).rename(columns={"Clave": "Q_Mensual"})
    
    # Calcular métricas derivadas
    df_mensual["Q_KINETIC"] = df_mensual["EsKinetic"]
    df_mensual["Q_MEJORA"] = df_mensual["EsMejora"]
    df_mensual["Q_Bugs_EVOLTIS"] = df_mensual["Q_Mensual"] - df_mensual["Q_KINETIC"] - df_mensual["Q_MEJORA"]
    df_mensual["Q_Bloqueantes"] = df_mensual["EsBloqueante"]
    df_mensual["%_Bloqueantes"] = (df_mensual["Q_Bloqueantes"] / df_mensual["Q_Bugs_EVOLTIS"] * 100).round(1)
    
    # Agregar nombre del mes
    df_mensual["Mes_Nombre"] = df_mensual.index.map(lambda x: pd.to_datetime(x + "-01").strftime("%B %Y"))
    
    # Ordenar por fecha
    df_mensual = df_mensual.sort_index()
    
    # ==========================
    # INTERFAZ DE USUARIO
    # ==========================
    
    # Mostrar tabla mensual (transpuesta)
    st.subheader("📊 Resumen Mensual")
    
    # Crear tabla transpuesta con meses como columnas
    tabla_transpuesta = {
        "Métrica": ["Q Mensual", "Q KINETIC", "Q MEJORA", "Q Bugs EVOLTIS", "Q Bloqueantes", "% Cumplimiento", "SLA Validación QA", "SLA Aprobado por QA"]
    }
    
    for idx, row in df_mensual.iterrows():
        mes_nombre = row["Mes_Nombre"]
        color_icon = "🟢" if row["%_Bloqueantes"] < 20 else "🔴"
        
        # Calcular promedios de SLA para bugs bloqueantes del mes
        df_mes_bloqueantes = df[(df["AñoMes"] == idx) & (df["EsBloqueante"] == True) & (df["EsKinetic"] == False) & (df["EsMejora"] == False)]
        
        sla_qa_promedio = "N/A"
        sla_approved_promedio = "N/A"
        
        if not df_mes_bloqueantes.empty:
            # Extraer días de los tiempos (remover "d" y convertir a número)
            tiempos_qa = []
            tiempos_approved = []
            
            for _, bug in df_mes_bloqueantes.iterrows():
                tiempo_qa = bug["TiempoToQA"]
                tiempo_approved = bug["TiempoQAApproved"]
                
                if tiempo_qa != "N/A" and tiempo_qa.endswith("d"):
                    try:
                        dias = int(tiempo_qa.replace("d", ""))
                        tiempos_qa.append(dias)
                    except:
                        pass
                
                if tiempo_approved != "N/A" and tiempo_approved.endswith("d"):
                    try:
                        dias = int(tiempo_approved.replace("d", ""))
                        tiempos_approved.append(dias)
                    except:
                        pass
            
            # Calcular promedios
            if tiempos_qa:
                sla_qa_promedio = f"{sum(tiempos_qa) / len(tiempos_qa):.1f} días"
            if tiempos_approved:
                sla_approved_promedio = f"{sum(tiempos_approved) / len(tiempos_approved):.1f} días"
        
        # Calcular % de cumplimiento: Bugs EVOLTIS cerrados / Bugs EVOLTIS total
        df_mes_evoltis = df[df["AñoMes"] == idx]
        df_mes_evoltis = df_mes_evoltis[(df_mes_evoltis["EsKinetic"] == False) & (df_mes_evoltis["EsMejora"] == False)]
        df_mes_evoltis_cerrados = df_mes_evoltis[df_mes_evoltis["Status"].str.contains("cerrado|closed|done|resuelto", case=False, na=False)]
        
        if not df_mes_evoltis.empty:
            cumplimiento = f"{(len(df_mes_evoltis_cerrados) / len(df_mes_evoltis) * 100):.1f}%"
        else:
            cumplimiento = "N/A"
        
        # Convertir todos los valores a string desde el inicio para evitar problemas con PyArrow
        tabla_transpuesta[mes_nombre] = [
            str(int(row["Q_Mensual"])),
            str(int(row["Q_KINETIC"])),
            str(int(row["Q_MEJORA"])),
            str(int(row["Q_Bugs_EVOLTIS"])),
            str(int(row["Q_Bloqueantes"])),
            cumplimiento,  # string con formato "XX.X%"
            sla_qa_promedio,  # string con formato "XX.X días" o "N/A"
            sla_approved_promedio  # string con formato "XX.X días" o "N/A"
        ]
    
    df_tabla_transpuesta = pd.DataFrame(tabla_transpuesta)
    st.dataframe(df_tabla_transpuesta, use_container_width=True, hide_index=True)
    
    # Detalle por mes
    st.subheader("🔍 Detalle por Mes")
    
    for idx, row in df_mensual.iterrows():
        mes_nombre = row["Mes_Nombre"]
        df_mes = df[df["AñoMes"] == idx]
        
        # Crear expander para cada mes
        expander_title = f"{mes_nombre} | Q Mensual: {int(row['Q_Mensual'])} | Q KINETIC: {int(row['Q_KINETIC'])} | Q MEJORA: {int(row['Q_MEJORA'])} | Q Bugs EVOLTIS: {int(row['Q_Bugs_EVOLTIS'])} | Q Bloqueantes: {int(row['Q_Bloqueantes'])}"
        
        with st.expander(expander_title, expanded=False):
            # Mostrar bugs no cerrados si el cumplimiento no es 100%
            df_mes_evoltis = df_mes[(df_mes["EsKinetic"] == False) & (df_mes["EsMejora"] == False)]
            df_mes_evoltis_cerrados = df_mes_evoltis[df_mes_evoltis["Status"].str.contains("cerrado|closed|done|resuelto", case=False, na=False)]
            
            if not df_mes_evoltis.empty:
                cumplimiento_porcentaje = (len(df_mes_evoltis_cerrados) / len(df_mes_evoltis) * 100)
                if cumplimiento_porcentaje < 100:
                    df_bugs_no_cerrados = df_mes_evoltis[~df_mes_evoltis["Status"].str.contains("cerrado|closed|done|resuelto", case=False, na=False)]
                    if not df_bugs_no_cerrados.empty:
                        st.warning(f"⚠️ **Bugs no cerrados ({len(df_bugs_no_cerrados)}):** {', '.join(df_bugs_no_cerrados['Clave'].tolist())}")
            
            # Mejoras
            df_mejoras = df_mes[df_mes["EsMejora"] == True]
            if not df_mejoras.empty:
                st.subheader(f"🔧 Mejoras ({len(df_mejoras)})")
                claves_mejoras = ", ".join(df_mejoras["Clave"].tolist())
                st.write(f"**Claves:** {claves_mejoras}")
            
            # Crear dos columnas para las tablas
            col1, col2 = st.columns(2)
            
            with col1:
                # Bugs Otras Funcionalidades (sin épica del JSON)
                df_otras_func = df_mes[(df_mes["EsEpicaDelJson"] == False) & (df_mes["EsKinetic"] == False) & (df_mes["EsMejora"] == False)]
                if not df_otras_func.empty:
                    st.subheader(f"🔧 Bugs Otras Funcionalidades ({len(df_otras_func)})")
                    
                    # Agrupar por épica
                    df_otras_agrupado = df_otras_func.groupby("EpicaNombre").agg({
                        "Clave": "count",
                        "Prioridad": lambda x: x.value_counts().to_dict()
                    }).reset_index()
                    df_otras_agrupado.columns = ["Épica", "Total", "Por Prioridad"]
                    
                    # Mostrar tabla
                    st.dataframe(df_otras_agrupado, use_container_width=True, hide_index=True)
                else:
                    st.subheader("🔧 Bugs Otras Funcionalidades (0)")
                    st.write("No hay bugs de otras funcionalidades")
            
            with col2:
                # Bugs de Entregables (con épica del JSON)
                df_entregables = df_mes[(df_mes["EsEpicaDelJson"] == True) & (df_mes["EsKinetic"] == False) & (df_mes["EsMejora"] == False)]
                if not df_entregables.empty:
                    st.subheader(f"📦 Bugs de Entregables ({len(df_entregables)})")
                    
                    # Agrupar por épica
                    df_entregables_agrupado = df_entregables.groupby("EpicaNombre").agg({
                        "Clave": "count",
                        "Prioridad": lambda x: x.value_counts().to_dict()
                    }).reset_index()
                    df_entregables_agrupado.columns = ["Épica", "Total", "Por Prioridad"]
                    
                    # Mostrar tabla
                    st.dataframe(df_entregables_agrupado, use_container_width=True, hide_index=True)
                else:
                    st.subheader("📦 Bugs de Entregables (0)")
                    st.write("No hay bugs de entregables")
            
            # Bugs Bloqueantes (con tiempos)
            df_bloqueantes = df_mes[(df_mes["EsBloqueante"] == True) & (df_mes["EsKinetic"] == False) & (df_mes["EsMejora"] == False)]
            if not df_bloqueantes.empty:
                st.subheader(f"🚨 Bugs Bloqueantes ({len(df_bloqueantes)})")
                
                # Crear tabla de bugs bloqueantes con tiempos
                df_bloqueantes_tabla = df_bloqueantes[["Clave", "TiempoToQA", "TiempoQAApproved"]].copy()
                df_bloqueantes_tabla.columns = ["Clave", "Días To Do → Validación QA", "Días To Do → Aprobado por QA"]
                
                st.dataframe(df_bloqueantes_tabla, use_container_width=True, hide_index=True)
            else:
                st.subheader("🚨 Bugs Bloqueantes (0)")
                st.write("No hay bugs bloqueantes")

    # ==========================
    # BUGS INTERNOS POR MES
    # ==========================
    st.subheader("🐛 Bugs Internos por Mes")
    st.caption("Cantidad de bugs internos por proyecto y mes (excluyendo bugs externos vinculados a BUG-XXX)")

    def tiene_vinculo_bug(issue):
        """Detecta si bug está vinculado a proyecto BUG-XXX (externo)"""
        try:
            issuelinks = issue.get("fields", {}).get("issuelinks", [])
            for link in issuelinks:
                # Verificar outward links
                outward_issue = link.get("outwardIssue")
                if outward_issue:
                    key = outward_issue.get("key", "")
                    if key.startswith("BUG-"):
                        return True
                
                # Verificar inward links
                inward_issue = link.get("inwardIssue")
                if inward_issue:
                    key = inward_issue.get("key", "")
                    if key.startswith("BUG-"):
                        return True
            return False
        except Exception:
            return False

    def traer_todas_las_issues_global(jira, jql, fields, max_results=5000):
        """Función global para cargar issues con paginación por mes para evitar límites de API"""
        issues = []
        # Cargar por mes para evitar límites de API
        meses_fechas = [
            ("2025-01", "2025-01-01", "2025-02-01"),
            ("2025-02", "2025-02-01", "2025-03-01"),
            ("2025-03", "2025-03-01", "2025-04-01"),
            ("2025-04", "2025-04-01", "2025-05-01"),
            ("2025-05", "2025-05-01", "2025-06-01"),
            ("2025-06", "2025-06-01", "2025-07-01"),
            ("2025-07", "2025-07-01", "2025-08-01"),
            ("2025-08", "2025-08-01", "2025-09-01"),
            ("2025-09", "2025-09-01", "2025-10-01"),
            ("2025-10", "2025-10-01", "2025-11-01"),
            ("2025-11", "2025-11-01", "2025-12-01"),
            ("2025-12", "2025-12-01", "2026-01-01")
        ]
        
        for mes, inicio, fin in meses_fechas:
            # Modificar JQL para filtrar por mes específico
            if 'created >= "2025-01-01"' in jql:
                jql_mes = jql.replace('created >= "2025-01-01"', f'created >= "{inicio}" AND created < "{fin}"')
            else:
                # Si no tiene el filtro de fecha, agregarlo
                jql_mes = f'{jql} AND created >= "{inicio}" AND created < "{fin}"'
            start_at = 0
            while True:
                endpoint = f'search?jql={jql_mes}&fields={fields}&startAt={start_at}&maxResults=100&expand=issuelinks'
                data = jira._get_json(endpoint)
                batch = data.get("issues", [])
                issues.extend(batch)
                if len(batch) < 100:  # Si devuelve menos de 100, es el último lote del mes
                    break
                start_at += 100
                if len(issues) >= max_results:
                    break
            if len(issues) >= max_results:
                break
        return issues[:max_results]

    MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

    try:
        # Cargar bugs desde la base de datos
        db = DatabaseHelper()
        db.conectar()
        
        # Cargar bugs de TAL, REP, ATI desde la base
        bugs_tal = db.obtener_bugs_con_cierre(["TAL"])
        bugs_rep = db.obtener_bugs_con_cierre(["REP"])
        bugs_ati = db.obtener_bugs_con_cierre(["ATI"])
        
        db.cerrar()
        
        # Filtrar bugs externos (vinculados a BUG-XXX)
        bugs_tal_internos = [b for b in bugs_tal if not tiene_vinculo_bug(b)]
        bugs_rep_internos = [b for b in bugs_rep if not tiene_vinculo_bug(b)]
        bugs_ati_internos = [b for b in bugs_ati if not tiene_vinculo_bug(b)]
        
        # Procesar datos para tabla
        datos_internos = []
        
        for bug in bugs_tal_internos:
            created = bug.get("fields", {}).get("created", "")
            if created:
                fecha = datetime.strptime(created[:10], "%Y-%m-%d")
                if fecha >= datetime(2025, 2, 1):
                    mes_nombre = MESES_ES[fecha.month]
                    datos_internos.append({"Proyecto": "TAL", "Mes": mes_nombre, "Cantidad": 1})
        
        for bug in bugs_rep_internos:
            created = bug.get("fields", {}).get("created", "")
            if created:
                fecha = datetime.strptime(created[:10], "%Y-%m-%d")
                if fecha >= datetime(2025, 2, 1):
                    mes_nombre = MESES_ES[fecha.month]
                    datos_internos.append({"Proyecto": "REP", "Mes": mes_nombre, "Cantidad": 1})
        
        for bug in bugs_ati_internos:
            created = bug.get("fields", {}).get("created", "")
            if created:
                fecha = datetime.strptime(created[:10], "%Y-%m-%d")
                if fecha >= datetime(2025, 2, 1):
                    mes_nombre = MESES_ES[fecha.month]
                    datos_internos.append({"Proyecto": "ATI", "Mes": mes_nombre, "Cantidad": 1})
        
        if datos_internos:
            df_internos = pd.DataFrame(datos_internos)
            
            # Crear pivot table
            df_pivot = df_internos.groupby(["Proyecto", "Mes"]).size().reset_index(name="Cantidad")
            df_pivot = df_pivot.pivot(index="Proyecto", columns="Mes", values="Cantidad").fillna(0)
            
            # Asegurar que todos los meses estén presentes
            meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            for mes in meses_orden:
                if mes not in df_pivot.columns:
                    df_pivot[mes] = 0
            
            # Reordenar columnas
            df_pivot = df_pivot[meses_orden]
            
            # Agregar columna de total
            df_pivot['Total'] = df_pivot.sum(axis=1)
            
            # Mostrar tabla
            st.dataframe(df_pivot, use_container_width=True)
            
            # Métricas totales
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("TAL Total", len(bugs_tal_internos))
            with col2:
                st.metric("REP Total", len(bugs_rep_internos))
            with col3:
                st.metric("ATI Total", len(bugs_ati_internos))
            with col4:
                st.metric("Total General", len(bugs_tal_internos) + len(bugs_rep_internos) + len(bugs_ati_internos))
        else:
            st.info("No se encontraron bugs internos para mostrar.")
            
    except Exception as e:
        st.error(f"Error cargando bugs internos: {e}")

    # ==========================
    # BUGS INTERNOS POR USUARIO
    # ==========================
    st.subheader("👥 Bugs Internos por Usuario")
    st.caption("Cantidad de bugs internos por usuario y mes (bugs vinculados a historias, asignado por historia)")

    try:
        # Cargar mapeo de usuarios
        with open('data/accountid_to_name.json', 'r', encoding='utf-8') as f:
            accountid_to_name = json.load(f)

        # Cargar historias desde la base de datos
        db = DatabaseHelper()
        db.conectar()
        
        historias_tal = db.obtener_historias_con_transiciones(["TAL"])
        historias_rep = db.obtener_historias_con_transiciones(["REP"])
        historias_ati = db.obtener_historias_con_transiciones(["ATI"])
        
        db.cerrar()
        
        # Crear diccionario de historias por clave
        historias_por_clave = {}
        for historia in historias_tal + historias_rep + historias_ati:
            clave = historia.get("key", "")
            assignee = historia.get("fields", {}).get("assignee")
            account_id = assignee.get("accountId", "") if assignee else ""
            nombre = accountid_to_name.get(account_id, "Sin asignar") if account_id else "Sin asignar"
            historias_por_clave[clave] = nombre
        
        # Cargar todos los bugs internos (ya cargados arriba)
        todos_los_bugs = bugs_tal_internos + bugs_rep_internos + bugs_ati_internos
        
        # Procesar bugs vinculados a historias
        datos_usuarios = []
        
        for bug in todos_los_bugs:
            created = bug.get("fields", {}).get("created", "")
            if not created:
                continue
            fecha = datetime.strptime(created[:10], "%Y-%m-%d")
            # Filtrar fechas anteriores a Feb 2025
            if fecha < datetime(2025, 2, 1):
                continue
            mes_nombre = MESES_ES[fecha.month]
            
            # Buscar historia vinculada (PRIMERO por parent, luego por issuelinks)
            usuario_asignado = None
            
            # 1. Buscar por parent (si el bug es subtask de una historia)
            parent = bug.get("fields", {}).get("parent")
            if parent:
                parent_key = parent.get("key", "")
                if parent_key in historias_por_clave:
                    usuario_asignado = historias_por_clave[parent_key]
            
            # 2. Si no encontró por parent, buscar por issuelinks
            if not usuario_asignado:
                issuelinks = bug.get("fields", {}).get("issuelinks", [])
                for link in issuelinks:
                    # Verificar outward links
                    outward_issue = link.get("outwardIssue")
                    if outward_issue:
                        clave_historia = outward_issue.get("key", "")
                        if clave_historia in historias_por_clave:
                            usuario_asignado = historias_por_clave[clave_historia]
                            break
                    
                    # Verificar inward links
                    inward_issue = link.get("inwardIssue")
                    if inward_issue:
                        clave_historia = inward_issue.get("key", "")
                        if clave_historia in historias_por_clave:
                            usuario_asignado = historias_por_clave[clave_historia]
                            break
            
            # Solo contar bugs que tienen historia vinculada (asignado por el dueño de la historia)
            if usuario_asignado and usuario_asignado != "Sin asignar":
                datos_usuarios.append({
                    "Usuario": usuario_asignado,
                    "Mes": mes_nombre,
                    "Cantidad": 1
                })
        
        if datos_usuarios:
            df_usuarios = pd.DataFrame(datos_usuarios)
            
            # Crear pivot table
            df_pivot_usuarios = df_usuarios.groupby(["Usuario", "Mes"]).size().reset_index(name="Cantidad")
            df_pivot_usuarios = df_pivot_usuarios.pivot(index="Usuario", columns="Mes", values="Cantidad").fillna(0)
            
            # Asegurar que todos los meses estén presentes
            meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                          "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            for mes in meses_orden:
                if mes not in df_pivot_usuarios.columns:
                    df_pivot_usuarios[mes] = 0
            
            # Reordenar columnas
            df_pivot_usuarios = df_pivot_usuarios[meses_orden]
            
            # Agregar columna de total
            df_pivot_usuarios['Total'] = df_pivot_usuarios.sum(axis=1)
            
            # Mostrar tabla
            st.dataframe(df_pivot_usuarios, use_container_width=True)
            
            # Estadísticas
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Bugs Asignados", len(datos_usuarios))
            with col2:
                st.metric("Usuarios Diferentes", len(df_pivot_usuarios.index))
            with col3:
                total_general = df_pivot_usuarios['Total'].sum()
                st.metric("Total General", int(total_general))
        else:
            st.info("No se encontraron bugs internos para mostrar.")
            
    except Exception as e:
        st.error(f"Error cargando bugs por usuario: {e}")