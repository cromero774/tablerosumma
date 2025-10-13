# ===== BOOTSTRAP SRC (compat sin cambiar tu estructura) =====
from pathlib import Path
import sys, importlib.util as _ilu
BASE = Path(__file__).resolve().parent
SRC = BASE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
try:
    import jira_conexion as _jc  # respeta tu import original
except ModuleNotFoundError:
    _p = SRC / "jira_conexion.py"
    if _p.exists():
        _spec = _ilu.spec_from_file_location("jira_conexion", _p)
        _jc = _ilu.module_from_spec(_spec)
        assert _spec.loader is not None
        _spec.loader.exec_module(_jc)
        sys.modules.setdefault("jira_conexion", _jc)
    else:
        raise
# Alias por compat para 'from src.jira_conexion import ...'
sys.modules.setdefault("src.jira_conexion", _jc)
# Exponer 'jira' al resto del código
jira = getattr(_jc, "jira", None)
if jira is None and hasattr(_jc, "get_jira"):
    try:
        jira = _jc.get_jira()
    except Exception:
        pass
# ===== FIN BOOTSTRAP =====

from pathlib import Path
BASE = Path(__file__).resolve().parent

# --- Helper de rutas para datos ---
def _data_path(name: str):
    cand1 = BASE / "data" / name
    if cand1.exists():
        return cand1
    cand2 = BASE / name
    return cand2  # si no existe, que falle con FileNotFoundError y muestre el path
# --- fin helper ---

# ===== Integración Jira segura (SoT v3) =====
import jira_conexion as _jc  # módulo local sin efectos colaterales
_jc.ensure_ready()
jira = _jc.get_jira()  # Cliente Jira listo para usar
# ============================================


# ===== JIRA BOOTSTRAP (auto-inyectado) =====
import sys, types, requests

def _try_import_jira_conexion():
    for name in ("jira_conexion", "src.jira_conexion", "tablero.jira_conexion"):
        try:
            return __import__(name, fromlist=["*"])
        except Exception:
            pass
    return None

def _build_client(mod):
    if not mod:
        return None
    if hasattr(mod, "jira") and getattr(mod, "jira") is not None:
        return getattr(mod, "jira")
    for fname in ("get_jira", "get_client", "get_jira_client"):
        if hasattr(mod, fname):
            try:
                return getattr(mod, fname)()
            except Exception:
                pass
    for cname in ("JiraAPI", "JiraClient", "Jira"):
        if hasattr(mod, cname):
            try:
                return getattr(mod, cname)()
            except Exception:
                pass
    return None

def _ensure_get_json(client):
    if client is None:
        return None
    if hasattr(client, "_get_json"):
        return client

    def _shim_get_json(endpoint, params=None, label=None):
        base = getattr(client, "base_url", "")
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = (base.rstrip("/") + "/" + endpoint.lstrip("/")) if base else endpoint
        sess = getattr(client, "session", None) or requests.Session()
        timeout = getattr(client, "timeout_read", 120)
        resp = sess.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"text": resp.text}

    try:
        setattr(client, "_get_json", _shim_get_json)
    except Exception:
        pass
    return client

_mod = _try_import_jira_conexion()
_cli = _build_client(_mod)
jira = _ensure_get_json(_cli)

proxy = types.SimpleNamespace(jira=jira)
sys.modules.setdefault("jira_conexion", proxy)
# ===== FIN JIRA BOOTSTRAP =====

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import os
import json
from dateutil.relativedelta import relativedelta

import sys
from jira_conexion import ensure_ready, jira, traer_issues_jql  # SoT v3
ensure_ready()  # valida auth y endpoint /search/jql
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from cache_datos import cargar_df_cache, guardar_df_cache, cache_actualizado, cargar_json_cache, guardar_json_cache, cache_path
from tempo_conexion import traer_worklogs
from jira_conexion import traer_issues_jql
import hashlib
import pickle


# ---- Helpers robustos para claves y formas de issues ----
def _unwrap_issue(iss):
    """Devuelve el diccionario del issue en caso de venir envuelto en 'issue', 'data' o 'attributes'."""
    if isinstance(iss, dict):
        return iss.get('issue') or iss.get('data') or iss.get('attributes') or iss
    return iss


def _safe_issue_key(iss):
    """Obtiene la clave (key) del issue sin asumir un único formato."""
    if not isinstance(iss, dict):
        return None
    k = iss.get('key') or iss.get('issueKey')
    if k:
        return k
    f = iss.get('fields') or iss.get('attributes') or {}
    return f.get('key') or f.get('issueKey') or f.get('issuekey')

st.set_page_config(page_title="Tablero SUMMA", layout="wide")

with open(_data_path("epicas_relevantes.json"), "r", encoding="utf-8") as f:
    epicas_relevantes = json.load(f)

rns_relevantes = [epica["rn"] for epica in epicas_relevantes]

# === CARGA DE DATOS PRINCIPALES CON CACHE ===
# Cargar mapeo de usuarios primero
with open(_data_path("accountid_to_name.json"), "r", encoding="utf-8") as f:
    accountid_to_name = json.load(f)

# FORZAR RECARGA COMPLETA - ELIMINAR CACHE
cache_file = cache_path('horas_unificadas', 'pkl')
if os.path.exists(cache_file):
    os.remove(cache_file)

# Lógica original de carga y procesamiento de df
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

try:
    
    # Aplicar mapeo de account IDs a nombres SIEMPRE (incluso si viene del cache)
    df["Usuario"] = df["Usuario"].map(accountid_to_name).fillna(df["Usuario"])
except Exception as e:
    st.error(f"Error cargando datos principales: {e}")
    raise

