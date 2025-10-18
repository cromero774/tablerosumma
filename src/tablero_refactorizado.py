"""
Tablero SUMMA - Versión Refactorizada
Archivo principal que importa todas las pestañas
"""

import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Importar módulos existentes
from jira_conexion import get_jira
from tempo_conexion import tempo_get
from cache_datos import cargar_df_cache, guardar_df_cache, cargar_json_cache, guardar_json_cache

# Importar pestañas
from tabs.horas_postventas import mostrar_horas_postventas
from tabs.desarrollo_postventas import mostrar_desarrollo_postventas
from tabs.entregables_postventas import mostrar_entregables_postventas
from tabs.historico_postventa import mostrar_historico_postventa
from tabs.horas_ati import mostrar_horas_ati
from tabs.desarrollo_ati import mostrar_desarrollo_ati
from tabs.entregables_ati import mostrar_entregables_ati
from tabs.historico_ati import mostrar_historico_ati
from tabs.bugs import mostrar_bugs
from tabs.velocidad_devs import mostrar_velocidad_devs
from tabs.gantt import mostrar_gantt

# Importar utilidades
from utils.configuracion import (
    MAPEO_TEM, RESUMEN_A_PROYECTO, PROYECTOS_POSTVENTA, PROYECTOS_ATI,
    cargar_epicas_relevantes, cargar_datos_historicos, cargar_issues_jira_cache,
    cargar_datos_principales, configurar_sidebar
)

def main():
    """Función principal del tablero"""
    
    # Configuración de la página
    st.set_page_config(
        page_title="Tablero SUMMA",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Cargar datos base (replicar exactamente la lógica del original)
    df = cargar_datos_principales()
    epicas_relevantes = cargar_epicas_relevantes()
    issues_jira = cargar_issues_jira_cache()
    
    # Configurar sidebar exactamente como el original
    configurar_sidebar()
    
    # Usar la opción del session state
    opcion = st.session_state.opcion_actual
    
    # Mostrar contenido según la opción seleccionada
    if opcion and opcion != "Menú":
        mostrar_contenido(
            opcion,
            df,
            epicas_relevantes,
            issues_jira
        )

def mostrar_contenido(opcion, df, epicas_relevantes, issues_jira):
    """Mostrar el contenido de la pestaña seleccionada"""
    
    if opcion == "Horas Postventas":
        mostrar_horas_postventas(df)
    elif opcion == "Desarrollo Postventas":
        mostrar_desarrollo_postventas(issues_jira)
    elif opcion == "Entregables Postventas":
        mostrar_entregables_postventas(epicas_relevantes, issues_jira)
    elif opcion == "Histórico Postventa":
        mostrar_historico_postventa(df)
    elif opcion == "Horas ATI":
        mostrar_horas_ati(df)
    elif opcion == "Desarrollo ATI":
        mostrar_desarrollo_ati(issues_jira)
    elif opcion == "Entregables ATI":
        mostrar_entregables_ati(epicas_relevantes, issues_jira)
    elif opcion == "Histórico ATI":
        mostrar_historico_ati(df)
    elif opcion == "BUGS":
        mostrar_bugs(issues_jira)
    elif opcion == "Velocidad de devs":
        mostrar_velocidad_devs(issues_jira)
    elif opcion == "Gantt":
        mostrar_gantt(issues_jira)

if __name__ == "__main__":
    main()
