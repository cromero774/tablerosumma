"""
Utilidades comunes para el Tablero SUMMA
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

def _safe_issue_key(issue_key):
    """Función auxiliar para manejar issue keys de forma segura"""
    if pd.isna(issue_key) or issue_key == '':
        return 'Sin Issue'
    return str(issue_key)

def obtener_proyecto_logico(row, fecha_inicio=None):
    """Obtener el proyecto lógico basado en las reglas de negocio"""
    
    # Si es TEM- y la fecha es desde junio 2025, usar MAPEO_TEM
    if fecha_inicio and fecha_inicio >= datetime(2025, 6, 1):
        if row.get('Proyecto', '').startswith('TEM-'):
            tem_key = row.get('Proyecto', '')
            if tem_key in MAPEO_TEM:
                return MAPEO_TEM[tem_key][1]
    
    # Normalización de proyectos
    proyecto = row.get('Proyecto', '')
    if proyecto in ['CORETECH', 'Core Tech', 'TECHLAB']:
        return 'TECH LAB - INTERNO'
    
    return proyecto

def aplicar_filtros_usuario(df, usuario_actual):
    """Aplicar filtros de usuario según las reglas de negocio"""
    
    if usuario_actual == 'BOTH':
        # Ver todas las filas (ATI + POST + INTERNO)
        return df
    elif usuario_actual == 'ATI':
        # Ver filas ATI + INTERNO
        return df[df['Proyecto'].isin(PROYECTOS_ATI)]
    elif usuario_actual == 'POSTVENTA':
        # Ver filas POSTVENTA + INTERNO
        return df[df['Proyecto'].isin(PROYECTOS_POSTVENTA)]
    else:
        return df

def mostrar_alerta_tem_no_mapeadas(df):
    """Mostrar alerta para TEM no mapeadas"""
    tem_no_mapeadas = df[df['Proyecto'].str.startswith('TEM-', na=False)]
    if not tem_no_mapeadas.empty:
        st.warning(f"⚠️ Se encontraron {len(tem_no_mapeadas)} registros TEM no mapeados")

def crear_grafico_barras(df, x_col, y_col, title, color_col=None):
    """Crear gráfico de barras con Plotly"""
    if color_col:
        fig = px.bar(df, x=x_col, y=y_col, color=color_col, title=title)
    else:
        fig = px.bar(df, x=x_col, y=y_col, title=title)
    
    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=y_col,
        height=400
    )
    
    return fig

def crear_grafico_lineas(df, x_col, y_col, title, color_col=None):
    """Crear gráfico de líneas con Plotly"""
    if color_col:
        fig = px.line(df, x=x_col, y=y_col, color=color_col, title=title)
    else:
        fig = px.line(df, x=x_col, y=y_col, title=title)
    
    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=y_col,
        height=400
    )
    
    return fig

def formatear_fecha(fecha):
    """Formatear fecha para mostrar"""
    if pd.isna(fecha):
        return 'Sin fecha'
    return fecha.strftime('%d/%m/%Y')

def calcular_dias_laborables(fecha_inicio, fecha_fin):
    """Calcular días laborables entre dos fechas"""
    if pd.isna(fecha_inicio) or pd.isna(fecha_fin):
        return 0
    
    # Feriados argentinos 2025
    feriados = [
        datetime(2025, 1, 1),   # Año Nuevo
        datetime(2025, 3, 24),  # Día Nacional de la Memoria
        datetime(2025, 3, 25),  # Día del Veterano
        datetime(2025, 4, 18),  # Viernes Santo
        datetime(2025, 5, 1),   # Día del Trabajador
        datetime(2025, 5, 25),  # Revolución de Mayo
        datetime(2025, 6, 20),  # Día de la Bandera
        datetime(2025, 7, 9),   # Día de la Independencia
        datetime(2025, 8, 17),  # Paso a la Inmortalidad de San Martín
        datetime(2025, 10, 12), # Día del Respeto a la Diversidad Cultural
        datetime(2025, 11, 20), # Día de la Soberanía Nacional
        datetime(2025, 12, 8),  # Inmaculada Concepción
        datetime(2025, 12, 25), # Navidad
    ]
    
    dias_laborables = 0
    fecha_actual = fecha_inicio
    
    while fecha_actual <= fecha_fin:
        # No contar fines de semana ni feriados
        if fecha_actual.weekday() < 5 and fecha_actual not in feriados:
            dias_laborables += 1
        fecha_actual += timedelta(days=1)
    
    return dias_laborables
