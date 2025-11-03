"""
Pestaña Puntos Históricos - Tablero SUMMA
Muestra puntos por mes y proyecto desde 2022
"""

import streamlit as st
import pandas as pd
from src.utils.database_helper import DatabaseHelper

def mostrar_puntos_historicos():
    """Mostrar la pestaña de Puntos Históricos por Proyecto"""
    
    st.header("📊 Puntos Históricos por Proyecto")
    st.caption("📈 Análisis de puntos quemados (lista para implementar) por mes y proyecto desde 2022 (ATI, REP, TAL)")
    
    # Mostrar fecha de última actualización
    db = DatabaseHelper()
    db.conectar()
    fecha_actualizacion = db.obtener_fecha_ultima_actualizacion()
    st.caption(f"🕒 **Última actualización:** {fecha_actualizacion}")
    
    # Cargar historias desde la base de datos (ATI, REP, TAL) desde 2022
    historias = db.obtener_historias_con_transiciones(["ATI", "REP", "TAL"], fecha_desde='2022-01-01')
    db.cerrar()
    
    if not historias:
        st.warning("⚠️ No se encontraron historias en la base de datos")
        st.stop()
    
    # Estado que indica que está lista para implementar (puntos quemados)
    ESTADO_LISTO_PARA_IMPLEMENTAR = "lista para implementar"
    
    def _norm(s):
        return str(s or "").strip().lower()
    
    def _obtener_fecha_listo_implementar(issue):
        """Obtener la fecha de primera transición a 'lista para implementar'"""
        histories = (issue.get("changelog", {}) or {}).get("histories", []) or []
        
        # Ordenar historias por fecha
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))
        
        # Buscar primera transición a "lista para implementar"
        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            
            for it in hist.get("items", []) or []:
                if _norm(it.get("field")) == "status" and _norm(it.get("toString")) == ESTADO_LISTO_PARA_IMPLEMENTAR:
                    if pd.notna(h_created):
                        return h_created
        
        return None
    
    # Procesar historias para obtener puntos por mes y proyecto
    puntos_por_mes_proyecto = []
    
    for issue in historias:
        f = issue.get("fields", {}) or {}
        
        # Verificar que sea una historia
        itype = (f.get("issuetype", {}) or {}).get("name", "").lower()
        if itype != "historia":
            continue
        
        # Obtener proyecto
        proyecto_key = (f.get("project") or {}).get("key", "")
        if proyecto_key not in ["ATI", "REP", "TAL"]:
            continue
        
        # Obtener puntos (mismo método que usa el resto del tablero)
        puntos = 0.0
        for cf_key in ["customfield_10026", "customfield_10016"]:
            val = f.get(cf_key)
            if val is not None:
                try:
                    puntos = float(val)
                    break
                except (ValueError, TypeError):
                    continue
        
        # Solo incluir historias con puntos > 0
        if puntos <= 0:
            continue
        
        # Obtener fecha de transición a "lista para implementar"
        fecha_listo = _obtener_fecha_listo_implementar(issue)
        
        # Si no tiene esa transición, no contar los puntos (no se quemaron aún)
        if fecha_listo is None:
            continue
        
        # Filtrar desde 2022
        if fecha_listo.year < 2022:
            continue
        
        año_mes = fecha_listo.strftime("%Y-%m")
        mes_nombre = fecha_listo.strftime("%B %Y")
        
        # Obtener clave de la historia
        historia_key = issue.get("key", "") or issue.get("id", "")
        if not historia_key:
            # Si no está en "key", intentar obtenerla de otra forma
            historia_key = str(issue.get("key", ""))
        
        puntos_por_mes_proyecto.append({
            "Proyecto": proyecto_key,
            "AñoMes": año_mes,
            "Mes": mes_nombre,
            "Puntos": puntos,
            "Clave": historia_key if historia_key else "SIN_CLAVE"
        })
    
    # Crear DataFrame y pivot table
    if not puntos_por_mes_proyecto:
        st.info("No se encontraron historias que hayan pasado a 'lista para implementar' desde 2022")
        st.stop()
    
    df_puntos = pd.DataFrame(puntos_por_mes_proyecto)
    
    # Agrupar por proyecto y mes, sumando puntos y concatenando claves
    df_puntos_agrupado = df_puntos.groupby(["Proyecto", "AñoMes", "Mes"], as_index=False).agg({
        "Puntos": "sum",
        "Clave": lambda x: ", ".join(sorted(set(x)))
    })
    
    # Crear pivot table con meses como columnas (puntos)
    df_pivot_puntos = df_puntos_agrupado.pivot(index="Proyecto", columns="AñoMes", values="Puntos").fillna(0)
    
    # Crear pivot table con claves agrupadas
    df_pivot_claves = pd.DataFrame()  # Inicializar vacío por si acaso
    if "Clave" in df_puntos_agrupado.columns:
        df_pivot_claves = df_puntos_agrupado.pivot(index="Proyecto", columns="AñoMes", values="Clave").fillna("")
    
    # Ordenar columnas por fecha (desde 2022)
    columnas_ordenadas = sorted([col for col in df_pivot_puntos.columns if col >= "2022-01"], reverse=False)
    if columnas_ordenadas:
        df_pivot_puntos = df_pivot_puntos[columnas_ordenadas]
        # Solo ordenar claves si existen las columnas
        if not df_pivot_claves.empty:
            columnas_claves_existentes = [col for col in columnas_ordenadas if col in df_pivot_claves.columns]
            if columnas_claves_existentes:
                df_pivot_claves = df_pivot_claves[columnas_claves_existentes]
    
    # Agregar columna de total a la tabla de puntos
    df_pivot_puntos['Total'] = df_pivot_puntos.sum(axis=1)
    
    # Renombrar columnas para mostrar formato "Mes Año" en español
    meses_es = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    columnas_renombradas = {}
    for col in df_pivot_puntos.columns:
        if col == 'Total':
            columnas_renombradas[col] = col
        else:
            try:
                fecha = pd.to_datetime(col + "-01")
                mes_es = meses_es.get(fecha.month, fecha.strftime("%B"))
                columnas_renombradas[col] = f"{mes_es} {fecha.year}"
            except:
                columnas_renombradas[col] = col
    
    df_pivot_puntos.rename(columns=columnas_renombradas, inplace=True)
    
    # Renombrar columnas para tabla de claves (solo si no está vacía)
    if not df_pivot_claves.empty:
        columnas_renombradas_claves = {}
        for col in df_pivot_claves.columns:
            if col == 'Total':
                continue  # No incluir Total en la tabla de claves
            try:
                fecha = pd.to_datetime(col + "-01")
                mes_es = meses_es.get(fecha.month, fecha.strftime("%B"))
                columnas_renombradas_claves[col] = f"{mes_es} {fecha.year}"
            except:
                columnas_renombradas_claves[col] = col
        
        if columnas_renombradas_claves:
            df_pivot_claves.rename(columns=columnas_renombradas_claves, inplace=True)
    
    # Mostrar tabla de puntos
    st.subheader("📊 Puntos por Mes y Proyecto (desde 2022)")
    st.dataframe(df_pivot_puntos, use_container_width=True)
    
    # Mostrar tabla de claves
    if not df_pivot_claves.empty:
        st.subheader("🔑 Claves de Historias por Mes y Proyecto")
        st.dataframe(df_pivot_claves, use_container_width=True)
    else:
        # Debug: mostrar información sobre los datos
        st.info("ℹ️ No hay claves para mostrar. Verificando datos...")
        with st.expander("🔍 Debug - Ver datos"):
            st.write("Datos agrupados:", df_puntos_agrupado.head() if not df_puntos_agrupado.empty else "Vacío")
            st.write("Columnas:", df_puntos_agrupado.columns.tolist() if not df_puntos_agrupado.empty else "Sin columnas")
    
    # Estadísticas adicionales
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_ati = df_pivot_puntos.loc["ATI", "Total"] if "ATI" in df_pivot_puntos.index else 0
        st.metric("ATI - Total", f"{total_ati:.1f}")
    
    with col2:
        total_rep = df_pivot_puntos.loc["REP", "Total"] if "REP" in df_pivot_puntos.index else 0
        st.metric("REP (Repuestos) - Total", f"{total_rep:.1f}")
    
    with col3:
        total_tal = df_pivot_puntos.loc["TAL", "Total"] if "TAL" in df_pivot_puntos.index else 0
        st.metric("TAL (Taller) - Total", f"{total_tal:.1f}")

