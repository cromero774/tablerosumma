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
from src.jira_conexion import get_jira
from src.tempo_conexion import tempo_get
from src.cache_datos import cargar_df_cache, guardar_df_cache, cargar_json_cache, guardar_json_cache

# Importar pestañas
from src.tabs.horas_postventas import mostrar_horas_postventas
from src.tabs.desarrollo_postventas import mostrar_desarrollo_postventas
from src.tabs.entregables_postventas import mostrar_entregables_postventas
from src.tabs.historico_postventa import mostrar_historico_postventa
from src.tabs.horas_ati import mostrar_horas_ati
from src.tabs.desarrollo_ati import mostrar_desarrollo_ati
from src.tabs.entregables_ati import mostrar_entregables_ati
from src.tabs.historico_ati import mostrar_historico_ati
from src.tabs.bugs import mostrar_bugs
from src.tabs.velocidad_devs import mostrar_velocidad_devs
from src.tabs.gantt import mostrar_gantt
from src.tabs.puntos_historicos import mostrar_puntos_historicos
from src.tabs.vacaciones import mostrar_vacaciones

# Importar utilidades
from src.utils.configuracion import (
    MAPEO_TEM, RESUMEN_A_PROYECTO, PROYECTOS_POSTVENTA, PROYECTOS_ATI,
    cargar_epicas_relevantes, cargar_datos_historicos, cargar_issues_jira_cache,
    cargar_datos_principales, configurar_sidebar, aplicar_estilos_css
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
    
    # Aplicar estilos CSS según el tema seleccionado
    aplicar_estilos_css()
    
    # Usar la opción del session state
    opcion = st.session_state.opcion_actual
    
    # Mostrar contenido según la opción seleccionada
    if opcion == "Menú":
        mostrar_pagina_menu()
    elif opcion and opcion != "Menú":
        mostrar_contenido(
            opcion,
            df,
            epicas_relevantes,
            issues_jira
        )

def mostrar_pagina_menu():
    """Mostrar la página de menú principal"""
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
        mostrar_historico_ati(epicas_relevantes, issues_jira)
    elif opcion == "BUGS":
        mostrar_bugs(epicas_relevantes, issues_jira)
    elif opcion == "Velocidad de devs":
        mostrar_velocidad_devs(df, issues_jira)
    elif opcion == "Gantt":
        mostrar_gantt(issues_jira)
    elif opcion == "Puntos Históricos":
        mostrar_puntos_historicos()
    elif opcion == "Vacaciones":
        mostrar_vacaciones()

if __name__ == "__main__":
    main()
