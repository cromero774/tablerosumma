"""
Configuración global para pytest
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
import streamlit as st

@pytest.fixture
def mock_jira():
    """Mock de la conexión a Jira"""
    mock = MagicMock()
    mock._get_json.return_value = {"issues": []}
    return mock

@pytest.fixture
def mock_streamlit():
    """Mock de Streamlit para testing"""
    with patch('streamlit.set_page_config'), \
         patch('streamlit.sidebar'), \
         patch('streamlit.markdown'), \
         patch('streamlit.header'), \
         patch('streamlit.caption'), \
         patch('streamlit.info'), \
         patch('streamlit.warning'), \
         patch('streamlit.error'), \
         patch('streamlit.success'), \
         patch('streamlit.expander'), \
         patch('streamlit.columns'), \
         patch('streamlit.button'), \
         patch('streamlit.selectbox'), \
         patch('streamlit.radio'), \
         patch('streamlit.dataframe'), \
         patch('streamlit.plotly_chart'), \
         patch('streamlit.rerun'):
        yield st

@pytest.fixture
def sample_dataframe():
    """DataFrame de ejemplo para testing"""
    return pd.DataFrame({
        'Clave': ['ATI-1', 'ATI-2', 'ATI-3'],
        'Nombre': ['Historia 1', 'Historia 2', 'Historia 3'],
        'Estado': ['Lista para implementar', 'En desarrollo', 'Lista para implementar'],
        'Asignado': ['Juan', 'María', 'Pedro'],
        'Puntos': [5, 8, 3]
    })

@pytest.fixture
def sample_epicas_relevantes():
    """Datos de ejemplo para épicas relevantes"""
    return [
        {
            "rn": "ATI-1",
            "nombre": "Generar presupuesto",
            "mes_entrega": "Enero",
            "proyecto": "ATI"
        },
        {
            "rn": "ATI-2", 
            "nombre": "Consultar stock",
            "mes_entrega": "Febrero",
            "proyecto": "ATI"
        }
    ]

@pytest.fixture
def sample_issues_jira():
    """Datos de ejemplo para issues de Jira"""
    return [
        {
            "key": "ATI-1",
            "fields": {
                "summary": "Historia de ejemplo",
                "status": {"name": "Lista para implementar"},
                "assignee": {"displayName": "Juan"},
                "customfield_10026": 5
            }
        }
    ]