# ----------------------------------------------
# Helper: carga de issues Jira con cache local JSON
# ----------------------------------------------
def cargar_issues_jira_cache(jql: str, fields: str, nombre_cache: str, max_horas: int = 24):
    """Usa la sesión Jira ya configurada (jira._get_json) para traer issues con paginado
    y cachea el resultado en data/cache/<nombre_cache>.json. Evita dependencias de env.
    """
    path = cache_path(nombre_cache, 'json')
    try:
        # Cache fresco
        if os.path.exists(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if (datetime.now() - mtime) < timedelta(hours=max_horas):
                return cargar_json_cache(nombre_cache)

        issues, start_at, page_size = [], 0, 100
        while True:
            params = {
                "jql": jql,
                "fields": fields,
                "startAt": start_at,
                "maxResults": page_size,
            }
            data = jira._get_json("search", params=params)
            batch = (data or {}).get("issues", [])
            issues.extend(batch)
            if len(batch) < page_size:
                break
            start_at += page_size

        guardar_json_cache(issues, nombre_cache)
        return issues
    except Exception as exc:
        try:
            # Fallback a cache viejo si existe
            return cargar_json_cache(nombre_cache)
        except Exception:
            st.error(f"No se pudo cargar issues (cache/Jira): {exc}")
            return []

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

# Usar la opción del session state
opcion = st.session_state.opcion_actual

# Mostrar la opción seleccionada actualmente
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

# Aplicar CSS según el tema seleccionado
if st.session_state.tema_seleccionado == "Claro":
    st.markdown("""
    <style>
    /* Tema Claro - Profesional */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #ffffff;
    }
    
    /* Eliminar franja negra superior */
    .stApp > header {
        background-color: transparent !important;
    }
    
    .stApp > header > div {
        background-color: transparent !important;
    }
    
    /* Main container sin margen superior */
    .main .block-container {
        background: rgba(255, 255, 255, 0.98);
        border-radius: 15px;
        padding: 2rem;
        margin: 0.5rem 1rem 1rem 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(10px);
        max-width: none;
    }
    
    /* Sidebar elegante */
    .stSidebar {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* Texto de sidebar visible - FORZAR VISIBILIDAD */
    .stSidebar * {
        color: #2c3e50 !important;
    }
    
    .stSidebar .stMarkdown {
        color: #2c3e50 !important;
    }
    
    .stSidebar h1, .stSidebar h2, .stSidebar h3 {
        color: #2c3e50 !important;
    }
    
    .stSidebar p, .stSidebar div, .stSidebar span {
        color: #2c3e50 !important;
    }
    
    /* Botones de sidebar elegantes */
    .stSidebar .stButton > button {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stSidebar .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        background: linear-gradient(45deg, #5a6fd8, #6a4190);
    }
    
    /* Botones del contenido principal */
    .main .stButton > button {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .main .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Selectbox elegante */
    .stSelectbox > div > div {
        background: white;
        border: 2px solid #e1e5e9;
        border-radius: 8px;
        color: #2c3e50;
    }
    
    /* Input fields elegantes */
    .stTextInput > div > div > input {
        background: white;
        border: 2px solid #e1e5e9;
        border-radius: 8px;
        color: #2c3e50;
    }
    
    .stNumberInput > div > div > input {
        background: white;
        border: 2px solid #e1e5e9;
        border-radius: 8px;
        color: #2c3e50;
    }
    
    /* Títulos con mejor contraste */
    .main h1, .main h2, .main h3 {
        color: #2c3e50;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    /* Texto del contenido */
    .main .stMarkdown {
        color: #2c3e50 !important;
    }
    
    /* Tablas elegantes */
    .stDataFrame {
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border: 1px solid #e1e5e9;
    }
    
    /* Expanders elegantes */
    .stSidebar .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.9);
        color: #2c3e50 !important;
        border-radius: 8px;
        margin: 2px 0;
        border: 1px solid #e1e5e9;
    }
    
    .stSidebar .streamlit-expanderContent {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 8px;
        margin: 2px 0;
        border: 1px solid #e1e5e9;
    }
    
    /* Checkbox elegante */
    .stCheckbox > div > div > div > div {
        background: white;
        border: 2px solid #e1e5e9;
        border-radius: 4px;
    }
    
    /* Métricas elegantes */
    .stMetric {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        border: 1px solid #e1e5e9;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    /* Tema Oscuro - Elegante */
    .stApp {
        background: linear-gradient(135deg, #0c0c0c 0%, #1a1a2e 50%, #16213e 100%);
        color: #ffffff;
    }
    
    .main .block-container {
        background: rgba(30, 30, 30, 0.9);
        border-radius: 15px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .stSidebar {
        background: rgba(20, 20, 20, 0.9);
        backdrop-filter: blur(10px);
    }
    
    /* Botones elegantes en tema oscuro */
    .stButton > button {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Selectbox elegante */
    .stSelectbox > div > div {
        background: #2a2a2a;
        border: 2px solid #444;
        border-radius: 8px;
        color: white;
    }
    
    /* Títulos con mejor contraste */
    h1, h2, h3 {
        color: #ffffff;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }
    
    /* Tablas con fondo oscuro */
    .stDataFrame {
        background: #2a2a2a;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# === PÁGINA DE MENÚ ===
if opcion == "Menú":
    # Centrar el contenido
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # Logo EVOLTIS - Centrado explícitamente
        logo_col_left, logo_col_center, logo_col_right = st.columns([1, 2, 1])
        with logo_col_center:
            try:
                st.image("data/logo-evoltis.png", width=400)
            except:
                # Si no encuentra la imagen, mostrar un logo simple con texto
                st.markdown("""
                <div style="text-align: center; margin: 20px 0;">
                    <h1 style="color: white; font-size: 48px; font-weight: bold; font-family: Arial, sans-serif; margin: 0; letter-spacing: 3px;">EVOLTIS</h1>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Título principal
        st.markdown("""
        <div style="text-align: center;">
            <h1 style="color: #ffffff; font-size: 3rem; margin-bottom: 1rem; font-weight: 300;">
                Proyecto SUMMA
            </h1>
            <h2 style="color: #cccccc; font-size: 1.5rem; margin-bottom: 2rem; font-weight: 300;">
                Dashboard de Gestión y Seguimiento
            </h2>
            <p style="color: #aaaaaa; font-size: 1.1rem; line-height: 1.6;">
                Sistema integral para el monitoreo de proyectos, desarrollo, entregables<br>
                y métricas de rendimiento del equipo de desarrollo.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # Botones de acceso rápido
        st.markdown("### 🚀 Acceso Rápido")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("📊 Horas", key="caratula_horas", use_container_width=True):
                st.session_state.opcion_actual = "Horas Postventas"
                st.rerun()
        
        with col_btn2:
            if st.button("💻 Desarrollo", key="caratula_desarrollo", use_container_width=True):
                st.session_state.opcion_actual = "Desarrollo Postventas"
                st.rerun()
        
        with col_btn3:
            if st.button("📦 Entregables", key="caratula_entregables", use_container_width=True):
                st.session_state.opcion_actual = "Entregables Postventas"
                st.rerun()
        
        col_btn4, col_btn5, col_btn6 = st.columns(3)
        
        with col_btn4:
            if st.button("🐛 BUGS", key="caratula_bugs", use_container_width=True):
                st.session_state.opcion_actual = "BUGS"
                st.rerun()
        
        with col_btn5:
            if st.button("⚡ Velocidad", key="caratula_velocidad", use_container_width=True):
                st.session_state.opcion_actual = "Velocidad de devs"
                st.rerun()
        
        with col_btn6:
            if st.button("📊 Gantt", key="caratula_gantt", use_container_width=True):
                st.session_state.opcion_actual = "Gantt"
                st.rerun()
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Información adicional
        st.markdown("""
        <div style="text-align: center; color: #666666; font-size: 0.9rem;">
            <p>Utiliza el menú lateral para navegar entre las diferentes secciones del dashboard</p>
        </div>
        """, unsafe_allow_html=True)


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
            # Filtrar solo usuarios que están en el mapeo (son nombres válidos, no IDs)
            usuarios_validos = [u for u in df["Usuario"].dropna().unique() if str(u).strip() != "" and u in accountid_to_name.values()]
            usuarios_lista = ["Todos"] + sorted(usuarios_validos)
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
    from src.jira_conexion import jira
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
    # Optimización: cargar TODAS las historias pero de forma más eficiente
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

    # Mensaje informativo sobre optimización de primera carga
    st.caption("ℹ️ **Primera carga optimizada**: Mostrando 30 historias más recientes. Usa 'Actualizar' para datos completos.")

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




# === ENTREGABLES POSTVENTAS ===
if opcion == "Entregables Postventas":
    from src.jira_conexion import jira
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
                issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
                with open(cache_file_tal_entregable, 'wb') as f:
                    pickle.dump(issues_tal, f)
        else:
            issues_tal = traer_todos_los_issues(jira, 'project = TAL AND issuetype = Historia', fields)
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
                with open(cache_file_rep_entregable, 'wb') as f:
                    pickle.dump(issues_rep, f)
        else:
            issues_rep = traer_todos_los_issues(jira, 'project = REP AND issuetype = Historia', fields)
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



#Bugsmaipu
if opcion == "BUGS":
    import re
    import unicodedata
    import pandas as pd
    import streamlit as st
    from src.jira_conexion import jira
    import json
    import os
    import time
    from datetime import datetime, timedelta, date

    st.header("🐛 Bugs - Análisis por Mes")
    st.caption("📊 Métricas de bugs del proyecto BUG con clasificación por tipo y épicas")

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
        return epic_key in [epic["rn"] for epic in epicas_relevantes]
    
    def es_bloqueante_por_prioridad(priority):
        if not priority:
            return False
        priority_str = _strip(priority).upper()
        return "MUY ALTA" in priority_str or "HIGHEST" in priority_str or "CRITICAL" in priority_str
    
    def _obtener_nombre_epica(epic_key):
        if not epic_key:
            return "Sin épica"
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
            
            
            # Buscar fechas clave
            fecha_salida_to_do = None
            fecha_entrada_validacion_qa = None
            fecha_entrada_aprobado_qa = None
            
            for history in histories:
                created = pd.to_datetime(history.get("created", ""), errors="coerce")
                if pd.isna(created):
                    continue
                
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        from_status = item.get("fromString", "").strip()
                        to_status = item.get("toString", "").strip()
                        
                        # Capturar salida de estado inicial (primera vez que sale de estado inicial)
                        if from_status in ["To Do", "Por Hacer"] and fecha_salida_to_do is None:
                            fecha_salida_to_do = created
                        
                        # Capturar entrada a "EN VALIDACIÓN QA" (primera vez)
                        if to_status == "EN VALIDACIÓN QA" and fecha_entrada_validacion_qa is None:
                            fecha_entrada_validacion_qa = created
                        
                        # Capturar entrada a "APROBADO POR QA" (primera vez)
                        if to_status == "APROBADO POR QA" and fecha_entrada_aprobado_qa is None:
                            fecha_entrada_aprobado_qa = created
            
            # Calcular días laborables (excluyendo sábados, domingos y feriados)
            def calcular_dias_laborables(fecha_inicio, fecha_fin):
                if pd.isna(fecha_inicio) or pd.isna(fecha_fin):
                    return 0
                
                dias = 0
                fecha_actual = fecha_inicio.date()
                fecha_final = fecha_fin.date()
                
                # Lista de feriados (Argentina 2025 - ajustar según necesidad)
                feriados = [
                    date(2025, 1, 1),   # Año Nuevo
                    date(2025, 2, 24),  # Carnaval
                    date(2025, 2, 25),  # Carnaval
                    date(2025, 3, 24),  # Día de la Memoria
                    date(2025, 4, 2),   # Día del Veterano
                    date(2025, 4, 18),  # Viernes Santo
                    date(2025, 5, 1),   # Día del Trabajador
                    date(2025, 5, 25),  # Día de la Revolución de Mayo
                    date(2025, 6, 16),  # Día de la Bandera
                    date(2025, 6, 20),  # Paso a la Inmortalidad del Gral. Güemes
                    date(2025, 7, 9),   # Día de la Independencia
                    date(2025, 8, 17),  # Paso a la Inmortalidad del Gral. San Martín
                    date(2025, 10, 12), # Día del Respeto a la Diversidad Cultural
                    date(2025, 11, 24), # Día de la Soberanía Nacional
                    date(2025, 12, 8),  # Inmaculada Concepción de María
                    date(2025, 12, 25), # Navidad
                ]
                
                while fecha_actual <= fecha_final:
                    # Excluir sábados (5), domingos (6) y feriados
                    if fecha_actual.weekday() < 5 and fecha_actual not in feriados:
                        dias += 1
                    fecha_actual += timedelta(days=1)
                
                return dias
            
            # Calcular los dos períodos solicitados
            # 1. De "To Do" a "EN VALIDACIÓN QA"
            if fecha_salida_to_do and fecha_entrada_validacion_qa:
                dias_to_qa = calcular_dias_laborables(fecha_salida_to_do, fecha_entrada_validacion_qa)
                resultado_to_qa = f"{dias_to_qa}d" if dias_to_qa > 0 else "N/A"
            else:
                resultado_to_qa = "N/A"
            
            # 2. De "To Do" a "APROBADO POR QA"
            if fecha_salida_to_do and fecha_entrada_aprobado_qa:
                dias_to_approved = calcular_dias_laborables(fecha_salida_to_do, fecha_entrada_aprobado_qa)
                resultado_to_approved = f"{dias_to_approved}d" if dias_to_approved > 0 else "N/A"
            else:
                resultado_to_approved = "N/A"
            
            return resultado_to_qa, resultado_to_approved
            
        except Exception as e:
            return "N/A", "N/A"

    # ==========================
    # CARGA DE DATOS
    # ==========================
    
    # Cargar épicas relevantes
    try:
        with open("data/epicas_relevantes.json", "r", encoding="utf-8") as f:
            epicas_relevantes = json.load(f)
    except Exception as e:
        st.error(f"❌ No se pudo cargar el archivo epicas_relevantes.json: {e}")
        st.stop()
    
    # JQL y campos
    jql = 'project = BUG AND created >= "2025-01-01"'
    fields = "key,created,priority,issuetype,summary,status,labels,parent,customfield_10016"
    
    # Cargar issues con changelog para calcular tiempos
    st.info("🔄 Cargando bugs desde Jira...")
    issues = []
    start_at = 0
    max_results = 100
    
    while True:
        try:
            endpoint = f'search?jql={jql}&fields={fields}&startAt={start_at}&maxResults={max_results}'
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            
            # Enriquecer cada issue con changelog
            for issue in batch:
                try:
                    issue_key = issue.get("key", "")
                    changelog_endpoint = f'issue/{issue_key}?expand=changelog&fields={fields}'
                    enriched_issue = jira._get_json(changelog_endpoint)
                    issues.append(enriched_issue)
                except Exception as e:
                    # Si falla el changelog, usar la issue sin enriquecer
                    issues.append(issue)
            
            if len(batch) < max_results:
                break
            start_at += max_results
        except Exception as e:
            st.error(f"❌ Error cargando datos: {e}")
            break
    
    if not issues:
        st.warning("⚠️ No se encontraron bugs")
        st.stop()
    
    st.success(f"✅ Cargados {len(issues)} bugs")
    
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
        
        tabla_transpuesta[mes_nombre] = [
            int(row["Q_Mensual"]),
            int(row["Q_KINETIC"]),
            int(row["Q_MEJORA"]),
            int(row["Q_Bugs_EVOLTIS"]),
            int(row["Q_Bloqueantes"]),
            cumplimiento,
            sla_qa_promedio,
            sla_approved_promedio
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

    # ----------------------------
    # Helpers
    # ----------------------------
    def traer_todas_las_issues(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
        while True:
            endpoint = f'search?jql={jql}&fields={fields}&startAt={start_at}&maxResults={max_results}'
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    def _strip(s: str) -> str:
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
        if any(k in p for k in ["critical","critica","highest","muy alta","bloqueante","blocker"]): return "Muy alta"
        if "lowest" in p or "muy baja" in p: return "Muy baja"
        if "high" in p or "alta" in p:       return "Alta"
        if "low" in p or "baja" in p:        return "Baja"
        if "medium" in p or "media" in p or "normal" in p: return "Media"
        return "Media"

    def es_bug_type(name: str) -> bool:
        n = _strip(name)
        return any(k in n for k in ["bug", "error", "defecto", "incidencia"])

    def proyecto_por_prefijo_key(key: str) -> str:
        k = (key or "").upper()
        if k.startswith("TAL-"): return "Taller"
        if k.startswith("REP-"): return "Repuestos"
        if k.startswith("ATI-"): return "ATI"
        return ""

    def proyecto_por_prefijo_summary(summary: str) -> str:
        m = re.match(r"^\s*\[\s*(REP|TAL|ATI)\s*\]", (summary or ""), flags=re.IGNORECASE)
        if not m: return ""
        tag = m.group(1).upper()
        return {"REP": "Repuestos", "TAL": "Taller", "ATI": "ATI"}[tag]

    def get_issue_type(key, cache):
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
        try:
            fields = jira._get_json("field")
            candidatos = []
            for f in fields:
                name = (f.get("name") or "").strip().lower()
                key  = (f.get("key") or f.get("id") or "").strip()
                if any(x in name for x in ["epic link", "enlace épico", "enlace epico", "epik link"]):
                    candidatos.append(key)
            for c in candidatos:
                if c.startswith("customfield_"):
                    return c
            return candidatos[0] if candidatos else ""
        except Exception:
            return ""

    def calcular_dias_laborables(fecha_inicio, fecha_fin):
        """Calcula días laborables entre dos fechas, excluyendo fines de semana y feriados argentinos 2025"""
        if not fecha_inicio or not fecha_fin:
            return 0
        
        # Feriados argentinos 2025
        feriados_2025 = [
            date(2025, 1, 1),   # Año Nuevo
            date(2025, 2, 20),  # Carnaval
            date(2025, 2, 21),  # Carnaval
            date(2025, 3, 24),  # Día Nacional de la Memoria
            date(2025, 4, 2),   # Viernes Santo
            date(2025, 5, 1),   # Día del Trabajador
            date(2025, 5, 25),  # Día de la Revolución de Mayo
            date(2025, 6, 17),  # Paso a la Inmortalidad del Gral. Martín Miguel de Güemes
            date(2025, 6, 20),  # Paso a la Inmortalidad del Gral. Manuel Belgrano
            date(2025, 7, 9),   # Día de la Independencia
            date(2025, 12, 8),  # Inmaculada Concepción de María
            date(2025, 12, 25), # Navidad
        ]
        
        dias_laborables = 0
        fecha_actual = fecha_inicio
        
        while fecha_actual <= fecha_fin:
            # Excluir sábados (5) y domingos (6)
            if fecha_actual.weekday() < 5 and fecha_actual not in feriados_2025:
                dias_laborables += 1
            fecha_actual += timedelta(days=1)
        
        return dias_laborables

    def _calcular_tiempos_estado(issue):
        """Calcula tiempos de SLA desde To Do hasta EN VALIDACIÓN QA y APROBADO POR QA"""
        try:
            changelog = issue.get("changelog", {}).get("histories", [])
            if not changelog:
                return {"sla_validacion_qa": "N/A", "sla_aprobado_qa": "N/A"}
            
            # Buscar primera salida de "To Do" o "Por Hacer"
            fecha_salida_todo = None
            for history in changelog:
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        from_string = item.get("fromString", "").strip()
                        to_string = item.get("toString", "").strip()
                        
                        # Buscar salida de To Do o Por Hacer
                        if (from_string.lower() in ["to do", "por hacer"] and 
                            to_string.lower() not in ["to do", "por hacer"]):
                            fecha_salida_todo = datetime.strptime(history["created"], "%Y-%m-%dT%H:%M:%S.%f%z").date()
                            break
                if fecha_salida_todo:
                    break
            
            if not fecha_salida_todo:
                return {"sla_validacion_qa": "N/A", "sla_aprobado_qa": "N/A"}
            
            # Buscar entrada a "EN VALIDACIÓN QA"
            fecha_validacion_qa = None
            for history in changelog:
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        to_string = item.get("toString", "").strip()
                        if to_string.lower() == "en validación qa":
                            fecha_validacion_qa = datetime.strptime(history["created"], "%Y-%m-%dT%H:%M:%S.%f%z").date()
                            break
                if fecha_validacion_qa:
                    break
            
            # Buscar entrada a "APROBADO POR QA"
            fecha_aprobado_qa = None
            for history in changelog:
                for item in history.get("items", []):
                    if item.get("field") == "status":
                        to_string = item.get("toString", "").strip()
                        if to_string.lower() == "aprobado por qa":
                            fecha_aprobado_qa = datetime.strptime(history["created"], "%Y-%m-%dT%H:%M:%S.%f%z").date()
                            break
                if fecha_aprobado_qa:
                    break
            
            # Calcular SLA
            sla_validacion = calcular_dias_laborables(fecha_salida_todo, fecha_validacion_qa) if fecha_validacion_qa else "N/A"
            sla_aprobado = calcular_dias_laborables(fecha_salida_todo, fecha_aprobado_qa) if fecha_aprobado_qa else "N/A"
            
            return {"sla_validacion_qa": sla_validacion, "sla_aprobado_qa": sla_aprobado}
            
        except Exception:
            return {"sla_validacion_qa": "N/A", "sla_aprobado_qa": "N/A"}

    # ----------------------------
    # CONFIGURACIÓN
    # ----------------------------
    MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    PRIORIDADES_ORDEN = ["Muy alta", "Alta", "Media", "Baja", "Muy baja"]

    # ----------------------------
    # Consulta a Jira (incluye STATUS) y armado base
    # ----------------------------
    EPIC_FIELD = detectar_campo_epic_link()
    # Limitar a últimos 6 meses para optimizar (ajustable según necesidad)
    fecha_limite_bugs = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    jql = f'project = BUG AND created >= "{fecha_limite_bugs}"'
    fields = "key,created,priority,issuetype,issuelinks,summary,status" + (f",{EPIC_FIELD}" if EPIC_FIELD else "")

    try:
        # Uso de cache para acelerar cargas repetidas de la pestaña Bugs
        issues = cargar_issues_jira_cache(jql, fields, "bugs_completo")
    except Exception as e:
        st.error(f"Error consultando Jira: {e}")
        issues = []

    # Cache de procesamiento de enlaces (la parte más costosa)
    cache_enlaces_key = "bugs_enlaces_completo"
    cache_enlaces_file = cache_path(cache_enlaces_key, 'pkl')
    
    try:
        if os.path.exists(cache_enlaces_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_enlaces_file))
            if (datetime.now() - mtime) < timedelta(hours=48):  # Cache de 48h para enlaces
                with open(cache_enlaces_file, 'rb') as f:
                    cache_enlaces_data = pickle.load(f)
                    rows = cache_enlaces_data['rows']
                    excluidos = cache_enlaces_data['excluidos']
                    type_cache = cache_enlaces_data['type_cache']
                    links_cache = cache_enlaces_data['links_cache']
                    summary_cache = cache_enlaces_data['summary_cache']
                procesamiento_enlaces_cacheado = True
            else:
                procesamiento_enlaces_cacheado = False
        else:
            procesamiento_enlaces_cacheado = False
    except Exception:
        procesamiento_enlaces_cacheado = False

    if not procesamiento_enlaces_cacheado:
        type_cache, links_cache, summary_cache = {}, {}, {}
        rows = []
        excluidos = []   # dicts: {"Clave","AñoMes","Mes"}
        
        for it in issues:
            f = it.get("fields") or {}
            itype = ((f.get("issuetype") or {}).get("name") or "")
            if not es_bug_type(itype):
                continue

            created_dt = pd.to_datetime(f.get("created"), errors="coerce")
            if pd.isna(created_dt):
                continue

            prio = normalizar_prioridad((f.get("priority") or {}).get("name"))
            summary = f.get("summary") or ""
            status_name = ((f.get("status") or {}).get("name") or "").strip()

            epic_val = ""
            if EPIC_FIELD:
                v = f.get(EPIC_FIELD)
                if isinstance(v, str):
                    epic_val = v.strip().upper()
                elif isinstance(v, dict):
                    epic_val = ((v.get("key") or v.get("id") or "") or "").upper()

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
                        pj_by_name = proyecto_por_prefijo_summary(summary)
                        if pj_by_name:
                            proyecto = pj_by_name
                            tipo_final = "Bug"
                        else:
                            tipo_final = "Excluir"

            elif tiene_hu:
                proyectos_de_hu = {proyecto_por_prefijo_key(k) for k in direct_story_keys}
                proyectos_de_hu.discard("")
                if len(proyectos_de_hu) == 1:
                    proyecto = list(proyectos_de_hu)[0]
                    tipo_final = "Mejora"
                else:
                    tipo_final = "Excluir"
            else:
                pj_by_name = proyecto_por_prefijo_summary(summary)
                if pj_by_name:
                    proyecto = pj_by_name
                    tipo_final = "Bug"
                else:
                    tipo_final = "Excluir"

            anio, mes = int(created_dt.year), int(created_dt.month)
            anio_mes = f"{anio}-{mes:02d}"
            mes_txt  = f"{MESES_ES[mes]} {anio}"

            if tipo_final == "Excluir":
                excluidos.append({"Clave": it.get("key",""), "AñoMes": anio_mes, "Mes": mes_txt})
            else:
                rows.append({
                "Clave": it.get("key", ""),
                "Creado": created_dt,
                "AñoMes": anio_mes,
                "Mes": mes_txt,
                "Prioridad": prio,
                "Proyecto": proyecto,
                "Tipo": tipo_final,
                "Summary": summary,
                "Epic": epic_val,
                "Status": status_name,
            })

        # Guardar cache de enlaces procesados (fuera del bucle, dentro del if)
        try:
            cache_enlaces_data = {
                'rows': rows,
                'excluidos': excluidos,
                'type_cache': type_cache,
                'links_cache': links_cache,
                'summary_cache': summary_cache
            }
            with open(cache_enlaces_file, 'wb') as f:
                pickle.dump(cache_enlaces_data, f)
        except Exception as e:
            st.warning(f"No se pudo guardar cache de enlaces: {e}")

    # Aviso de excluidos (texto)

    if not rows and not excluidos:
        st.info("No hay datos para mostrar con las condiciones actuales.")
        st.stop()

    # ----------------------------
    # DataFrame base simplificado
    # ----------------------------
    df_all = pd.DataFrame(rows).drop_duplicates(subset=["Clave"]).sort_values("AñoMes") if rows else pd.DataFrame(columns=["AñoMes","Mes"])
    meses_disp = (df_all[["AñoMes","Mes"]].drop_duplicates().sort_values("AñoMes")
                  if not df_all.empty else pd.DataFrame([{"AñoMes":"0000-00","Mes":"(sin datos)"}]))
    inv = dict(zip(meses_disp["Mes"], meses_disp["AñoMes"]))

    # ----------------------------
    # Buckets de estado + utilidades
    # ----------------------------
    BUCKETS = [
        "POR HACER",
        "EN VALIDACION QA",
        "ASIGNADOS A BACKLOG",
        "APROBADOS POR QA",
        "ASIGNADO A DESARROLLO",
        "CERRADOS",
    ]
    def bucket_estado(status_name: str) -> str:
        n = _strip(status_name)
        if "backlog" in n:
            return "ASIGNADOS A BACKLOG"
        if ("por hacer" in n) or ("to do" in n) or ("pendiente" in n):
            return "POR HACER"
        if ("validacion" in n and "qa" in n) or ("en validacion qa" in n):
            return "EN VALIDACION QA"
        if ("aprobado" in n and "qa" in n) or ("aprobados por qa" in n) or ("validado qa" in n):
            return "APROBADOS POR QA"
        if ("desarrollo" in n) or ("in progress" in n) or ("asignado a desarrollo" in n):
            return "ASIGNADO A DESARROLLO"
        if any(x in n for x in ["cerrado","cerrada","done","closed","resuelto","resuelta"]):
            return "CERRADOS"
        return ""

    def es_bloqueante_por_prioridad(name: str, summary: str = "") -> bool:
        n = (_strip(name) + " " + _strip(summary)).strip()
        return ("bloqueante" in n) or ("blocker" in n) or (re.search(r"\bp0\b", n) is not None)

    # ----------------------------
    # TABLA TRANSPUESTA MENSUAL
    # ----------------------------
    # Procesar datos para tabla transpuesta
    tabla_transpuesta = {}
    
    for mes in meses_disp["Mes"]:
        if mes == "(sin datos)":
            continue
            
        bugs_mes = df_all[df_all["Mes"] == mes] if not df_all.empty else pd.DataFrame()
        
        # Métricas básicas
        pendientes = len(bugs_mes[bugs_mes["Status"].str.contains("POR HACER|ASIGNADOS A BACKLOG|ASIGNADO A DESARROLLO|EN VALIDACION QA", case=False, na=False)])
        cerrados = len(bugs_mes[bugs_mes["Status"].str.contains("CERRADOS|APROBADOS POR QA", case=False, na=False)])
        total = len(bugs_mes)
        cumplimiento = round((cerrados / total * 100), 1) if total > 0 else 0
        
        # Métricas por tipo
        mejoras = len(bugs_mes[bugs_mes["Tipo"] == "MEJORA"])
        bugs_otras = len(bugs_mes[bugs_mes["Tipo"] == "BUG_OTRAS"])
        bugs_entregables = len(bugs_mes[bugs_mes["Tipo"] == "BUG_ENTREGABLE"])
        bugs_bloqueantes = len(bugs_mes[bugs_mes["Tipo"] == "BLOQUEANTE"])
        
        # Calcular SLA promedio para el mes
        sla_validacion_qa = "N/A"
        sla_aprobado_qa = "N/A"
        
        if not bugs_mes.empty:
            # Obtener issues con changelog para calcular SLA
            issues_mes = []
            for _, row in bugs_mes.iterrows():
                issue_key = row["Clave"]
                # Buscar issue en la lista original
                for issue in issues:
                    if issue.get("key") == issue_key:
                        issues_mes.append(issue)
                        break
            
            # Calcular SLA promedio
            slas_validacion = []
            slas_aprobado = []
            
            for issue in issues_mes:
                sla_data = _calcular_tiempos_estado(issue)
                if sla_data["sla_validacion_qa"] != "N/A":
                    slas_validacion.append(sla_data["sla_validacion_qa"])
                if sla_data["sla_aprobado_qa"] != "N/A":
                    slas_aprobado.append(sla_data["sla_aprobado_qa"])
            
            if slas_validacion:
                sla_validacion_qa = round(sum(slas_validacion) / len(slas_validacion), 1)
            if slas_aprobado:
                sla_aprobado_qa = round(sum(slas_aprobado) / len(slas_aprobado), 1)
        
        tabla_transpuesta[mes] = {
            "Pendientes": pendientes,
            "Cerrados": cerrados,
            "% Cumplimiento": cumplimiento,
            "Mejoras": mejoras,
            "Bugs Otras Funcionalidades": bugs_otras,
            "Bugs de Entregables": bugs_entregables,
            "Bugs Bloqueantes": bugs_bloqueantes,
            "SLA Validación QA": sla_validacion_qa,
            "SLA Aprobado por QA": sla_aprobado_qa
        }

    # Tabla transpuesta eliminada - usando la tabla original del código

    # ----------------------------
    # DESPLEGABLES POR MES
    # ----------------------------
    for mes in meses_disp["Mes"]:
        if mes == "(sin datos)":
            continue
            
        bugs_mes = df_all[df_all["Mes"] == mes] if not df_all.empty else pd.DataFrame()
        
        if not bugs_mes.empty:
            with st.expander(f"📅 {mes} - {len(bugs_mes)} bugs"):
                # Mejoras
                mejoras_mes = bugs_mes[bugs_mes["Tipo"] == "MEJORA"]
                if not mejoras_mes.empty:
                    st.write("**✅ Mejoras:**")
                    for _, row in mejoras_mes.iterrows():
                        st.write(f"• {row['Clave']}: {row['Summary']}")
                
                # Bugs Otras Funcionalidades
                bugs_otras_mes = bugs_mes[bugs_mes["Tipo"] == "BUG_OTRAS"]
                if not bugs_otras_mes.empty:
                    st.write("**🐛 Bugs Otras Funcionalidades:**")
                    for _, row in bugs_otras_mes.iterrows():
                        st.write(f"• {row['Clave']}: {row['Summary']}")
                
                # Bugs de Entregables
                bugs_entregables_mes = bugs_mes[bugs_mes["Tipo"] == "BUG_ENTREGABLE"]
                if not bugs_entregables_mes.empty:
                    st.write("**📦 Bugs de Entregables:**")
                    for _, row in bugs_entregables_mes.iterrows():
                        st.write(f"• {row['Clave']}: {row['Summary']}")
                
                # Bugs Bloqueantes
                bugs_bloqueantes_mes = bugs_mes[bugs_mes["Tipo"] == "BLOQUEANTE"]
                if not bugs_bloqueantes_mes.empty:
                    st.write("**🚨 Bugs Bloqueantes:**")
                    for _, row in bugs_bloqueantes_mes.iterrows():
                        st.write(f"• {row['Clave']}: {row['Summary']}")


    # ----------------------------
    # BUGS INTERNOS POR MES
    # ----------------------------
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

    try:
        # Cargar bugs de TAL, REP, ATI
        jql_tal = 'project = TAL AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'
        jql_rep = 'project = REP AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'
        jql_ati = 'project = ATI AND issuetype in (Error, Bug) AND created >= "2025-01-01" ORDER BY created ASC'
        
        fields_bugs = "key,created,issuelinks,summary,status"
        
        bugs_tal = traer_todas_las_issues_global(jira, jql_tal, fields_bugs, max_results=5000)
        bugs_rep = traer_todas_las_issues_global(jira, jql_rep, fields_bugs, max_results=5000)
        bugs_ati = traer_todas_las_issues_global(jira, jql_ati, fields_bugs, max_results=5000)
        
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
                mes_nombre = MESES_ES[fecha.month]
                datos_internos.append({"Proyecto": "TAL", "Mes": mes_nombre, "Cantidad": 1})
        
        for bug in bugs_rep_internos:
            created = bug.get("fields", {}).get("created", "")
            if created:
                fecha = datetime.strptime(created[:10], "%Y-%m-%d")
                mes_nombre = MESES_ES[fecha.month]
                datos_internos.append({"Proyecto": "REP", "Mes": mes_nombre, "Cantidad": 1})
        
        for bug in bugs_ati_internos:
            created = bug.get("fields", {}).get("created", "")
            if created:
                fecha = datetime.strptime(created[:10], "%Y-%m-%d")
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

    # ----------------------------
    # BUGS INTERNOS POR USUARIO
    # ----------------------------
    st.subheader("👥 Bugs Internos por Usuario")
    st.caption("Cantidad de bugs internos por usuario y mes (bugs vinculados a historias, asignado por historia)")

    try:
        # Cargar mapeo de usuarios
        with open('data/accountid_to_name.json', 'r', encoding='utf-8') as f:
            accountid_to_name = json.load(f)

        # Cargar historias de TAL, REP, ATI
        jql_historias_tal = 'project = TAL AND issuetype in ("Historia", "Story", "User Story") AND created >= "2025-01-01"'
        jql_historias_rep = 'project = REP AND issuetype in ("Historia", "Story", "User Story") AND created >= "2025-01-01"'
        jql_historias_ati = 'project = ATI AND issuetype in ("Historia", "Story", "User Story") AND created >= "2025-01-01"'
        
        fields_historias = "key,assignee,summary,status"
        
        historias_tal = traer_todas_las_issues_global(jira, jql_historias_tal, fields_historias, max_results=5000)
        historias_rep = traer_todas_las_issues_global(jira, jql_historias_rep, fields_historias, max_results=5000)
        historias_ati = traer_todas_las_issues_global(jira, jql_historias_ati, fields_historias, max_results=5000)
        
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
            mes_nombre = MESES_ES[fecha.month]
            
            # Buscar historia vinculada
            issuelinks = bug.get("fields", {}).get("issuelinks", [])
            usuario_asignado = "Sin historia vinculada"
            
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
            
            # Si no hay historia vinculada, usar asignado del bug como fallback
            if usuario_asignado == "Sin historia vinculada":
                assignee_bug = bug.get("fields", {}).get("assignee")
                if assignee_bug:
                    account_id = assignee_bug.get("accountId", "")
                    usuario_asignado = accountid_to_name.get(account_id, "") if account_id else ""
            
            # Solo agregar si hay usuario asignado (no incluir "Sin asignar")
            if usuario_asignado and usuario_asignado != "Sin historia vinculada":
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

#Historico postventas
# === PESTAÑA HISTÓRICO POSTVENTA (CON FILTRO RN + UAT POR EPIC LINK + FIX PROMEDIO HS) ===
if opcion == "Histórico Postventa":
    import re
    import unicodedata
    import pandas as pd
    import streamlit as st
    import time
    from src.jira_conexion import jira

    # ------------------ Helpers ------------------
    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    def _status_norm(s: str) -> str:
        return (s or "").strip().lower()

    def _safe_issue_key(iss) -> str:
        return (iss.get("key") or iss.get("id") or "") if isinstance(iss, dict) else ""

    # Función _unwrap_issue duplicada eliminada

    def traer_todos_las_issues(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
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
        issues, start_at = [], 0
        while True:
            endpoint = (f'search?jql={jql}&fields={fields}'
                        f'&expand=changelog&startAt={start_at}&maxResults={max_results}')
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    # --- FIX: cálculo robusto de horas desde changelog (con fallbacks) ---
    def _bug_resolution_hours(bug_issue) -> float | None:
        f = bug_issue.get("fields", {}) or {}
        created = pd.to_datetime(f.get("created"), errors="coerce")
        resolution = pd.to_datetime(f.get("resolutiondate"), errors="coerce")
        updated = pd.to_datetime(f.get("updated"), errors="coerce")

        TODO_PATTERNS     = ("to do", "por hacer", "pendiente", "backlog", "asignados a backlog")
        PROGRESS_PATTERNS = ("in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo")
        DONE_PATTERNS     = ("cerrad", "done", "resuelt", "hech", "closed")

        start_dt, end_dt, last_hist_dt = None, None, None
        histories = (bug_issue.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))

        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            last_hist_dt = h_created if pd.notna(h_created) else last_hist_dt
            for it in hist.get("items", []) or []:
                if _status_norm(it.get("field")) != "status":
                    continue
                to_str  = _status_norm(it.get("toString"))
                from_str= _status_norm(it.get("fromString"))

                if start_dt is None:
                    sale_de_todo  = any(p in from_str for p in TODO_PATTERNS) and not any(p in to_str for p in TODO_PATTERNS)
                    entra_en_prog = any(p in to_str for p in PROGRESS_PATTERNS)
                    if sale_de_todo or entra_en_prog:
                        start_dt = h_created

                if end_dt is None and any(p in to_str for p in DONE_PATTERNS):
                    end_dt = h_created

            if start_dt is not None and end_dt is not None:
                break

        if start_dt is None:
            start_dt = created
        if end_dt is None:
            if pd.notna(resolution):
                end_dt = resolution
            else:
                status_now = _status_norm((f.get("status") or {}).get("name"))
                if any(p in status_now for p in DONE_PATTERNS):
                    end_dt = last_hist_dt or updated

        if pd.isna(start_dt) or pd.isna(end_dt):
            return None

        delta_hs = (end_dt - start_dt).total_seconds() / 3600.0
        return None if delta_hs < 0 else float(delta_hs)

    def _bugs_por_hu(bugs_issues) -> dict:
        """
        Dict { HU_KEY: {"bugs": [bug_key,...], "hrs": [resol_horas,...]} }
        Para bugs de REP/TAL (métrica 'Bugs asociados' + promedio hs).
        """
        por_hu = {}
        for iss in bugs_issues:
            f = iss.get("fields", {}) or {}
            itype = _status_norm((f.get("issuetype", {}) or {}).get("name"))
            if itype not in ("error", "bug", "defecto", "incidencia"):
                continue
            bug_key = iss.get("key", "")
            if not bug_key:
                continue
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

    def detectar_campo_epic_link():
        try:
            fields = jira._get_json("field")
            candidatos = []
            for f in fields:
                name = (f.get("name") or "").strip().lower()
                key  = (f.get("key") or f.get("id") or "").strip()
                if any(x in name for x in ["epic link", "enlace épico", "enlace epico", "epik link"]):
                    candidatos.append(key)
            for c in candidatos:
                if c.startswith("customfield_"):
                    return c
            return candidatos[0] if candidatos else None
        except Exception:
            return None

    def _es_tipo_bug_uat(issuetype_name: str) -> bool:
        n = (issuetype_name or "").lower()
        return any(k in n for k in ("bug", "error", "defecto", "incidencia"))

    # ------------------ Fuente de datos ------------------
    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    # Historias (REP + TAL) → base de RN (con cache)
    fields_hist = ("key,summary,status,project,issuetype,assignee,parent,"
                   "customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated")
    
    # Cache para issues de TAL y REP - OPTIMIZADO para primera carga
    cache_key_tal = "desarrollo_tal_issues"
    cache_key_rep = "desarrollo_rep_issues"
    cache_file_tal = cache_path(cache_key_tal, 'pkl')
    cache_file_rep = cache_path(cache_key_rep, 'pkl')
    
    # Inicializar variable de sesión para controlar carga completa
    if 'historico_carga_completa' not in st.session_state:
        st.session_state.historico_carga_completa = False
    
    # Cargar desde cache o consultar Jira con límites para primera carga rápida
    try:
        if os.path.exists(cache_file_tal) and not st.session_state.historico_carga_completa:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_tal))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_tal, 'rb') as f:
                    issues_tal = pickle.load(f)
            else:
                # Limitar a 50 issues más recientes para primera carga rápida
                issues_tal = traer_todos_las_issues(jira, 'project = TAL AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=50)
                with open(cache_file_tal, 'wb') as f:
                    pickle.dump(issues_tal, f)
        else:
            # Carga completa o primera carga
            if st.session_state.historico_carga_completa:
                # Carga completa: usar el límite máximo de Jira (5000)
                issues_tal = traer_todos_las_issues(jira, 'project = TAL AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=5000)
            else:
                # Primera carga limitada
                issues_tal = traer_todos_las_issues(jira, 'project = TAL AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=50)
            with open(cache_file_tal, 'wb') as f:
                pickle.dump(issues_tal, f)
    except Exception:
        if st.session_state.historico_carga_completa:
            issues_tal = traer_todos_las_issues(jira, 'project = TAL AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=5000)
        else:
            issues_tal = traer_todos_las_issues(jira, 'project = TAL AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=50)
    
    try:
        if os.path.exists(cache_file_rep) and not st.session_state.historico_carga_completa:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_rep))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_rep, 'rb') as f:
                    issues_rep = pickle.load(f)
            else:
                # Limitar a 50 issues más recientes para primera carga rápida
                issues_rep = traer_todos_las_issues(jira, 'project = REP AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=50)
                with open(cache_file_rep, 'wb') as f:
                    pickle.dump(issues_rep, f)
        else:
            # Carga completa o primera carga
            if st.session_state.historico_carga_completa:
                # Carga completa: usar el límite máximo de Jira (5000)
                issues_rep = traer_todos_las_issues(jira, 'project = REP AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=5000)
            else:
                # Primera carga limitada
                issues_rep = traer_todos_las_issues(jira, 'project = REP AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=50)
            with open(cache_file_rep, 'wb') as f:
                pickle.dump(issues_rep, f)
    except Exception:
        if st.session_state.historico_carga_completa:
            issues_rep = traer_todos_las_issues(jira, 'project = REP AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=5000)
        else:
            issues_rep = traer_todos_las_issues(jira, 'project = REP AND issuetype = Historia ORDER BY updated DESC', fields_hist, max_results=50)
    
    issues = issues_tal + issues_rep

    # Desduplico por key
    issues = [_unwrap_issue(iss) for iss in issues]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # Map RN (nombre de épica) → historias y → set de EPIC KEYS (para UAT)
    EPIC_LINK_CAMPO_STORY = "customfield_10016"
    epicas = {}              # { RN_name: {"Historias": [...] } }
    rn_to_epic_keys = {}     # { RN_name: set([EPIC-123,...]) }

    # Filtrar solo issues de postventas (REP y TAL)
    issues_postventas = [i for i in issues if i["fields"]["project"]["key"] in ["REP", "TAL"]]

    for issue in issues_postventas:
        f = issue.get("fields", {}) or {}

        # RN/Épica (nombre) desde parent.summary (o custom)
        epic_name = None
        parent = f.get("parent")
        parent_key = None
        if parent:
            epic_name = (parent.get("summary") or (parent.get("fields") or {}).get("summary"))
            parent_key = (parent.get("key") or (parent.get("fields") or {}).get("key"))
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            epica_custom = f.get(EPIC_LINK_CAMPO_STORY, None)
            if isinstance(epica_custom, dict) and epica_custom.get("value"):
                epic_name = epica_custom["value"]
            elif isinstance(epica_custom, str) and epica_custom:
                epic_name = epica_custom
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            epic_name = "Sin epica"

        summary = f.get("summary", "")
        if "madre" in (summary or "").lower():
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

        epicas.setdefault(epic_name, {"Historias": []})["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos,
        })
        if parent_key:
            rn_to_epic_keys.setdefault(epic_name, set()).add(parent_key)

    # Bugs REP/TAL con changelog (para 'Bugs asociados' y promedio hs) - con cache
    fields_bugs_rep_tal = "key,project,issuetype,status,resolutiondate,assignee,parent,issuelinks,created,updated"
    
    # Cache para bugs de REP y TAL
    cache_key_bugs_rep = "desarrollo_bugs_rep"
    cache_key_bugs_tal = "desarrollo_bugs_tal"
    cache_file_bugs_rep = cache_path(cache_key_bugs_rep, 'pkl')
    cache_file_bugs_tal = cache_path(cache_key_bugs_tal, 'pkl')
    
    try:
        if os.path.exists(cache_file_bugs_rep):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_rep))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_rep, 'rb') as f:
                    bugs_rep = pickle.load(f)
            else:
                # Limitar bugs a 30 más recientes para primera carga rápida
                bugs_rep = traer_bugs_con_changelog(jira, 'project = REP AND issuetype = Error ORDER BY updated DESC', fields_bugs_rep_tal, max_results=30)
                with open(cache_file_bugs_rep, 'wb') as f:
                    pickle.dump(bugs_rep, f)
        else:
            # Primera carga: solo 30 bugs más recientes
            bugs_rep = traer_bugs_con_changelog(jira, 'project = REP AND issuetype = Error ORDER BY updated DESC', fields_bugs_rep_tal, max_results=30)
            with open(cache_file_bugs_rep, 'wb') as f:
                pickle.dump(bugs_rep, f)
    except Exception:
        bugs_rep = traer_bugs_con_changelog(jira, 'project = REP AND issuetype = Error ORDER BY updated DESC', fields_bugs_rep_tal, max_results=30)
    
    try:
        if os.path.exists(cache_file_bugs_tal):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_tal))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_tal, 'rb') as f:
                    bugs_tal = pickle.load(f)
            else:
                # Limitar bugs a 30 más recientes para primera carga rápida
                bugs_tal = traer_bugs_con_changelog(jira, 'project = TAL AND issuetype = Error ORDER BY updated DESC', fields_bugs_rep_tal, max_results=30)
                with open(cache_file_bugs_tal, 'wb') as f:
                    pickle.dump(bugs_tal, f)
        else:
            # Primera carga: solo 30 bugs más recientes
            bugs_tal = traer_bugs_con_changelog(jira, 'project = TAL AND issuetype = Error ORDER BY updated DESC', fields_bugs_rep_tal, max_results=30)
            with open(cache_file_bugs_tal, 'wb') as f:
                pickle.dump(bugs_tal, f)
    except Exception:
        bugs_tal = traer_bugs_con_changelog(jira, 'project = TAL AND issuetype = Error ORDER BY updated DESC', fields_bugs_rep_tal, max_results=30)
    
    bugs_all = bugs_rep + bugs_tal
    mapa_bugs_hu = _bugs_por_hu(bugs_all)

    # BUGS UAT (project = BUG) — SOLO por Epic Link - con cache
    EPIC_FIELD_BUG = detectar_campo_epic_link() or "customfield_10016"
    fields_bugs_uat = f"key,issuetype,created,{EPIC_FIELD_BUG}"
    
    cache_key_bugs_uat = "desarrollo_bugs_uat"
    cache_file_bugs_uat = cache_path(cache_key_bugs_uat, 'pkl')
    
    try:
        if os.path.exists(cache_file_bugs_uat):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_uat))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_uat, 'rb') as f:
                    bugs_uat = pickle.load(f)
            else:
                # Limitar bugs UAT a 20 más recientes para primera carga rápida
                bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat, max_results=20)
                with open(cache_file_bugs_uat, 'wb') as f:
                    pickle.dump(bugs_uat, f)
        else:
            # Primera carga: solo 20 bugs UAT más recientes
            bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat, max_results=20)
            with open(cache_file_bugs_uat, 'wb') as f:
                pickle.dump(bugs_uat, f)
    except Exception:
        bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat, max_results=20)

    epic_to_bugs_uat: dict[str, set] = {}
    for iss in bugs_uat:
        f = iss.get("fields", {}) or {}
        itype = (f.get("issuetype") or {}).get("name") or ""
        if not _es_tipo_bug_uat(itype):
            continue
        bug_key = iss.get("key", "")
        if not bug_key:
            continue
        epic_ref = f.get(EPIC_FIELD_BUG)
        epic_key = ""
        if isinstance(epic_ref, dict):
            epic_key = (epic_ref.get("key") or epic_ref.get("id") or "").strip()
        elif isinstance(epic_ref, str):
            epic_key = epic_ref.strip()
        if epic_key:
            epic_to_bugs_uat.setdefault(epic_key, set()).add(bug_key)

    # ------------------ Tabla de histórico (usa 'epicas_relevantes') - con cache ------------------
    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except Exception:
            return 99

    # Cache para tabla histórica procesada
    cache_key_historico = "historico_tabla_procesada"
    cache_file_historico = cache_path(cache_key_historico, 'pkl')
    
    # Intentar cargar tabla histórica desde cache
    tabla_historico = []
    try:
        if os.path.exists(cache_file_historico):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_historico))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_historico, 'rb') as f:
                    tabla_historico = pickle.load(f)
                    # Verificar si el cache tiene el campo DCR_% (nuevo campo)
                    if tabla_historico and "DCR_%" not in tabla_historico[0]:
                        # Cache antiguo sin DCR, limpiarlo para recalcular
                        os.remove(cache_file_historico)
                        tabla_historico = []
    except Exception:
        pass
    
    # Botón para limpiar cache del histórico
    if st.button("🗑️ Limpiar Cache Histórico", help="Limpia el cache del histórico para regenerar datos"):
        cache_file_historico = cache_path("historico_postventa", 'pkl')
        if os.path.exists(cache_file_historico):
            os.remove(cache_file_historico)
        st.success("✅ Cache del histórico limpiado. Recargando datos...")
        st.rerun()

    # Si no hay cache, procesar tabla histórica
    if not tabla_historico:
        st.info("⏳ **Procesando datos históricos de POSTVENTAS**... Esto puede tomar unos minutos la primera vez.")
        tabla_historico = []
        # Filtrar solo épicas de postventas (REP y TAL), excluir ATI
        epicas_postventas = [e for e in epicas_relevantes if e["rn"].startswith(("REP-", "TAL-"))]
        for epica_rn in epicas_postventas:
            nombre_epica = epica_rn.get("nombre", "")
            mes_entrega = epica_rn.get("mes_entrega", "")
            epic_match = next((rn for rn in epicas if normalize(nombre_epica) == normalize(rn)), None)

            if epic_match:
                data = epicas[epic_match]
                historias = data["Historias"]
                total = len(historias)
                listas_para_implementar = sum(1 for h in historias if h["Estado"] == "lista para implementar")
                porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
                puntos_totales = sum(h.get("Puntos", 0) or 0 for h in historias)

                # Bugs asociados (REP/TAL) + promedio hs
                hu_keys = [h["Clave"] for h in historias if h.get("Clave")]
                bugs_keys_rep_tal, bugs_hrs = [], []
                for hu in hu_keys:
                    info = mapa_bugs_hu.get(hu)
                    if not info:
                        continue
                    bugs_keys_rep_tal.extend(info.get("bugs", []))
                    bugs_hrs.extend(info.get("hrs", []))
                uniq_bugs_rep_tal = sorted(set(bugs_keys_rep_tal))
                bugs_cnt_rep_tal = len(uniq_bugs_rep_tal)
                prom_hrs = round(sum(bugs_hrs) / len(bugs_hrs), 2) if bugs_hrs else None

                # UAT por RN (solo Epic Link)
                candidate_epic_keys = rn_to_epic_keys.get(epic_match, set())
                uat_keys = set()
                for ek in candidate_epic_keys:
                    uat_keys |= epic_to_bugs_uat.get(ek, set())
                uniq_bugs_uat = sorted(uat_keys)
                bugs_cnt_uat = len(uniq_bugs_uat)
                
                # Calcular DCR (Defect Containment Rate) = QBug / (QBug + QUAT) * 100
                total_bugs = bugs_cnt_rep_tal + bugs_cnt_uat
                dcr = round((bugs_cnt_rep_tal / total_bugs * 100), 1) if total_bugs > 0 else 0.0
                    
            else:
                historias = []
                porcentaje_num = 0
                puntos_totales = 0
                uniq_bugs_rep_tal, bugs_cnt_rep_tal, prom_hrs = [], 0, None
                uniq_bugs_uat, bugs_cnt_uat = [], 0
                dcr = 0.0  # Sin datos, DCR = 0

            tabla_historico.append({
                "Épica": nombre_epica,
                "Mes entrega": mes_entrega,
                "%_num": porcentaje_num,
                "Historias": historias,
                "Puntos totales": puntos_totales,
                "Bugs_asociados": bugs_cnt_rep_tal,
                "Bugs_asociados_claves": ", ".join(uniq_bugs_rep_tal),
                "Promedio_resolucion_bugs_hs": prom_hrs,
                "Bugs_pruebas_UAT": bugs_cnt_uat,
                "Bugs_pruebas_UAT_claves": ", ".join(uniq_bugs_uat),
                "DCR_%": dcr,
            })
        
        # Guardar tabla histórica en cache
        try:
            with open(cache_file_historico, 'wb') as f:
                pickle.dump(tabla_historico, f)
        except Exception:
            pass

    tabla_historico = sorted(tabla_historico, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    # ------------------ UI ------------------
    st.markdown("## Histórico de RNs postventa")
    
    # Mostrar información sobre datos limitados en primera carga
    if not tabla_historico:
        st.info("🔄 Cargando datos limitados para primera carga rápida...")
    else:
        if st.session_state.historico_carga_completa:
            st.caption("✅ **Carga completa**: Mostrando TODOS los datos disponibles.")
        else:
            st.caption("ℹ️ **Primera carga optimizada**: Mostrando datos más recientes. Usa 'Actualizar' para datos completos.")
    
    # Leyenda de colores DCR
    st.caption("🎨 **DCR**: 🟢 ≥90% (Excelente) | 🔴 <90% (Necesita mejora)")
    
    # Verificar si hay DCR mal calculado y mostrar advertencia
    dcr_mal_calculado = any(row.get("DCR_%", 0) == 0.0 and row.get("Bugs_asociados", 0) > 0 for row in tabla_historico)
    if dcr_mal_calculado:
        st.warning("⚠️ **DCR mal calculado detectado**. Usa 'Actualizar' para recalcular con la fórmula correcta.")

    # Filtro de entregable (RN)
    colf1, colf2, colf3 = st.columns([2,1,1])
    with colf1:
        buscar_rn = st.text_input("Buscar entregable (RN)", value="", placeholder="Ej: Generar presupuesto")
    with colf2:
        st.caption("Filtra por nombre (ignora acentos y mayúsculas).")
    with colf3:
        # Botón para forzar actualización
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="historico_actualizar"):
            # Activar carga completa
            st.session_state.historico_carga_completa = True
            
            # Limpiar todos los caches relacionados con histórico postventa (comparte cache con desarrollo)
            cache_keys_to_clear = [
                "desarrollo_tal_issues",
                "desarrollo_rep_issues", 
                "desarrollo_bugs_rep",
                "desarrollo_bugs_tal",
                "desarrollo_bugs_uat",
                "historico_tabla_procesada"  # Cache de tabla con nuevo campo DCR
            ]
            
            for cache_key in cache_keys_to_clear:
                cache_file = cache_path(cache_key, 'pkl')
                if os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                    except Exception:
                        pass
            
            st.success("✅ Cache limpiado. Cargando TODOS los datos...")
            st.rerun()

    buscar_norm = normalize(buscar_rn)
    if buscar_norm:
        tabla_filtrada = [r for r in tabla_historico if buscar_norm in normalize(r["Épica"])]
    else:
        tabla_filtrada = tabla_historico

    for row in tabla_filtrada:
        nombre = row["Épica"]
        mes = row["Mes entrega"]
        porcentaje = row["%_num"]
        puntos_totales = row["Puntos totales"]
        historias = row["Historias"]

        bugs_cnt_rep_tal = row["Bugs_asociados"]
        prom_hrs = row["Promedio_resolucion_bugs_hs"]
        prom_txt = f"{prom_hrs:.2f} hs" if prom_hrs is not None else "-"

        bugs_cnt_uat = row.get("Bugs_pruebas_UAT", 0)
        dcr = row.get("DCR_%", 0.0)

        # Color para DCR: Verde si ≥90%, Rojo si <90%
        dcr_color = "🟢" if dcr >= 90 else "🔴"

        expander_title = (
            f"{nombre} | Avance: {porcentaje:.1f}% | {mes} | "
            f"Puntos: {puntos_totales} | Bugs: {bugs_cnt_rep_tal} | UAT: {bugs_cnt_uat} | "
            f"DCR: {dcr_color} {dcr}% | Prom. resolución: {prom_txt}"
        )
        with st.expander(expander_title, expanded=False):
            st.markdown(
                f"**Bugs asociados (REP/TAL):** {bugs_cnt_rep_tal} &nbsp;|&nbsp; "
                f"**Promedio resolución (REP/TAL):** {prom_txt} &nbsp;|&nbsp; "
                f"**Claves REP/TAL:** {row['Bugs_asociados_claves'] or '-'}"
            )
            st.markdown(
                f"**Bugs pruebas UAT (project BUG, Epic Link):** {bugs_cnt_uat} &nbsp;|&nbsp; "
                f"**Claves UAT:** {row.get('Bugs_pruebas_UAT_claves','') or '-'}"
            )
            st.markdown(
                f"**DCR (Defect Containment Rate):** {dcr_color} **{dcr}%** &nbsp;|&nbsp; "
                f"**Fórmula:** QBug / (QBug + QUAT) × 100 = {bugs_cnt_rep_tal} / ({bugs_cnt_rep_tal} + {bugs_cnt_uat}) × 100"
            )
            st.markdown("---")

            if historias:
                for h in historias:
                    estado = h["Estado"]
                    color_estado = (
                        "#39d353" if estado == "lista para implementar"
                        else "#fa4" if "desarroll" in estado
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





# === PESTAÑA VELOCIDAD DE DEVS (NUEVA IMPLEMENTACIÓN) ===
if opcion == "Velocidad de devs":
    import json
    from datetime import datetime
    from urllib.parse import quote_plus
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import altair as alt
    import pandas as pd
    import streamlit as st

    # Conexión JIRA
    try:
        from src.jira_conexion import jira
    except Exception:
        jira = None

    st.header("Velocidad de devs")
    st.caption("📊 **Métricas de productividad de desarrolladores**")

    # ==========================
    #   FUNCIONES MODULARES
    # ==========================
    
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
        return True

    STATUS_TESTING = {
        "en testing", "testing", "qa", "en test", "pruebas", "ready for qa", "ready for testing"
    }

    def _get_points_from_fields(fields: dict) -> float:
        for key in ["customfield_10026", "customfield_10016", "storyPoints"]:
            val = fields.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return 0.0

    # ==========================
    #   CARGA DE DATOS BASE
    # ==========================
    
    # Cargar mapeo de usuarios primero
    with open("data/accountid_to_name.json", "r", encoding="utf-8") as f:
        accountid_to_name = json.load(f)
    
    # Crear diccionario inverso name_to_acc
    name_to_acc = {v: k for k, v in accountid_to_name.items()}

    allowed_names = set(accountid_to_name.values()) | set(name_to_acc.keys())
    
    # Cargar datos de horas (usar el mismo df que las pestañas de horas)
    df_horas = df.copy()  # Usar el df principal que ya tiene Proyecto_logico
    df_horas["Fecha"] = pd.to_datetime(df_horas["Fecha"], errors="coerce")
    df_horas["Mes_dt"] = df_horas["Fecha"].apply(lambda d: _mes_start(d) if pd.notna(d) else pd.NaT)
    
    # Mapear account IDs a nombres legibles
    df_horas["Usuario_nombre"] = df_horas["Usuario"].map(accountid_to_name).fillna(df_horas["Usuario"]).apply(_norm)
    
    # Filtrar solo usuarios que están en el mapeo (desarrolladores válidos)
    df_horas = df_horas[df_horas["Usuario_nombre"].isin(accountid_to_name.values())]
    
    # Agrupar por usuario y mes (sin filtro de proyecto por ahora)
    df_horas_sum = df_horas.groupby(["Usuario_nombre", "Mes_dt"], as_index=False)["Horas"].sum()
    

    # ==========================
    #   UI: SELECTOR DE FECHAS
    # ==========================
    
    st.info("💡 **Cómo usar**: Selecciona las fechas del período que quieres evaluar")
    
    # Inicializar session_state para filtros (últimos 3 meses incluyendo el mes actual)
    if "vel_fecha_inicio" not in st.session_state:
        # Calcular dinámicamente: hace 2 meses desde el mes actual (para tener 3 meses en total)
        hoy = datetime.now()
        hace_dos_meses = hoy - pd.DateOffset(months=2)
        st.session_state["vel_fecha_inicio"] = hace_dos_meses.replace(day=1).date()
    if "vel_fecha_fin" not in st.session_state:
        # Último día del mes actual
        hoy = datetime.now()
        ultimo_dia_mes_actual = (hoy.replace(day=1) + pd.offsets.MonthEnd(0)).date()
        st.session_state["vel_fecha_fin"] = ultimo_dia_mes_actual
    if "vel_proyecto_sel" not in st.session_state:
        st.session_state["vel_proyecto_sel"] = "Todos"
    
    col_fecha1, col_fecha2, col_proj, col_btn = st.columns([1, 1, 1, 1])
    
    # === OPTIMIZACIÓN: Callbacks para evitar recargas innecesarias ===
    def on_fecha_inicio_change():
        st.session_state["vel_fecha_inicio"] = st.session_state["vel_fecha_inicio_input"]
        # NO forzar refresh, solo rerun para aplicar filtros
        
    def on_fecha_fin_change():
        st.session_state["vel_fecha_fin"] = st.session_state["vel_fecha_fin_input"]
        # NO forzar refresh, solo rerun para aplicar filtros
        
    def on_proyecto_change():
        st.session_state["vel_proyecto_sel"] = st.session_state["vel_proyecto_input"]
        # NO forzar refresh al cambiar proyecto, filtrar en memoria
    
    with col_fecha1:
        fecha_inicio = st.date_input(
            "Fecha inicio",
            value=st.session_state["vel_fecha_inicio"],
            help="Fecha de inicio del período a evaluar",
            key="vel_fecha_inicio_input",
            on_change=on_fecha_inicio_change
        )
    with col_fecha2:
        fecha_fin = st.date_input(
            "Fecha fin",
            value=st.session_state["vel_fecha_fin"],
            help="Fecha de fin del período a evaluar",
            key="vel_fecha_fin_input",
            on_change=on_fecha_fin_change
        )
    with col_proj:
        proyecto_sel = st.selectbox(
            "Proyecto", 
            ["Todos", "ATI", "Postventas"], 
            index=["Todos", "ATI", "Postventas"].index(st.session_state["vel_proyecto_sel"]),
            key="vel_proyecto_input",
            on_change=on_proyecto_change
        )
    with col_btn:
        if st.button("🔄 Actualizar datos", help="Fuerza la recarga de datos desde Jira", key="velocidad_actualizar"):
            st.session_state["force_refresh"] = True
            # Limpiar TODOS los caches de velocidad
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith(("velocidad_cache", "calculos_velocidad", "usuarios_validos"))]
            for key in keys_to_clear:
                del st.session_state[key]
            st.success("✅ Actualizando datos...")
            st.rerun()
    
    # === PROTECCIÓN: Cache inteligente con invalidación ===
    cache_key_velocidad = f"velocidad_{proyecto_sel}_{fecha_inicio}_{fecha_fin}"
    
    # Botón adicional para limpiar cache específico
    if st.button("🗑️ Limpiar Cache Velocidad", help="Limpia completamente el cache de velocidad", key="velocidad_limpiar_cache"):
        # Limpiar todos los caches relacionados con velocidad
        import os
        import glob
        
        # Buscar archivos de cache de velocidad
        cache_files = glob.glob("data/cache_velocidad_*")
        for cache_file in cache_files:
            try:
                os.remove(cache_file)
            except Exception:
                pass
        
        # Limpiar session state
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith("velocidad_cache")]
        for key in keys_to_clear:
            del st.session_state[key]
        
        st.success("✅ Cache de velocidad limpiado completamente. Recargando...")
        st.rerun()

    # ==========================
    #   FUNCIÓN: CARGAR DATOS DE JIRA
    # ==========================
    
    def cargar_datos_velocidad(_jira, _fecha_inicio, _fecha_fin, _proyecto_sel, _force_refresh):
        if _jira is None:
            return [], []
        
        # === CACHE PERSISTENTE EN ARCHIVO ===
        cache_key = f"velocidad_data_Todos_{_fecha_inicio}_{_fecha_fin}"
        cache_file = cache_path(cache_key, 'pkl')
        
        # Intentar cargar desde cache de archivo (válido por 24 horas)
        if not _force_refresh and os.path.exists(cache_file):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if (datetime.now() - mtime) < timedelta(hours=48):
                    with open(cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                        st.info(f"✅ Datos cargados desde cache ({len(cache_data['historias'])} historias, {len(cache_data['bugs'])} bugs)")
                        return cache_data['historias'], cache_data['bugs']
            except Exception as e:
                if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
                    print(f"⚠️ Error cargando cache: {e}")
        
        # Si no hay cache válido, cargar desde Jira
        st.info("🔄 Cargando datos desde Jira... Esto puede tomar un momento...")

        # SIEMPRE cargar TODOS los proyectos (se filtrará después en memoria)
        proy_jql = "project in (REP, TAL, ATI)"

        # Buscar TODAS las historias con puntos (sin filtro de fecha)
        jql_hist = f"{proy_jql} AND issuetype = Historia AND (cf[10026] is not EMPTY OR cf[10016] is not EMPTY OR 'Story Points' is not EMPTY)"
        
        jql_bugs = f"{proy_jql} AND issuetype = Error"
        
        FIELDS = "key,summary,status,project,issuetype,assignee,customfield_10026,customfield_10016,storyPoints,statuscategorychangedate,parent,issuelinks,created,updated"
        
        # === PROTECCIÓN: Logs de monitoreo (solo en desarrollo) ===
        if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
            print(f"🔍 VELOCIDAD DEBUG: JQL historias: {jql_hist}")
            print(f"🔍 VELOCIDAD DEBUG: JQL bugs: {jql_bugs}")
            print(f"🔍 VELOCIDAD DEBUG: Período: {_fecha_inicio} a {_fecha_fin}")
            print(f"🔍 VELOCIDAD DEBUG: Proyecto: {_proyecto_sel}")
        
        # Cargar historias con changelog (con filtro de fecha para optimizar)
        
        historias = []
        start_at = 0
        max_issues = 10000  # Sin límite de datos
        
        while True:
            params = {"jql": jql_hist, "fields": FIELDS, "startAt": start_at, "maxResults": 100, "expand": "changelog"}
            data = _jira._get_json("search", params=params)
            batch = data.get("issues", [])
            historias.extend(batch)
            
            if len(batch) < 100 or len(historias) >= max_issues:
                break
            start_at += 100

        # === PROTECCIÓN: Validación de datos mínimos ===
        if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
            print(f"🔍 VELOCIDAD DEBUG: Historias encontradas: {len(historias)}")
        if len(historias) < 5:  # Mínimo esperado
            st.warning(f"⚠️ **ALERTA**: Solo se encontraron {len(historias)} historias. Esto puede indicar un problema con el JQL o los datos de Jira.")
            st.info("💡 **Sugerencia**: Verifica que el proyecto seleccionado tenga historias con puntos asignados.")

        # Cargar bugs
        
        bugs = []
        start_at = 0
        max_bugs = 10000  # Sin límite de datos
        
        while True:
            params = {"jql": jql_bugs, "fields": FIELDS, "startAt": start_at, "maxResults": 100}
            data = _jira._get_json("search", params=params)
            batch = data.get("issues", [])
            bugs.extend(batch)
            if len(batch) < 100 or len(bugs) >= max_bugs:
                break
            start_at += 100
        
        # === PROTECCIÓN: Validación de bugs ===
        if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
            print(f"🔍 VELOCIDAD DEBUG: Bugs encontrados: {len(bugs)}")
        if len(bugs) < 1:  # Mínimo esperado
            st.warning(f"⚠️ **ALERTA**: No se encontraron bugs. Esto puede indicar un problema con el JQL de bugs.")
            st.info("💡 **Sugerencia**: Verifica que el proyecto seleccionado tenga bugs reportados.")
        
        # === PROTECCIÓN: Guardar en cache si los datos son válidos ===
        if len(historias) >= 5:  # Solo cachear si hay datos suficientes
            cache_data = {
                "historias": historias,
                "bugs": bugs,
                "timestamp": pd.Timestamp.now(),
                "proyecto": _proyecto_sel,
                "fecha_inicio": _fecha_inicio,
                "fecha_fin": _fecha_fin
            }
            st.session_state[cache_key_velocidad] = cache_data
            
            # Guardar en archivo persistente
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
                    print(f"🔍 VELOCIDAD DEBUG: Datos guardados en cache de archivo - {len(historias)} historias, {len(bugs)} bugs")
            except Exception as e:
                if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
                    print(f"⚠️ Error guardando cache: {e}")
            
        else:
            if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
                print(f"🔍 VELOCIDAD DEBUG: No se guarda en cache - datos insuficientes")
        
        return historias, bugs

    # ==========================
    #   FUNCIÓN: PROCESAR HISTORIAS
    # ==========================
    
    def procesar_historias(historias, accountid_to_name, name_to_acc):
        rows_issues = []
        
        for iss in historias:
            f = iss.get("fields", {}) or {}
            itype = _norm((f.get("issuetype", {}) or {}).get("name")).lower()
            if itype != "historia":
                continue
            
            proj_key = _norm((f.get("project") or {}).get("key"))
            if not _proy_ok(proj_key, proyecto_sel):
                continue
            
            key = iss.get("key", "")
            pts = _get_points_from_fields(f)
            
            # Buscar owner al momento de testing
            owner_name, owner_id, first_dt = _owner_al_momento_testing(iss, accountid_to_name, name_to_acc)
            
            if pd.notna(first_dt) and pts > 0 and owner_name and owner_id:
                rows_issues.append({
                    "Issue": key,
                    "Puntos": pts,
                    "Usuario_nombre": owner_name,
                    "Mes": _mes_label(_mes_start(first_dt)),
                    "Proyecto": proj_key,
                })
        
        return pd.DataFrame(rows_issues, columns=["Issue", "Puntos", "Usuario_nombre", "Mes", "Proyecto"])

    def _owner_al_momento_testing(iss, accountid_to_name, name_to_acc):
        f = iss.get("fields", {}) or {}
        
        # Usar el assignee actual (quien tiene la historia ahora)
        current_id = (f.get("assignee") or {}).get("accountId")
        current_name = _norm(accountid_to_name.get(current_id) or (f.get("assignee") or {}).get("displayName"))
        
        histories = (iss.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))
        
        # Solo buscar la fecha de testing, no cambiar el assignee
        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            
            # Primera vez que pasa a testing
            for it in hist.get("items", []) or []:
                if _norm(it.get("field")).lower() == "status" and _norm(it.get("toString")).lower() in STATUS_TESTING:
                    if pd.notna(h_created):
                        # Retornar el assignee actual con la fecha de testing
                        return current_name, current_id, h_created
        
        return None, None, None

    # ==========================
    #   FUNCIÓN: PROCESAR BUGS
    # ==========================
    
    def procesar_bugs(bugs, historias_por_dev):
        bug_rows = []
        bugs_extra_rows = []

        bugs_filtrados_por_tipo = 0
        bugs_filtrados_por_proyecto = 0
        bugs_filtrados_por_estado = 0
        bugs_filtrados_por_fecha = 0
        bugs_filtrados_por_asignado = 0
        
        # Debug: recopilar todos los estados únicos de bugs
        estados_bugs_unicos = set()
        
        for iss in bugs:
            f = iss.get("fields", {}) or {}
            itype = _norm((f.get("issuetype", {}) or {}).get("name")).lower()
            if itype != "error":
                bugs_filtrados_por_tipo += 1
                continue

            bug_key = iss.get("key", "")
            bug_proj = _norm((f.get("project") or {}).get("key"))

            if not _proy_ok(bug_proj, proyecto_sel):
                bugs_filtrados_por_proyecto += 1
                continue

            estado_bug = _norm((f.get("status", {}) or {}).get("name")).lower()
            estados_bugs_unicos.add(estado_bug)
            
            # Estados válidos más amplios para bugs (incluyendo estados en español)
            estados_validos = ("resolved", "closed", "done", "cerrado", "resuelto", "hecho", "completado", "finalizado", "terminado", "aprobado", "hecha")
            if estado_bug not in estados_validos:
                bugs_filtrados_por_estado += 1
                continue
            
            fecha_cierre = pd.to_datetime(f.get("statuscategorychangedate", ""), errors="coerce")
            if pd.isna(fecha_cierre):
                bugs_filtrados_por_fecha += 1
                continue

            bug_mes_cierre = _mes_label(_mes_start(fecha_cierre))
            assg = f.get("assignee") or {}
            bug_assignee_id = assg.get("accountId")
            bug_assignee_nm = _norm(accountid_to_name.get(bug_assignee_id) or assg.get("displayName"))

            if not bug_assignee_nm:
                bugs_filtrados_por_asignado += 1
                continue
            
            # Buscar si es bug extra (vinculado a HU del dev)
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

            # Determinar si es bug extra o bug normal
            # Bug extra: NO vinculado a ninguna historia del MISMO desarrollador
            # Bug normal: SÍ vinculado a alguna historia del MISMO desarrollador
            historias_del_dev = historias_por_dev.get(bug_assignee_nm, set())
            
            # Verificar si está vinculado a historias del dev
            is_bug_extra = not bool(candidate_hus & historias_del_dev)
            
            if is_bug_extra:
                # Bug extra: vinculado a historia del mismo dev
                bugs_extra_rows.append({
                    "Issue": bug_key,
                    "Usuario_nombre": bug_assignee_nm,
                    "Mes": bug_mes_cierre,
                    "Proyecto": bug_proj,
                })
            else:
                # Bug normal: no vinculado a historia del dev
                bug_rows.append({
                    "Issue": bug_key,
                    "Usuario_nombre": bug_assignee_nm,
                    "Mes": bug_mes_cierre,
                    "Proyecto": bug_proj,
                })
        
        return bug_rows, bugs_extra_rows

    # ==========================
    #   FUNCIÓN: AGREGAR POR USUARIO/MES
    # ==========================
    
    def agregar_por_usuario_mes(df_issues, bug_rows, bugs_extra_rows, df_horas_sum):
        # Puntos por usuario/mes
        if not df_issues.empty:
            df_puntos = df_issues.groupby(["Usuario_nombre", "Mes"], as_index=False).agg(
                Puntos=("Puntos", "sum"),
                Claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        else:
            df_puntos = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Puntos", "Claves"])

        # Bugs por usuario/mes
        if bug_rows:
            df_bugs = pd.DataFrame(bug_rows)
            df_bugs = df_bugs.groupby(["Usuario_nombre", "Mes"], as_index=False).agg(
                Bugs=("Issue", "count"),
                Bugs_claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        else:
            df_bugs = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Bugs", "Bugs_claves"])
        
        # Bugs extra por usuario/mes
        if bugs_extra_rows:
            df_bugs_extra = pd.DataFrame(bugs_extra_rows)
            df_bugs_extra = df_bugs_extra.groupby(["Usuario_nombre", "Mes"], as_index=False).agg(
                Bugs_resueltos_extra=("Issue", "count"),
                Bugs_extra_claves=("Issue", lambda x: ", ".join(sorted(set(k for k in x if k)))),
            )
        else:
            df_bugs_extra = pd.DataFrame(columns=["Usuario_nombre", "Mes", "Bugs_resueltos_extra", "Bugs_extra_claves"])
        
        # Crear base unificada
        df_puntos["_Mes_dt_aux"] = pd.to_datetime(df_puntos["Mes"], format="%B %Y", errors="coerce")
        
        # Convertir accountids a nombres legibles en df_horas_sum para el merge
        df_horas_sum_legible = df_horas_sum.copy()
        df_horas_sum_legible["Usuario_nombre"] = df_horas_sum_legible["Usuario_nombre"].map(
            lambda x: accountid_to_name.get(x, x) if x in accountid_to_name else x
        )
        
        base_horas = df_horas_sum_legible[["Usuario_nombre", "Mes_dt"]].drop_duplicates() if "Mes_dt" in df_horas_sum_legible.columns else pd.DataFrame(columns=["Usuario_nombre","Mes_dt"])
        base_puntos = df_puntos[["Usuario_nombre", "_Mes_dt_aux"]].rename(columns={"_Mes_dt_aux":"Mes_dt"}).drop_duplicates()
        df_base = pd.concat([base_horas, base_puntos], ignore_index=True).dropna(subset=["Mes_dt"]).drop_duplicates()
        df_base["Mes"] = df_base["Mes_dt"].dt.strftime("%B %Y")

        # Merge todos los datos
        df_merge = df_base.merge(df_horas_sum_legible[["Usuario_nombre","Mes_dt","Horas"]], on=["Usuario_nombre","Mes_dt"], how="left")
        
        # Merge con puntos
        df_merge = df_merge.merge(df_puntos[["Usuario_nombre","Mes","Puntos","Claves"]], on=["Usuario_nombre","Mes"], how="left")

        # Merge con bugs
        df_merge = df_merge.merge(df_bugs, on=["Usuario_nombre", "Mes"], how="left")
        df_merge = df_merge.merge(df_bugs_extra, on=["Usuario_nombre", "Mes"], how="left")

        # Llenar valores faltantes
        for col, fill in [("Horas", 0.0), ("Puntos", 0.0), ("Bugs", 0), ("Bugs_resueltos_extra", 0)]:
            if col in df_merge.columns:
                df_merge[col] = df_merge[col].fillna(fill)
        for col in ["Claves", "Bugs_claves", "Bugs_extra_claves"]:
            if col in df_merge.columns:
                df_merge[col] = df_merge[col].fillna("").astype(str)

        # Calcular velocidad (usando 80% de las horas)
        df_merge["Velocidad"] = df_merge.apply(
            lambda r: round((r["Horas"] * 0.8) / r["Puntos"], 4) if r["Puntos"] > 0 else 0, axis=1
        )
        
        return df_merge

    # ==========================
    #   FUNCIÓN: APLICAR FILTROS
    # ==========================
    
    def aplicar_filtros(df_completo, fecha_inicio, fecha_fin, proyecto_sel):
        # Filtrar por fechas
        df_completo["Mes_dt"] = pd.to_datetime(df_completo["Mes_dt"], errors="coerce")
        fecha_limite_inicio = pd.Timestamp(fecha_inicio)
        fecha_limite_fin = pd.Timestamp(fecha_fin)
        
        df_filtrado = df_completo[
            (df_completo["Mes_dt"] >= fecha_limite_inicio) & 
            (df_completo["Mes_dt"] <= fecha_limite_fin)
        ].copy()
        
        return df_filtrado

    # ==========================
    #   FUNCIÓN: CALCULAR MÉTRICAS FINALES
    # ==========================
    
    def calcular_metricas_finales(df_filtrado):
        def calcular_nota_final(r):
            p = float(r.get("Puntos", 0.0))
            h = float(r.get("Horas", 0.0))
            b = int(r.get("Bugs", 0))
            v = float(r.get("Velocidad", 0.0))
            bex = int(r.get("Bugs_resueltos_extra", 0))

            if p <= 0: 
                return 0.0

            # Calcular puntuación de puntos
            if p < 8: sp = 0.70
            elif 8 <= p < 10: sp = 0.80
            elif 10 <= p < 13: sp = 0.85
            elif 13 <= p < 16: sp = 0.90
            elif 16 <= p <= 19: sp = 1.05
            elif p >= 20: sp = 1.10
            else: sp = 1.00  # p == 16

            # Calcular puntuación de horas
            if h >= 128: 
                sh = 1.00
            elif 100 <= h <= 127: 
                sh = 0.95
            else: 
                sh = 0.70

            # Calcular puntuación de bugs
            if b == 0: 
                sb = 1.00
            elif 1 <= b <= 3: 
                sb = 0.95
            elif 4 <= b <= 5: 
                sb = 0.90
            else: 
                sb = 0.80

            # Calcular puntuación de velocidad
            if v <= 5: sv = 1.10
            elif 6 <= v <= 7: sv = 1.05
            elif abs(v - 8.0) < 1e-9: sv = 1.00
            elif 8 < v <= 10: sv = 0.95
            elif 10 < v <= 12: sv = 0.90
            else: sv = 0.80

            # Calcular puntuación base
            base = (sp * 0.40) + (sh * 0.25) + (sv * 0.25) + (sb * 0.10)

            # Calcular bonus por bugs extra
            if 1 <= bex <= 5: bonus = 0.02
            elif 6 <= bex <= 10: bonus = 0.03
            elif bex > 10: bonus = 0.05
            else: bonus = 0.0

            return round((base + bonus) * 100, 2)

        if not df_filtrado.empty:
            df_filtrado["Nota_final"] = df_filtrado.apply(calcular_nota_final, axis=1)
            # Agregar columna Mes_label para el gráfico
            df_filtrado["Mes_label"] = df_filtrado["Mes_dt"].apply(_mes_label)
        else:
            df_filtrado["Nota_final"] = pd.Series(dtype=float)
            df_filtrado["Mes_label"] = pd.Series(dtype=str)

        return df_filtrado

    # ==========================
    #   FUNCIONES AUXILIARES PARA RANKING
    # ==========================
    
    def _calcular_usuarios_validos(df_final, allowed_names):
        """Calcula los usuarios válidos que tienen puntos"""
        df_final = df_final.copy()
        df_final["Usuario_nombre"] = df_final["Usuario_nombre"].apply(_norm)
        users_with_points = set(
            df_final.loc[df_final["Puntos"] > 0, "Usuario_nombre"].dropna().astype(str)
        )
        return sorted(list(allowed_names & users_with_points))
    
    def _mostrar_selector_usuario(usuarios_validos):
        """Muestra el selector de usuario y maneja la selección"""
        # === OPTIMIZACIÓN: Cache de usuarios para evitar recargas ===
        cache_key_usuarios = f"usuarios_validos_{len(usuarios_validos)}"
        
        # Mantener la selección de usuario si está disponible
        usuario_actual = st.session_state.get("vel_usuario_actual", "Todos")
        
        # Verificar si la lista de usuarios cambió
        usuarios_cache = st.session_state.get(cache_key_usuarios, [])
        if usuarios_cache != usuarios_validos:
            # Lista de usuarios cambió, resetear selección
            usuario_actual = "Todos"
            st.session_state[cache_key_usuarios] = usuarios_validos.copy()
        
        if usuario_actual not in ["Todos"] + usuarios_validos:
            usuario_actual = "Todos"
        
        # Calcular el índice correcto
        if usuario_actual in usuarios_validos:
            index_usuario = usuarios_validos.index(usuario_actual) + 1  # +1 porque "Todos" está en posición 0
        else:
            index_usuario = 0  # "Todos"
            
        # === OPTIMIZACIÓN: Usar on_change para evitar recargas ===
        def on_usuario_change():
            st.session_state["vel_usuario_actual"] = st.session_state["vel_usuario"]
            
        usuario_sel = st.selectbox(
            "Seleccioná usuario", ["Todos"] + usuarios_validos, 
            index=index_usuario,
            key="vel_usuario",
            on_change=on_usuario_change
        )
        
        # Guardar la selección actual
        st.session_state["vel_usuario_actual"] = usuario_sel
        return usuario_sel
    
    def _mostrar_cards_objetivos():
        """Muestra las cards con objetivos y ponderaciones"""
        st.subheader("🎯 Objetivos y Ponderaciones")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            with st.expander("📊 **Puntos** (40%)", expanded=False):
                st.markdown("""
                **Objetivo:** 16 puntos/mes = 100%
                
                **Escala:**
                - ≥20 puntos: 110%
                - 16-19 puntos: 105%
                - 13-15 puntos: 90%
                - 10-12 puntos: 85%
                - 8-9 puntos: 80%
                - <8 puntos: 70%
                """)
        
        with col2:
            with st.expander("⏰ **Horas** (25%)", expanded=False):
                st.markdown("""
                **Objetivo:** ≥128 horas/mes = 100%
                
                **Escala:**
                - ≥128 horas: 100%
                - 100-127 horas: 95%
                - <100 horas: 70%
                """)
        
        with col3:
            with st.expander("🚀 **Velocidad** (25%)", expanded=False):
                st.markdown("""
                **Objetivo:** ≤8 horas/punto = 100%
                
                **Escala:**
                - ≤5 h/punto: 110%
                - 6-7 h/punto: 105%
                - 8 h/punto: 100%
                - 9-10 h/punto: 95%
                - 11-12 h/punto: 90%
                - >12 h/punto: 80%
                """)
        
        with col4:
            with st.expander("🐛 **Bugs** (10%)", expanded=False):
                st.markdown("""
                **Objetivo:** 0 bugs/mes = 100%
                
                **Escala:**
                - 0 bugs: 100%
                - 1-3 bugs: 95%
                - 4-5 bugs: 90%
                - >5 bugs: 80%
                
                **Bonus Bugs Extra:**
                - 1-5 extra: +2%
                - 6-10 extra: +3%
                - >10 extra: +5%
                """)
    
    def _calcular_ranking(df_final, usuarios_validos):
        """Calcula el ranking de desarrolladores"""
        df_rank_src = df_final[df_final["Usuario_nombre"].isin(usuarios_validos)].copy()
        
        if df_rank_src.empty:
            return pd.DataFrame(columns=[
                "Usuario_nombre", "Promedio_puntos", "Promedio_horas", "Promedio_velocidad", 
                "Promedio_bugs", "Promedio_bugs_extra", "Nota_final", "Meses_con_nota_0", "Total_meses"
            ])
        
        # Calcular promedios excluyendo meses con nota final 0
        df_ranking = (
            df_rank_src.groupby("Usuario_nombre", as_index=False)
            .agg(
                Promedio_puntos=("Puntos", "mean"),
                Promedio_horas=("Horas", "mean"),
                Promedio_velocidad=("Velocidad", "mean"),
                Promedio_bugs=("Bugs", "mean"),
                Promedio_bugs_extra=("Bugs_resueltos_extra", "mean"),
                Nota_final=("Nota_final", "mean"),
                # Contar meses con nota 0 para alertas
                Meses_con_nota_0=("Nota_final", lambda x: (x == 0).sum()),
                Total_meses=("Nota_final", "count"),
            )
            .sort_values("Nota_final", ascending=False)
            .reset_index(drop=True)
        )

        # Recalcular promedio de nota final excluyendo meses con nota 0
        df_ranking["Promedio_nota_final"] = df_ranking.apply(
            lambda row: df_rank_src[
                (df_rank_src["Usuario_nombre"] == row["Usuario_nombre"]) & 
                (df_rank_src["Nota_final"] > 0)
            ]["Nota_final"].mean() if row["Meses_con_nota_0"] < row["Total_meses"] else 0, 
            axis=1
        )
        
        return df_ranking
    
    def _mostrar_tabla_ranking(df_ranking, usuario_sel):
        """Muestra la tabla de ranking con formato"""
        if df_ranking.empty:
            return
            
        # Mostrar solo las columnas necesarias (ocultar las de control)
        columnas_mostrar = [
            "Usuario_nombre", "Promedio_puntos", "Promedio_horas", "Promedio_velocidad", 
            "Promedio_bugs", "Promedio_bugs_extra", "Promedio_nota_final"
        ]
        
        # Función para pintar filas con meses en nota 0
        def highlight_zero_months(row):
            # Obtener los valores del DataFrame original
            original_row = df_ranking.loc[row.name]
            if original_row['Meses_con_nota_0'] > 0:
                return ['color: #ffc107'] * len(row)  # Texto amarillo
            else:
                return [''] * len(row)  # Sin color
        
        # Formatear números antes de mostrar
        df_formatted = df_ranking[columnas_mostrar].copy()
        
        # Formatear columnas numéricas con 1 decimal
        df_formatted['Promedio_puntos'] = df_formatted['Promedio_puntos'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_horas'] = df_formatted['Promedio_horas'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_velocidad'] = df_formatted['Promedio_velocidad'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_bugs'] = df_formatted['Promedio_bugs'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_bugs_extra'] = df_formatted['Promedio_bugs_extra'].apply(lambda x: f"{x:.1f}")
        df_formatted['Promedio_nota_final'] = df_formatted['Promedio_nota_final'].apply(lambda x: f"{x:.1f}")
        
        # Mostrar tabla con resaltado y formato
        st.dataframe(
            df_formatted.style.apply(highlight_zero_months, axis=1),
            use_container_width=True, 
            hide_index=True
        )
        
        # Leyenda simple
        st.markdown("**Nota:** El texto en amarillo corresponde a desarrolladores que tienen meses con nota final 0.")
    
    def _mostrar_grafico_ranking(df_ranking, usuario_sel):
        """Muestra el gráfico de ranking general"""
        if usuario_sel != "Todos" or df_ranking.empty:
            return
            
        st.subheader("📊 Velocidad por Desarrollador")
        
        # Preparar datos para el gráfico
        df_grafico_ranking = df_ranking[['Usuario_nombre', 'Promedio_velocidad']].copy()
        df_grafico_ranking = df_grafico_ranking.sort_values('Promedio_velocidad', ascending=False)
        
        # Crear gráfico de barras con Altair
        import altair as alt
        
        # Crear DataFrame con datos y línea de objetivo
        chart_df_ranking = df_grafico_ranking.copy()
        chart_df_ranking['Objetivo'] = 8
        
        # Crear gráfico base
        base_ranking = alt.Chart(chart_df_ranking).add_selection(
            alt.selection_interval(bind='scales')
        )
        
        # Barras de datos
        bars = base_ranking.mark_bar(
            color='#1f77b4',
            opacity=0.7
        ).encode(
            x=alt.X('Usuario_nombre:N', sort=None, title='Desarrolladores'),
            y=alt.Y('Promedio_velocidad:Q', title='Velocidad (horas/punto)')
        )
        
        # Línea de objetivo
        objective_ranking = base_ranking.mark_rule(
            stroke='red',
            strokeDash=[5, 5],
            strokeWidth=2
        ).encode(
            y=alt.datum(8)
        )
        
        # Combinar gráficos
        chart_ranking = (bars + objective_ranking).resolve_scale(
            color='independent'
        ).properties(
            width=600,
            height=400,
            title='Velocidad Promedio por Desarrollador'
        )
        
        # Mostrar gráfico
        st.altair_chart(chart_ranking, use_container_width=True)
        
        # Agregar nota sobre el objetivo
        st.markdown("**Objetivo:** ≤8 horas/punto (línea roja punteada)")
    
    def _mostrar_historial_usuario(df_final, usuario_sel):
        """Muestra el historial del usuario seleccionado"""
        if usuario_sel == "Todos":
            return
            
        st.subheader(f"Historial de {usuario_sel}")
        df_hist = df_final[df_final["Usuario_nombre"] == usuario_sel].copy()
        if not df_hist.empty:
            df_hist = df_hist.sort_values("Mes_dt")
        st.dataframe(
            df_hist[[
                "Usuario_nombre", "Mes", "Horas", "Puntos", "Claves",
                "Velocidad", "Bugs", "Bugs_claves", "Bugs_resueltos_extra", 
                "Bugs_extra_claves", "Nota_final"
            ]],
            use_container_width=True,
            hide_index=True,
        )
        return df_hist
    
    def _mostrar_grafico_velocidad_mensual(df_hist, usuario_sel):
        """Muestra el gráfico de velocidad mensual del usuario"""
        if len(df_hist) <= 1:  # Solo mostrar gráfico si hay más de un mes
            st.info("Se necesita más de un mes de datos para mostrar el gráfico de velocidad mensual.")
            return
            
        st.subheader(f"📈 Velocidad Mensual - {usuario_sel}")
        
        # Preparar datos para el gráfico mensual
        df_grafico_mensual = df_hist[['Mes_label', 'Velocidad']].copy()
        
        # Crear gráfico de líneas con Altair (mantiene tema oscuro)
        import altair as alt
        
        # Crear DataFrame con datos y línea de objetivo
        chart_df = df_grafico_mensual.copy()
        chart_df['Objetivo'] = 8
        
        # Crear gráfico base
        base = alt.Chart(chart_df).add_selection(
            alt.selection_interval(bind='scales')
        )
        
        # Línea de datos
        line = base.mark_line(
            point=True,
            strokeWidth=3,
            color='#1f77b4'
        ).encode(
            x=alt.X('Mes_label:N', sort=None, title='Mes'),
            y=alt.Y('Velocidad:Q', title='Velocidad (horas/punto)')
        )
        
        # Línea de objetivo
        objective = base.mark_rule(
            stroke='red',
            strokeDash=[5, 5],
            strokeWidth=2
        ).encode(
            y=alt.datum(8)
        )
        
        # Combinar gráficos
        chart = (line + objective).resolve_scale(
            color='independent'
        ).properties(
            width=600,
            height=300,
            title=f'Velocidad Mensual - {usuario_sel}'
        )
        
        # Mostrar gráfico
        st.altair_chart(chart, use_container_width=True)
        
        # Agregar nota sobre el objetivo
        st.markdown("**Objetivo:** ≤8 horas/punto (línea roja punteada)")

    # ==========================
    #   FUNCIÓN: MOSTRAR RANKING Y HISTÓRICO
    # ==========================
    
    def mostrar_ranking_y_historico(df_final, usuario_sel, allowed_names):
        """Función principal refactorizada para mostrar ranking y histórico"""
        
        # === OPTIMIZACIÓN: Cache de cálculos pesados ===
        cache_key_calculos = f"calculos_velocidad_{len(df_final)}_{hash(str(allowed_names))}"
        
        # Verificar si ya tenemos los cálculos en cache
        if cache_key_calculos in st.session_state:
            usuarios_validos = st.session_state[cache_key_calculos]["usuarios_validos"]
            df_ranking_completo = st.session_state[cache_key_calculos]["df_ranking"]
            if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
                print(f"🔍 VELOCIDAD DEBUG: Usando cálculos del cache")
        else:
            # 1. Calcular usuarios válidos
            usuarios_validos = _calcular_usuarios_validos(df_final, allowed_names)
            
            # 4. Calcular ranking completo (una sola vez)
            st.subheader("Ranking de devs")
            df_ranking_completo = _calcular_ranking(df_final, usuarios_validos)
            
            # Guardar en cache
            st.session_state[cache_key_calculos] = {
                "usuarios_validos": usuarios_validos,
                "df_ranking": df_ranking_completo
            }
            if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
                print(f"🔍 VELOCIDAD DEBUG: Cálculos guardados en cache")
        
        # 2. Mostrar selector de usuario (rápido, solo filtro)
        usuario_sel = _mostrar_selector_usuario(usuarios_validos)
        
        # 3. Mostrar cards de objetivos
        _mostrar_cards_objetivos()
        
        if df_ranking_completo.empty:
            st.info("No hay usuarios con puntos en la ventana seleccionada.")
        else:
            # 5. Filtrar por usuario si no es "Todos" (rápido, solo filtro)
            if usuario_sel != "Todos":
                df_ranking = df_ranking_completo[df_ranking_completo["Usuario_nombre"] == usuario_sel]
                
                # Mostrar alerta si el usuario tiene meses con nota 0
                if not df_ranking.empty and df_ranking.iloc[0]["Meses_con_nota_0"] > 0:
                    meses_con_0 = df_ranking.iloc[0]["Meses_con_nota_0"]
                    total_meses = df_ranking.iloc[0]["Total_meses"]
                    st.warning(f"⚠️ **Atención:** {usuario_sel} tiene {meses_con_0} de {total_meses} meses con nota final 0. Verificar datos.")
            else:
                df_ranking = df_ranking_completo
            
            # 6. Mostrar tabla de ranking
            _mostrar_tabla_ranking(df_ranking, usuario_sel)
            
            # 7. Mostrar gráfico de ranking general
            _mostrar_grafico_ranking(df_ranking, usuario_sel)
        
        # 8. Mostrar historial del usuario
        df_hist = _mostrar_historial_usuario(df_final, usuario_sel)
        
        # 9. Mostrar gráfico de velocidad mensual
        if df_hist is not None:
            _mostrar_grafico_velocidad_mensual(df_hist, usuario_sel)

    # ==========================
    #   EJECUCIÓN PRINCIPAL
    # ==========================
    
    # Cargar datos (usar cache si está disponible y es válido)
    force_refresh = st.session_state.get("force_refresh", False)
    
    # Verificar si hay cache válido
    if (not force_refresh and 
        cache_key_velocidad in st.session_state and 
        len(st.session_state[cache_key_velocidad].get("historias", [])) >= 5):
        if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
            print(f"🔍 VELOCIDAD DEBUG: Usando datos del cache...")
        cache_data = st.session_state[cache_key_velocidad]
        historias = cache_data.get("historias", [])
        bugs = cache_data.get("bugs", [])
    else:
        if os.getenv("DEBUG_VELOCIDAD", "false").lower() == "true":
            print(f"🔍 VELOCIDAD DEBUG: Cargando datos desde Jira...")
        historias, bugs = cargar_datos_velocidad(
            jira, fecha_inicio.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d"), 
            proyecto_sel, force_refresh
        )
    
    if not historias and not bugs:
        st.error("❌ No se pudieron cargar datos de Jira")
        st.stop()
    
    # === PROTECCIÓN: Alertas visuales de calidad de datos ===
    col_alert1, col_alert2 = st.columns(2)
    
    
    # Procesar datos
    df_issues = procesar_historias(historias, accountid_to_name, name_to_acc)
    
    # Crear mapeo de historias por desarrollador para bugs extra
    historias_por_dev = {}
    for _, row in df_issues.iterrows():
        dev = row["Usuario_nombre"]
        historia = row["Issue"]
        if dev not in historias_por_dev:
            historias_por_dev[dev] = set()
        historias_por_dev[dev].add(historia)
    
    
    
    bug_rows, bugs_extra_rows = procesar_bugs(bugs, historias_por_dev)
    
    # Aplicar filtro de proyecto a las horas
    if proyecto_sel == "ATI":
        proyectos_validos = ["AFUs ATI", "TECH LAB - INTERNO"]
    elif proyecto_sel == "Postventas":
        proyectos_validos = ["TALLER - MAIPÚ -", "REPUESTOS MAIPU", "AFUS", "TECH LAB - INTERNO"]
    else:  # Todos
        proyectos_validos = ["TALLER - MAIPÚ -", "REPUESTOS MAIPU", "AFUS", "AFUs ATI", "TECH LAB - INTERNO"]
    
    # Filtrar horas por proyecto
    df_horas_filtrado = df_horas[df_horas["Proyecto_logico"].isin(proyectos_validos)]
    df_horas_sum_filtrado = df_horas_filtrado.groupby(["Usuario_nombre", "Mes_dt"], as_index=False)["Horas"].sum()
    
    # Agregar por usuario/mes
    df_completo = agregar_por_usuario_mes(df_issues, bug_rows, bugs_extra_rows, df_horas_sum_filtrado)
    
    # Aplicar filtros
    df_filtrado = aplicar_filtros(df_completo, fecha_inicio, fecha_fin, proyecto_sel)
    
    # Calcular métricas finales
    df_final = calcular_metricas_finales(df_filtrado)
    
    # Mostrar resultados
    mostrar_ranking_y_historico(df_final, "Todos", allowed_names)



# === PESTAÑA DESARROLLO ATI ===
if opcion == "Desarrollo ATI":
    from src.jira_conexion import jira
    import pandas as pd
    import time
    from datetime import datetime, timedelta
    import re

    # Funciones duplicadas eliminadas
    
    def traer_todas_las_issues(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
        while True:
            endpoint = f'search?jql={jql}&fields={fields}&startAt={start_at}&maxResults={max_results}'
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    def get_issue_summary(issue_key, cache):
        if issue_key in cache:
            return cache[issue_key]
        try:
            issue = jira.issue(issue_key)
            summary = issue.fields.summary
            cache[issue_key] = summary
            return summary
        except Exception:
            cache[issue_key] = issue_key
            return issue_key

    def get_fix_version(issue):
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
    
    # Cache para issues de ATI
    cache_key_ati_desarrollo = "desarrollo_ati_issues"
    cache_file_ati_desarrollo = cache_path(cache_key_ati_desarrollo, 'pkl')
    
    try:
        if os.path.exists(cache_file_ati_desarrollo):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_ati_desarrollo))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_ati_desarrollo, 'rb') as f:
                    issues_ati = pickle.load(f)
            else:
                issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia', fields)
                with open(cache_file_ati_desarrollo, 'wb') as f:
                    pickle.dump(issues_ati, f)
        else:
            issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia', fields)
            with open(cache_file_ati_desarrollo, 'wb') as f:
                pickle.dump(issues_ati, f)
    except Exception:
        issues_ati = traer_todas_las_issues(jira, 'project = ATI AND issuetype = Historia', fields)

    issues = [_unwrap_issue(iss) for iss in issues_ati]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # ==== FILTROS ====
    st.subheader("Filtros")
    cols = st.columns([1, 1, 1, 1])
    
    with cols[0]:
        version_sel = st.selectbox("Versión", ["Todas"] + sorted(set(get_fix_version(i) for i in issues if get_fix_version(i))), key="ati_version")
    with cols[1]:
        usuario_seleccionado = st.selectbox("Usuario", ["Todos"] + sorted(set(i["fields"]["assignee"]["displayName"] for i in issues if i["fields"].get("assignee"))), key="ati_usuario")
    with cols[2]:
        estado_sel = st.selectbox("Estado", ["Todos"] + sorted(set(i["fields"]["status"]["name"] for i in issues)), key="ati_estado")
    with cols[3]:
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="ati_desarrollo_actualizar"):
            # Limpiar cache de ATI desarrollo
            cache_keys_to_clear = ["desarrollo_ati_issues"]
            
            for cache_key in cache_keys_to_clear:
                cache_file = cache_path(cache_key, 'pkl')
                if os.path.exists(cache_file):
                    try:
                        os.remove(cache_file)
                    except Exception:
                        pass
            
            st.success("✅ Cache limpiado. Recargando datos...")
            st.rerun()

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

    # ==== FILTRADO DE ISSUES ====
    issues_filtradas = issues.copy()
    
    if version_sel != "Todas":
        issues_filtradas = [i for i in issues_filtradas if get_fix_version(i) == version_sel]
    
    if usuario_seleccionado != "Todos":
        issues_filtradas = [i for i in issues_filtradas if i["fields"].get("assignee") and i["fields"]["assignee"]["displayName"] == usuario_seleccionado]
    
    if estado_sel != "Todos":
        issues_filtradas = [i for i in issues_filtradas if i["fields"]["status"]["name"] == estado_sel]

    # ==== PROCESAMIENTO DE DATOS ====
    rows = []
    for issue in issues_filtradas:
        fila = {
            "Clave": issue["key"],
            "Resumen": issue["fields"]["summary"],
            "Estado": issue["fields"]["status"]["name"],
            "Proyecto": issue["fields"]["project"]["key"],
            "Asignado": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Sin asignar",
            "Duedate": issue["fields"].get("duedate", ""),
            "Version": get_fix_version(issue),
            "Puntos": issue["fields"].get("customfield_10026", 0),
            "Porcentaje avance": "Sin subtareas"
        }

        if issue["fields"].get("assignee"):
            fila["Asignado"] = issue["fields"]["assignee"]["displayName"]

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
            # Cache para estados de subtareas
            cache_key_subtareas = f"desarrollo_subtareas_ati_{version_sel}_{usuario_seleccionado}"
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
                if issue and issue["fields"].get("subtasks"):
                    subtasks = issue["fields"]["subtasks"]
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

        df = pd.DataFrame(rows_a_mostrar)
        st.dataframe(df, use_container_width=True)

# === PESTAÑA ENTREGABLES ATI ===
if opcion == "Entregables ATI":
    from src.jira_conexion import jira
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
    # Filtrar épicas de ATI
    epicas_ati = [e for e in epicas_relevantes if e["rn"].startswith("ATI-")]
    meses_entrega = sorted({epica["mes_entrega"] for epica in epicas_ati}, key=lambda m: meses_orden.index(m))

    # ---- Filtros en columnas ----
    cols = st.columns([1, 1, 1])
    with cols[0]:
        proyecto_seleccionado = st.selectbox("Filtrar por proyecto", ["Todos", "ATI"], key="ati_proyecto")
    with cols[1]:
        mes_seleccionado = st.selectbox("Filtrar por mes de entrega", ["Todos"] + meses_entrega, key="ati_mes")
    with cols[2]:
        # Botón para forzar actualización
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="ati_entregable_actualizar"):
            # Limpiar cache de ATI
            cache_keys_to_clear = ["entregable_ati_issues"]
            
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

    # Cache para issues de ATI en Entregable
    cache_key_ati_entregable = "entregable_ati_issues"
    cache_file_ati_entregable = cache_path(cache_key_ati_entregable, 'pkl')
    
    try:
        if os.path.exists(cache_file_ati_entregable):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_ati_entregable))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_ati_entregable, 'rb') as f:
                    issues_ati = pickle.load(f)
            else:
                issues_ati = traer_todos_los_issues(jira, 'project = ATI AND issuetype = Historia', fields)
                with open(cache_file_ati_entregable, 'wb') as f:
                    pickle.dump(issues_ati, f)
        else:
            issues_ati = traer_todos_los_issues(jira, 'project = ATI AND issuetype = Historia', fields)
            with open(cache_file_ati_entregable, 'wb') as f:
                pickle.dump(issues_ati, f)
    except Exception:
        issues_ati = traer_todos_los_issues(jira, 'project = ATI AND issuetype = Historia', fields)

    # Eliminar duplicados
    issues = [_unwrap_issue(iss) for iss in issues_ati]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # Filtrar épicas relevantes (solo ATI)
    if mes_seleccionado != "Todos":
        epicas_relevantes_filtradas = [e for e in epicas_ati if e["mes_entrega"] == mes_seleccionado]
    else:
        epicas_relevantes_filtradas = epicas_ati

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

    # --- Mostrar tabla completas abajo ---
    if tabla_completas:
        df_completas = pd.DataFrame(tabla_completas)
        st.markdown("## Entregas completadas")
        st.dataframe(
            df_completas[["Épica", "Mes entrega", "% Con ok QA", "% En desarrollo", "Q de HU pendientes", "Puntos totales"]],
            hide_index=True,
            use_container_width=True
        )

# === PESTAÑA HISTÓRICO ATI ===
if opcion == "Histórico ATI":
    import re
    import unicodedata
    import pandas as pd
    import streamlit as st
    import time
    from src.jira_conexion import jira

    # Crear diccionario inverso name_to_acc
    name_to_acc = {v: k for k, v in accountid_to_name.items()}

    # ------------------ Helpers ------------------
    def normalize(s):
        if not s:
            return ""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower().strip()

    def _status_norm(s: str) -> str:
        return (s or "").strip().lower()

    def _safe_issue_key(iss) -> str:
        return (iss.get("key") or iss.get("id") or "") if isinstance(iss, dict) else ""

    def _unwrap_issue(iss):
        if isinstance(iss, dict) and "fields" in iss:
            return iss
        return {"key": str(iss), "fields": {}}

    def traer_todos_las_issues(jira, jql, fields, max_results=100):
        issues, start_at = [], 0
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
        issues, start_at = [], 0
        while True:
            endpoint = (f'search?jql={jql}&fields={fields}'
                        f'&expand=changelog&startAt={start_at}&maxResults={max_results}')
            data = jira._get_json(endpoint)
            batch = data.get("issues", [])
            issues.extend(batch)
            if len(batch) < max_results:
                break
            start_at += max_results
        return issues

    # --- FIX: cálculo robusto de horas desde changelog (con fallbacks) ---
    def _bug_resolution_hours(bug_issue) -> float | None:
        f = bug_issue.get("fields", {}) or {}
        created = pd.to_datetime(f.get("created"), errors="coerce")
        resolution = pd.to_datetime(f.get("resolutiondate"), errors="coerce")
        updated = pd.to_datetime(f.get("updated"), errors="coerce")

        TODO_PATTERNS     = ("to do", "por hacer", "pendiente", "backlog", "asignados a backlog")
        PROGRESS_PATTERNS = ("in progress", "haciendo", "desarroll", "en curso", "working", "asignado a desarrollo")
        DONE_PATTERNS     = ("cerrad", "done", "resuelt", "hech", "closed")

        start_dt, end_dt, last_hist_dt = None, None, None
        histories = (bug_issue.get("changelog", {}) or {}).get("histories", []) or []
        histories = sorted(histories, key=lambda h: pd.to_datetime(h.get("created"), errors="coerce"))

        for hist in histories:
            h_created = pd.to_datetime(hist.get("created"), errors="coerce")
            last_hist_dt = h_created if pd.notna(h_created) else last_hist_dt
            for it in hist.get("items", []) or []:
                if _status_norm(it.get("field")) != "status":
                    continue
                to_str  = _status_norm(it.get("toString"))
                from_str= _status_norm(it.get("fromString"))

                if start_dt is None:
                    sale_de_todo  = any(p in from_str for p in TODO_PATTERNS) and not any(p in to_str for p in TODO_PATTERNS)
                    entra_en_prog = any(p in to_str for p in PROGRESS_PATTERNS)
                    if sale_de_todo or entra_en_prog:
                        start_dt = h_created

                if end_dt is None and any(p in to_str for p in DONE_PATTERNS):
                    end_dt = h_created

            if start_dt is not None and end_dt is not None:
                break

        if start_dt is None:
            start_dt = created
        if end_dt is None:
            if pd.notna(resolution):
                end_dt = resolution
            else:
                status_now = _status_norm((f.get("status") or {}).get("name"))
                if any(p in status_now for p in DONE_PATTERNS):
                    end_dt = last_hist_dt or updated

        if pd.isna(start_dt) or pd.isna(end_dt):
            return None

        delta_hs = (end_dt - start_dt).total_seconds() / 3600.0
        return None if delta_hs < 0 else float(delta_hs)

    def _bugs_por_hu(bugs_issues) -> dict:
        """
        Dict { HU_KEY: {"bugs": [bug_key,...], "hrs": [resol_horas,...]} }
        Para bugs de ATI (métrica 'Bugs asociados' + promedio hs).
        """
        por_hu = {}
        for iss in bugs_issues:
            f = iss.get("fields", {}) or {}
            itype = _status_norm((f.get("issuetype", {}) or {}).get("name"))
            if itype not in ("error", "bug", "defecto", "incidencia"):
                continue
            bug_key = iss.get("key", "")
            if not bug_key:
                continue
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

    def detectar_campo_epic_link():
        try:
            fields = jira._get_json("field")
            candidatos = []
            for f in fields:
                name = (f.get("name") or "").strip().lower()
                key  = (f.get("key") or f.get("id") or "").strip()
                if any(x in name for x in ["epic link", "enlace épico", "enlace epico", "epik link"]):
                    candidatos.append(key)
            for c in candidatos:
                if c.startswith("customfield_"):
                    return c
            return candidatos[0] if candidatos else None
        except Exception:
            return None

    def _es_tipo_bug_uat(issuetype_name: str) -> bool:
        n = (issuetype_name or "").lower()
        return any(k in n for k in ("bug", "error", "defecto", "incidencia"))

    # ------------------ Fuente de datos ------------------
    meses_orden = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

    # Historias ATI → base de RN (con cache)
    fields_hist = ("key,summary,status,project,issuetype,assignee,parent,"
                   "customfield_10016,customfield_10026,duedate,statuscategorychangedate,updated")
    
    # Cache para issues de ATI - OPTIMIZADO para primera carga
    cache_key_ati = "desarrollo_ati_issues"
    cache_file_ati = cache_path(cache_key_ati, 'pkl')
    
    # Cargar desde cache o consultar Jira con límites para primera carga rápida
    try:
        if os.path.exists(cache_file_ati):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_ati))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_ati, 'rb') as f:
                    issues_ati = pickle.load(f)
            else:
                issues_ati = traer_todos_las_issues(jira, 'project = ATI AND issuetype = Historia ORDER BY updated DESC', fields_hist)
                with open(cache_file_ati, 'wb') as f:
                    pickle.dump(issues_ati, f)
        else:
            issues_ati = traer_todos_las_issues(jira, 'project = ATI AND issuetype = Historia ORDER BY updated DESC', fields_hist)
            with open(cache_file_ati, 'wb') as f:
                pickle.dump(issues_ati, f)
    except Exception:
        issues_ati = traer_todos_las_issues(jira, 'project = ATI AND issuetype = Historia ORDER BY updated DESC', fields_hist)
    
    issues = issues_ati

    # Desduplico por key
    issues = [_unwrap_issue(iss) for iss in issues]
    issues_unicos = {}
    for iss in issues:
        k = _safe_issue_key(iss)
        if k:
            issues_unicos[k] = iss
    issues = list(issues_unicos.values())

    # Map RN (nombre de épica) → historias y → set de EPIC KEYS (para UAT)
    EPIC_LINK_CAMPO_STORY = "customfield_10016"
    epicas = {}              # { RN_name: {"Historias": [...] } }
    rn_to_epic_keys = {}     # { RN_name: set([EPIC-123,...]) }

    # Filtrar solo issues de ATI
    issues_ati_filtered = [i for i in issues if i["fields"]["project"]["key"] == "ATI"]

    for issue in issues_ati_filtered:
        f = issue.get("fields", {}) or {}

        # RN/Épica (nombre) desde parent.summary (o custom)
        epic_name = None
        parent = f.get("parent")
        parent_key = None
        if parent:
            epic_name = (parent.get("summary") or (parent.get("fields") or {}).get("summary"))
            parent_key = (parent.get("key") or (parent.get("fields") or {}).get("key"))
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            epica_custom = f.get(EPIC_LINK_CAMPO_STORY, None)
            if isinstance(epica_custom, dict) and epica_custom.get("value"):
                epic_name = epica_custom["value"]
            elif isinstance(epica_custom, str) and epica_custom:
                epic_name = epica_custom
        if not epic_name or normalize(epic_name) in {"sin epica", "sin épica", "none", ""}:
            epic_name = "Sin epica"

        summary = f.get("summary", "")
        if "madre" in (summary or "").lower():
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

        epicas.setdefault(epic_name, {"Historias": []})["Historias"].append({
            "Clave": key,
            "Nombre": summary,
            "Estado": estado,
            "Asignado": asignado,
            "Fecha_estado": fecha_estado,
            "Duedate": duedate,
            "Puntos": puntos,
        })
        if parent_key:
            rn_to_epic_keys.setdefault(epic_name, set()).add(parent_key)

    # Bugs ATI con changelog (para 'Bugs asociados' y promedio hs) - con cache
    fields_bugs_ati = "key,project,issuetype,status,resolutiondate,assignee,parent,issuelinks,created,updated"
    
    # Cache para bugs de ATI
    cache_key_bugs_ati = "desarrollo_bugs_ati"
    cache_file_bugs_ati = cache_path(cache_key_bugs_ati, 'pkl')
    
    try:
        if os.path.exists(cache_file_bugs_ati):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_ati))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_ati, 'rb') as f:
                    bugs_ati = pickle.load(f)
            else:
                bugs_ati = traer_bugs_con_changelog(jira, 'project = ATI AND issuetype = Error ORDER BY updated DESC', fields_bugs_ati)
                with open(cache_file_bugs_ati, 'wb') as f:
                    pickle.dump(bugs_ati, f)
        else:
            bugs_ati = traer_bugs_con_changelog(jira, 'project = ATI AND issuetype = Error ORDER BY updated DESC', fields_bugs_ati)
            with open(cache_file_bugs_ati, 'wb') as f:
                pickle.dump(bugs_ati, f)
    except Exception:
        bugs_ati = traer_bugs_con_changelog(jira, 'project = ATI AND issuetype = Error ORDER BY updated DESC', fields_bugs_ati)
    
    bugs_all = bugs_ati
    mapa_bugs_hu = _bugs_por_hu(bugs_all)

    # BUGS UAT (project = BUG) — SOLO por Epic Link - con cache
    EPIC_FIELD_BUG = detectar_campo_epic_link() or "customfield_10016"
    fields_bugs_uat = f"key,issuetype,created,{EPIC_FIELD_BUG}"
    
    cache_key_bugs_uat = "desarrollo_bugs_uat_ati"
    cache_file_bugs_uat = cache_path(cache_key_bugs_uat, 'pkl')
    
    try:
        if os.path.exists(cache_file_bugs_uat):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_bugs_uat))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_bugs_uat, 'rb') as f:
                    bugs_uat = pickle.load(f)
            else:
                bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat)
                with open(cache_file_bugs_uat, 'wb') as f:
                    pickle.dump(bugs_uat, f)
        else:
            bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat)
            with open(cache_file_bugs_uat, 'wb') as f:
                pickle.dump(bugs_uat, f)
    except Exception:
        bugs_uat = traer_todos_las_issues(jira, 'project = BUG AND created >= "2025-01-01" ORDER BY created DESC', fields_bugs_uat)

    epic_to_bugs_uat: dict[str, set] = {}
    for iss in bugs_uat:
        f = iss.get("fields", {}) or {}
        itype = (f.get("issuetype") or {}).get("name") or ""
        if not _es_tipo_bug_uat(itype):
            continue
        bug_key = iss.get("key", "")
        if not bug_key:
            continue
        epic_ref = f.get(EPIC_FIELD_BUG)
        epic_key = ""
        if isinstance(epic_ref, dict):
            epic_key = (epic_ref.get("key") or epic_ref.get("id") or "").strip()
        elif isinstance(epic_ref, str):
            epic_key = epic_ref.strip()
        if epic_key:
            epic_to_bugs_uat.setdefault(epic_key, set()).add(bug_key)

    # ------------------ Tabla de histórico (usa 'epicas_relevantes') - con cache ------------------
    def ordenar_mes(m):
        try:
            return meses_orden.index(m)
        except Exception:
            return 99

    # Cache para tabla histórica procesada
    cache_key_historico = "historico_tabla_procesada_ati"
    cache_file_historico = cache_path(cache_key_historico, 'pkl')
    
    # Intentar cargar tabla histórica desde cache
    tabla_historico = []
    try:
        if os.path.exists(cache_file_historico):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_historico))
            if (datetime.now() - mtime) < timedelta(hours=48):
                with open(cache_file_historico, 'rb') as f:
                    tabla_historico = pickle.load(f)
                    # Verificar si el cache tiene el campo DCR_% (nuevo campo)
                    if tabla_historico and "DCR_%" not in tabla_historico[0]:
                        # Cache antiguo sin DCR, limpiarlo para recalcular
                        os.remove(cache_file_historico)
                        tabla_historico = []
    except Exception:
        pass
    
    # Botón para limpiar cache del histórico
    if st.button("🗑️ Limpiar Cache Histórico", help="Limpia el cache del histórico para regenerar datos"):
        cache_file_historico = cache_path("historico_ati", 'pkl')
        if os.path.exists(cache_file_historico):
            os.remove(cache_file_historico)
        st.success("✅ Cache del histórico limpiado. Recargando datos...")
        st.rerun()

    # Si no hay cache, procesar tabla histórica
    if not tabla_historico:
        st.info("⏳ **Procesando datos históricos de ATI**... Esto puede tomar unos minutos la primera vez.")
        tabla_historico = []
        # Filtrar solo épicas de ATI
        epicas_ati = [e for e in epicas_relevantes if e["rn"].startswith("ATI-")]
        for epica_rn in epicas_ati:
            nombre_epica = epica_rn.get("nombre", "")
            mes_entrega = epica_rn.get("mes_entrega", "")
            epic_match = next((rn for rn in epicas if normalize(nombre_epica) == normalize(rn)), None)

            if epic_match:
                data = epicas[epic_match]
                historias = data["Historias"]
                total = len(historias)
                listas_para_implementar = sum(1 for h in historias if h["Estado"] == "lista para implementar")
                porcentaje_num = (listas_para_implementar / total * 100) if total > 0 else 0
                puntos_totales = sum(h.get("Puntos", 0) or 0 for h in historias)

                # Bugs asociados (ATI) + promedio hs
                hu_keys = [h["Clave"] for h in historias if h.get("Clave")]
                bugs_keys_ati, bugs_hrs = [], []
                for hu in hu_keys:
                    info = mapa_bugs_hu.get(hu)
                    if not info:
                        continue
                    bugs_keys_ati.extend(info.get("bugs", []))
                    bugs_hrs.extend(info.get("hrs", []))
                uniq_bugs_ati = sorted(set(bugs_keys_ati))
                bugs_cnt_ati = len(uniq_bugs_ati)
                prom_hrs = round(sum(bugs_hrs) / len(bugs_hrs), 2) if bugs_hrs else None

                # UAT por RN (solo Epic Link)
                candidate_epic_keys = rn_to_epic_keys.get(epic_match, set())
                uat_keys = set()
                for ek in candidate_epic_keys:
                    uat_keys |= epic_to_bugs_uat.get(ek, set())
                uniq_bugs_uat = sorted(uat_keys)
                bugs_cnt_uat = len(uniq_bugs_uat)
                
                # Calcular DCR (Defect Containment Rate) = QBug / (QBug + QUAT) * 100
                total_bugs = bugs_cnt_ati + bugs_cnt_uat
                dcr = round((bugs_cnt_ati / total_bugs * 100), 1) if total_bugs > 0 else 0.0
                    
            else:
                historias = []
                porcentaje_num = 0
                puntos_totales = 0
                uniq_bugs_ati, bugs_cnt_ati, prom_hrs = [], 0, None
                uniq_bugs_uat, bugs_cnt_uat = [], 0
                dcr = 0.0  # Sin datos, DCR = 0

            tabla_historico.append({
                "Épica": nombre_epica,
                "Mes entrega": mes_entrega,
                "%_num": porcentaje_num,
                "Historias": historias,
                "Puntos totales": puntos_totales,
                "Bugs_asociados": bugs_cnt_ati,
                "Bugs_asociados_claves": ", ".join(uniq_bugs_ati),
                "Promedio_resolucion_bugs_hs": prom_hrs,
                "Bugs_pruebas_UAT": bugs_cnt_uat,
                "Bugs_pruebas_UAT_claves": ", ".join(uniq_bugs_uat),
                "DCR_%": dcr,
            })
        
        # Guardar tabla histórica en cache
        try:
            with open(cache_file_historico, 'wb') as f:
                pickle.dump(tabla_historico, f)
        except Exception:
            pass

    tabla_historico = sorted(tabla_historico, key=lambda r: (ordenar_mes(r["Mes entrega"]), r["%_num"]))

    # ------------------ UI ------------------
    st.markdown("## Histórico de RNs ATI")
    
    # Mostrar información sobre datos limitados en primera carga
    if not tabla_historico:
        st.info("🔄 Cargando datos limitados para primera carga rápida...")
    else:
        st.caption("ℹ️ **Primera carga optimizada**: Mostrando datos más recientes. Usa 'Actualizar' para datos completos.")
    
    # Leyenda de colores DCR
    st.caption("🎨 **DCR**: 🟢 ≥90% (Excelente) | 🔴 <90% (Necesita mejora)")
    
    # Verificar si hay DCR mal calculado y mostrar advertencia
    dcr_mal_calculado = any(row.get("DCR_%", 0) == 0.0 and row.get("Bugs_asociados", 0) > 0 for row in tabla_historico)
    if dcr_mal_calculado:
        st.warning("⚠️ **DCR mal calculado detectado**. Usa 'Actualizar' para recalcular con la fórmula correcta.")

    # Filtro de entregable (RN)
    colf1, colf2, colf3 = st.columns([2,1,1])
    with colf1:
        buscar_rn = st.text_input("Buscar entregable (RN)", value="", placeholder="Ej: Generar presupuesto")
    with colf2:
        st.caption("Filtra por nombre (ignora acentos y mayúsculas).")
    with colf3:
        # Botón para forzar actualización
        if st.button("🔄 Actualizar", help="Fuerza la recarga de datos desde Jira", key="historico_ati_actualizar"):
            # Limpiar todos los caches relacionados con histórico ATI
            cache_keys_to_clear = [
                "desarrollo_ati_issues",
                "desarrollo_bugs_ati",
                "desarrollo_bugs_uat_ati",
                "historico_tabla_procesada_ati"  # Cache de tabla con nuevo campo DCR
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

    buscar_norm = normalize(buscar_rn)
    if buscar_norm:
        tabla_filtrada = [r for r in tabla_historico if buscar_norm in normalize(r["Épica"])]
    else:
        tabla_filtrada = tabla_historico

    for row in tabla_filtrada:
        nombre = row["Épica"]
        mes = row["Mes entrega"]
        porcentaje = row["%_num"]
        puntos_totales = row["Puntos totales"]
        historias = row["Historias"]

        bugs_cnt_ati = row["Bugs_asociados"]
        prom_hrs = row["Promedio_resolucion_bugs_hs"]
        prom_txt = f"{prom_hrs:.2f} hs" if prom_hrs is not None else "-"

        bugs_cnt_uat = row.get("Bugs_pruebas_UAT", 0)
        dcr = row.get("DCR_%", 0.0)

        # Color para DCR: Verde si ≥90%, Rojo si <90%
        dcr_color = "🟢" if dcr >= 90 else "🔴"

        expander_title = (
            f"{nombre} | Avance: {porcentaje:.1f}% | {mes} | "
            f"Puntos: {puntos_totales} | Bugs: {bugs_cnt_ati} | UAT: {bugs_cnt_uat} | "
            f"DCR: {dcr_color} {dcr}% | Prom. resolución: {prom_txt}"
        )
        with st.expander(expander_title, expanded=False):
            st.markdown(
                f"**Bugs asociados (ATI):** {bugs_cnt_ati} &nbsp;|&nbsp; "
                f"**Promedio resolución (ATI):** {prom_txt} &nbsp;|&nbsp; "
                f"**Claves ATI:** {row['Bugs_asociados_claves'] or '-'}"
            )
            st.markdown(
                f"**Bugs pruebas UAT (project BUG, Epic Link):** {bugs_cnt_uat} &nbsp;|&nbsp; "
                f"**Claves UAT:** {row.get('Bugs_pruebas_UAT_claves','') or '-'}"
            )
            st.markdown(
                f"**DCR (Defect Containment Rate):** {dcr_color} **{dcr}%** &nbsp;|&nbsp; "
                f"**Fórmula:** QBug / (QBug + QUAT) × 100 = {bugs_cnt_ati} / ({bugs_cnt_ati} + {bugs_cnt_uat}) × 100"
            )
            st.markdown("---")

            if historias:
                for h in historias:
                    estado = h["Estado"]
                    color_estado = (
                        "#39d353" if estado == "lista para implementar"
                        else "#fa4" if "desarroll" in estado
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
      
# Nota: el cache de la pestaña Bugs se maneja a nivel de carga de issues
# mediante `cargar_issues_jira_cache` y los cálculos subsiguientes quedan
# dentro del flujo de la propia pestaña para evitar NameError por variables
# no definidas fuera de contexto.

# Botón global para limpiar todo el cache (al final de la aplicación)
st.divider()
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🗑️ Limpiar Todo el Cache", help="Elimina todos los archivos de cache del sistema"):
        import shutil
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                st.success("✅ Todo el cache ha sido eliminado. La próxima carga será desde cero.")
                st.rerun()
            except Exception as e:
                st.error(f"Error limpiando cache: {e}")
        else:
            st.info("No hay cache para limpiar")
      