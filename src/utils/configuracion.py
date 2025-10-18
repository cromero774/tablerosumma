"""
Configuración y constantes del Tablero SUMMA
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from cache_datos import cargar_df_cache, guardar_df_cache, cargar_json_cache, guardar_json_cache

# Mapeos de proyectos
MAPEO_TEM = {
    "TEM-1":  ("CORE-TECH", "TECH LAB - INTERNO"),
    "TEM-2":  ("CORE-TECH", "TECH LAB - INTERNO"),
    "TEM-5":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF POSVENTA"),
    "TEM-7":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS"),
    "TEM-8":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO ATI"),
    "TEM-9":  ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - DESARROLLO MODULO TALLER"),
    "TEM-28": ("CORE-TECH", "TECH LAB - INTERNO"),
    "TEM-30": ("MP-MAIPU-SUMMA", "MAIPU - SUMMA - ESCRITURA RF ATI"),
}

RESUMEN_A_PROYECTO = {
    "MAIPU - SUMMA - ESCRITURA RF POSVENTA": "AFUS",
    "MAIPU - SUMMA - DESARROLLO MODULO REPUESTOS": "REPUESTOS MAIPU",
    "MAIPU - SUMMA - DESARROLLO MODULO TALLER": "TALLER - MAIPÚ -",
    "MAIPU - SUMMA - DESARROLLO ATI": "AFUs ATI",
    "MAIPU - SUMMA - ESCRITURA RF ATI": "AFUs ATI",
    "": "TECH LAB - INTERNO"
}

# Proyectos por categoría
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

def cargar_epicas_relevantes():
    """Cargar épicas relevantes desde el archivo JSON"""
    try:
        with open('data/epicas_relevantes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def cargar_datos_historicos():
    """Cargar datos históricos de horas"""
    try:
        horas_historicas = pd.read_csv('data/horas_historicas.csv')
        horas_con_proyecto = pd.read_csv('data/horas_con_proyecto.csv')
        return horas_historicas, horas_con_proyecto
    except FileNotFoundError:
        return pd.DataFrame(), pd.DataFrame()

def cargar_issues_jira_cache():
    """Cargar issues de Jira con cache"""
    try:
        # Intentar cargar desde cache
        return cargar_df_cache('issues_jira_cache')
    except FileNotFoundError:
        # Si no hay cache, retornar DataFrame vacío
        return pd.DataFrame()

def _data_path(filename):
    """Helper para obtener rutas de archivos de datos"""
    return os.path.join(os.path.dirname(__file__), '..', '..', 'data', filename)

def cache_path(nombre, ext):
    """Helper para obtener rutas de cache"""
    cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{nombre}.{ext}")

def obtener_proyecto_logico(row):
    """Función para obtener el proyecto lógico basado en las reglas de negocio"""
    proyecto = row.get('Proyecto', '')
    issue = row.get('Issue', '')
    fecha = row.get('Fecha', '')
    
    # Convertir fecha a timestamp
    if fecha and pd.notna(fecha):
        fecha_dt = pd.to_datetime(fecha, errors='coerce')
    else:
        fecha_dt = None
    
    # Normalización de proyectos
    def normalizar_proyecto(p):
        if p in ['CORETECH', 'Core Tech', 'TECHLAB']:
            return 'TECH LAB - INTERNO'
        return p
    
    # Antes de junio 2025: ignorar TEMPO WORKLOAD, resto usar proyecto normalizado
    if fecha_dt and fecha_dt < pd.Timestamp("2025-06-01"):
        if proyecto == "TEMPO WORKLOAD":
            return None
        return normalizar_proyecto(proyecto)
    
    # Desde junio 2025: si es TEM-, usar el mapeo
    if issue and issue.startswith("TEM-"):
        if issue in MAPEO_TEM:
            cuenta, resumen = MAPEO_TEM[issue]
            if cuenta == "CORE-TECH":
                return "TECH LAB - INTERNO"
            elif cuenta == "MP-MAIPU-SUMMA":
                return RESUMEN_A_PROYECTO.get(resumen, "OTRO")
            # Si no lo encontramos en el mapeo, caemos al proyecto normalizado
            return normalizar_proyecto(proyecto)
    
    # Para TEMPO WORKLOAD desde junio 2025, procesar normalmente
    if proyecto == "TEMPO WORKLOAD":
        # Mapear según el issue si es TEM-
        if issue and issue.startswith("TEM-"):
            if issue in MAPEO_TEM:
                cuenta, resumen = MAPEO_TEM[issue]
                if cuenta == "CORE-TECH":
                    return "TECH LAB - INTERNO"
                else:
                    # Aplicar mapeo RESUMEN_A_PROYECTO si existe
                    if resumen in RESUMEN_A_PROYECTO:
                        return RESUMEN_A_PROYECTO[resumen]
                    return resumen
    
    # Aplicar mapeo RESUMEN_A_PROYECTO si existe
    if proyecto in RESUMEN_A_PROYECTO:
        return RESUMEN_A_PROYECTO[proyecto]
    
    return normalizar_proyecto(proyecto)

def cargar_datos_principales():
    """Cargar datos principales replicando la lógica del original"""
    import json
    import streamlit as st
    
    try:
        # Cargar mapeo de usuarios
        accountid_path = _data_path("accountid_to_name.json")
        with open(accountid_path, "r", encoding="utf-8") as f:
            accountid_to_name = json.load(f)
        
        # Cargar datos históricos y actuales
        hist_path = str(_data_path("horas_historicas.csv"))
        actual_path = str(_data_path("horas_con_proyecto.csv"))
        
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
        
        # Aplicar mapeo de account IDs a nombres
        df["Usuario"] = df["Usuario"].map(accountid_to_name).fillna(df["Usuario"])
        
        # Crear columna Proyecto_logico
        df["Proyecto_logico"] = df.apply(obtener_proyecto_logico, axis=1)
        df = df[df["Proyecto_logico"].notna()]
        
        
        return df
        
    except Exception as e:
        st.error(f"❌ Error cargando datos: {e}")
        return pd.DataFrame()

def configurar_sidebar():
    """Configurar el sidebar exactamente como el original"""
    import streamlit as st
    
    # Menú principal con expandibles
    st.sidebar.markdown("## 📊 Dashboard")
    
    # Botón para volver al menú
    if st.sidebar.button("🏠 Menú", key="btn_menu", use_container_width=True):
        st.session_state.opcion_actual = "Menú"
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Inicializar session state para la opción seleccionada
    if 'opcion_actual' not in st.session_state:
        st.session_state.opcion_actual = "Menú"
    
    # Postventas
    with st.sidebar.expander("🏢 Postventas", expanded=False):
        if st.button("📊 Horas Postventas", key="btn_horas_postventas", use_container_width=True):
            st.session_state.opcion_actual = "Horas Postventas"
            st.rerun()
        if st.button("💻 Desarrollo Postventas", key="btn_desarrollo_postventas", use_container_width=True):
            st.session_state.opcion_actual = "Desarrollo Postventas"
            st.rerun()
        if st.button("📦 Entregables Postventas", key="btn_entregables_postventas", use_container_width=True):
            st.session_state.opcion_actual = "Entregables Postventas"
            st.rerun()
        if st.button("📈 Histórico Postventa", key="btn_historico_postventas", use_container_width=True):
            st.session_state.opcion_actual = "Histórico Postventa"
            st.rerun()
    
    # ATI
    with st.sidebar.expander("🏢 ATI", expanded=False):
        if st.button("📊 Horas ATI", key="btn_horas_ati", use_container_width=True):
            st.session_state.opcion_actual = "Horas ATI"
            st.rerun()
        if st.button("💻 Desarrollo ATI", key="btn_desarrollo_ati", use_container_width=True):
            st.session_state.opcion_actual = "Desarrollo ATI"
            st.rerun()
        if st.button("📦 Entregables ATI", key="btn_entregables_ati", use_container_width=True):
            st.session_state.opcion_actual = "Entregables ATI"
            st.rerun()
        if st.button("📈 Histórico ATI", key="btn_historico_ati", use_container_width=True):
            st.session_state.opcion_actual = "Histórico ATI"
            st.rerun()
    
    # BUGS
    with st.sidebar.expander("🐛 BUGS", expanded=False):
        if st.button("🐛 BUGS", key="btn_bugs", use_container_width=True):
            st.session_state.opcion_actual = "BUGS"
            st.rerun()
    
    # Velocidad
    with st.sidebar.expander("⚡ Velocidad", expanded=False):
        if st.button("⚡ Velocidad de devs", key="btn_velocidad", use_container_width=True):
            st.session_state.opcion_actual = "Velocidad de devs"
            st.rerun()
    
    # Gantt
    with st.sidebar.expander("📊 Gantt", expanded=False):
        if st.button("📊 Gantt", key="btn_gantt", use_container_width=True):
            st.session_state.opcion_actual = "Gantt"
            st.rerun()
    
    # Mostrar la opción seleccionada actualmente
    opcion = st.session_state.opcion_actual
    st.sidebar.markdown(f"**Seleccionado:** {opcion}")
    
    # Configuración
    st.sidebar.markdown("---")
    with st.sidebar.expander("⚙️ Configuración", expanded=False):
        # Inicializar tema en session state
        if 'tema_seleccionado' not in st.session_state:
            st.session_state.tema_seleccionado = "Oscuro"
        
        # Selector de tema
        tema_actual = st.selectbox(
            "Tema del tablero:",
            ["Claro", "Oscuro"],
            index=1 if st.session_state.tema_seleccionado == "Oscuro" else 0,
            key="selector_tema"
        )
        
        # Guardar tema seleccionado
        st.session_state.tema_seleccionado = tema_actual
