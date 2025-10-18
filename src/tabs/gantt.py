"""
Pestaña Gantt - Tablero SUMMA
Implementa la lógica completa del diagrama de Gantt para seguimiento de proyectos
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def mostrar_gantt(issues_jira):
    """Mostrar la pestaña de Gantt"""
    
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
        """Cargar y procesar datos del Gantt desde Google Sheets"""
        try:
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
        except Exception as e:
            st.error(f"Error cargando datos del Gantt: {e}")
            return pd.DataFrame()

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

    # Verificar que se cargaron datos
    if df_gantt.empty:
        st.error("No se pudieron cargar los datos del Gantt. Verifica la conexión a internet.")
        return

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
        
        # Mostrar estadísticas
        st.subheader("📊 Estadísticas del Gantt")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total RNs", len(df_filtrado))
        with col2:
            estados_count = df_filtrado['estado'].value_counts()
            entregados = estados_count.get('Entregado', 0)
            st.metric("Entregados", entregados)
        with col3:
            en_desarrollo = estados_count.get('En desarrollo', 0)
            st.metric("En Desarrollo", en_desarrollo)
        with col4:
            porcentaje_entregado = (entregados / len(df_filtrado) * 100) if len(df_filtrado) > 0 else 0
            st.metric("% Entregado", f"{porcentaje_entregado:.1f}%")
    else:
        st.warning("No hay datos para los filtros seleccionados.")