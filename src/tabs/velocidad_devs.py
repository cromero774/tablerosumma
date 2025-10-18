"""
Pestaña de Velocidad de devs
"""

import streamlit as st
import pandas as pd

def mostrar_velocidad_devs(issues_jira):
    """Mostrar la pestaña de Velocidad de devs"""
    
    st.title("⚡ Velocidad de devs")
    st.info("Esta pestaña está en desarrollo. Se implementará próximamente.")
    
    # TODO: Implementar la lógica de Velocidad de devs
    # - CRÍTICO: NUNCA reducir cantidad de datos (max_issues y max_bugs = 10000)
    # - Análisis de velocidad de desarrollo
    # - Métricas de story points completados
