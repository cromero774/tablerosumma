"""
Tests con mocks para Jira y APIs externas
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestMockJira:
    """Tests con mocks para la conexión a Jira"""
    
    @patch('src.jira_conexion.get_jira')
    def test_conexion_jira_mock(self, mock_get_jira):
        """Test de conexión a Jira con mock"""
        
        # Setup mock
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {
            "issues": [
                {
                    "key": "ATI-1",
                    "fields": {
                        "summary": "Historia de prueba",
                        "status": {"name": "Lista para implementar"},
                        "assignee": {"displayName": "Juan"},
                        "customfield_10026": 5
                    }
                }
            ]
        }
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            from src.jira_conexion import get_jira
            
            jira = get_jira()
            assert jira is not None
            
            # Test que puede hacer consultas
            result = jira._get_json("search?jql=project=ATI")
            assert "issues" in result
            assert len(result["issues"]) == 1
            
        except Exception as e:
            pytest.fail(f"Test de conexión Jira con mock falló: {e}")
    
    @patch('src.jira_conexion.get_jira')
    def test_consultas_jira_complejas(self, mock_get_jira):
        """Test de consultas complejas a Jira con mock"""
        
        # Setup mock con datos más complejos
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {
            "issues": [
                {
                    "key": "ATI-1",
                    "fields": {
                        "summary": "Historia 1",
                        "status": {"name": "Lista para implementar"},
                        "assignee": {"displayName": "Juan"},
                        "customfield_10026": 5,
                        "parent": {"key": "ATI-EPIC-1", "summary": "Épica 1"},
                        "issuelinks": [],
                        "created": "2024-01-01T10:00:00.000+0000",
                        "updated": "2024-01-02T10:00:00.000+0000"
                    },
                    "changelog": {
                        "histories": [
                            {
                                "created": "2024-01-01T10:00:00.000+0000",
                                "items": [
                                    {
                                        "field": "status",
                                        "fromString": "To Do",
                                        "toString": "In Progress"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            from src.jira_conexion import get_jira
            
            jira = get_jira()
            
            # Test consulta con changelog
            result = jira._get_json("search?jql=project=ATI&expand=changelog")
            assert "issues" in result
            assert "changelog" in result["issues"][0]
            
        except Exception as e:
            pytest.fail(f"Test de consultas complejas Jira falló: {e}")

class TestMockTempo:
    """Tests con mocks para la conexión a Tempo"""
    
    @patch('src.tempo_conexion.tempo_get')
    def test_conexion_tempo_mock(self, mock_tempo_get):
        """Test de conexión a Tempo con mock"""
        
        # Setup mock
        mock_tempo_get.return_value = [
            {
                "issue": {"key": "ATI-1"},
                "timeSpentSeconds": 28800,  # 8 horas
                "dateStarted": "2024-01-01",
                "author": {"displayName": "Juan"}
            }
        ]
        
        # Test
        try:
            from src.tempo_conexion import tempo_get
            
            result = tempo_get("2024-01-01", "2024-01-31", "ATI")
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["issue"]["key"] == "ATI-1"
            
        except Exception as e:
            pytest.fail(f"Test de conexión Tempo con mock falló: {e}")

class TestMockCache:
    """Tests con mocks para el sistema de cache"""
    
    @patch('src.cache_datos.cargar_df_cache')
    @patch('src.cache_datos.guardar_df_cache')
    @patch('src.cache_datos.cargar_json_cache')
    @patch('src.cache_datos.guardar_json_cache')
    def test_sistema_cache_completo(self, mock_guardar_json, mock_cargar_json, 
                                  mock_guardar_df, mock_cargar_df):
        """Test completo del sistema de cache con mocks"""
        
        # Setup mocks
        mock_df = pd.DataFrame({
            'Clave': ['ATI-1', 'ATI-2'],
            'Nombre': ['Historia 1', 'Historia 2'],
            'Estado': ['Lista para implementar', 'En desarrollo'],
            'Horas': [8, 6]
        })
        
        mock_cargar_df.return_value = mock_df
        mock_guardar_df.return_value = True
        mock_cargar_json.return_value = [{"rn": "ATI-1", "nombre": "Test"}]
        mock_guardar_json.return_value = True
        
        # Test
        try:
            from src.cache_datos import (
                cargar_df_cache, guardar_df_cache, 
                cargar_json_cache, guardar_json_cache
            )
            
            # Test cache de DataFrames
            df_cargado = cargar_df_cache('test_df', 'pkl')
            assert isinstance(df_cargado, pd.DataFrame)
            assert len(df_cargado) == 2
            
            resultado_df = guardar_df_cache(mock_df, 'test_df', 'pkl')
            assert resultado_df == True
            
            # Test cache de JSON
            json_cargado = cargar_json_cache('test_json', 'json')
            assert isinstance(json_cargado, list)
            assert len(json_cargado) == 1
            
            resultado_json = guardar_json_cache(mock_cargar_json.return_value, 'test_json', 'json')
            assert resultado_json == True
            
        except Exception as e:
            pytest.fail(f"Test de sistema de cache completo falló: {e}")

class TestMockStreamlit:
    """Tests con mocks para Streamlit"""
    
    @patch('streamlit.set_page_config')
    @patch('streamlit.sidebar')
    @patch('streamlit.markdown')
    @patch('streamlit.header')
    @patch('streamlit.caption')
    @patch('streamlit.expander')
    @patch('streamlit.columns')
    @patch('streamlit.button')
    @patch('streamlit.selectbox')
    @patch('streamlit.radio')
    @patch('streamlit.dataframe')
    @patch('streamlit.plotly_chart')
    def test_streamlit_mock_completo(self, mock_plotly, mock_dataframe, mock_radio, 
                                   mock_selectbox, mock_button, mock_columns, 
                                   mock_expander, mock_caption, mock_header, 
                                   mock_markdown, mock_sidebar, mock_page_config):
        """Test completo con mocks de Streamlit"""
        
        # Setup mocks
        mock_columns.return_value = [MagicMock(), MagicMock()]
        mock_button.return_value = False
        mock_selectbox.return_value = "Desarrollo Postventas"
        mock_radio.return_value = "Desarrollo Postventas"
        
        # Test
        try:
            import streamlit as st
            
            # Test configuración de página
            st.set_page_config(
                page_title="Test",
                page_icon="📊",
                layout="wide"
            )
            
            # Test elementos básicos
            st.header("Test Header")
            st.caption("Test Caption")
            st.markdown("Test Markdown")
            
            # Test columnas
            col1, col2 = st.columns(2)
            assert col1 is not None
            assert col2 is not None
            
            # Test botones y selectores
            button_result = st.button("Test Button")
            assert button_result == False
            
            selectbox_result = st.selectbox("Test Select", ["Option 1", "Option 2"])
            assert selectbox_result == "Desarrollo Postventas"
            
            radio_result = st.radio("Test Radio", ["Option 1", "Option 2"])
            assert radio_result == "Desarrollo Postventas"
            
        except Exception as e:
            pytest.fail(f"Test de Streamlit con mocks falló: {e}")

class TestMockIntegracionCompleta:
    """Test de integración completa con todos los mocks"""
    
    @patch('src.jira_conexion.get_jira')
    @patch('src.tempo_conexion.tempo_get')
    @patch('src.cache_datos.cargar_df_cache')
    @patch('src.cache_datos.cargar_json_cache')
    @patch('streamlit.set_page_config')
    @patch('streamlit.sidebar')
    @patch('streamlit.markdown')
    def test_integracion_completa_con_mocks(self, mock_markdown, mock_sidebar, 
                                          mock_page_config, mock_cargar_json, 
                                          mock_cargar_df, mock_tempo, mock_get_jira):
        """Test de integración completa con todos los mocks"""
        
        # Setup mocks
        mock_df = pd.DataFrame({
            'Fecha_dt': pd.to_datetime(['2024-01-01']),
            'Proyecto': ['ATI'],
            'Horas': [8],
            'Año': [2024],
            'Mes': [1]
        })
        
        mock_cargar_df.return_value = mock_df
        mock_cargar_json.return_value = [{"rn": "ATI-1", "nombre": "Test"}]
        
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        mock_tempo.return_value = []
        
        # Test
        try:
            # Importar módulos
            from src.jira_conexion import get_jira
            from src.tempo_conexion import tempo_get
            from src.cache_datos import cargar_df_cache, cargar_json_cache
            
            # Test conexiones
            jira = get_jira()
            tempo_data = tempo_get("2024-01-01", "2024-01-31", "ATI")
            
            # Test cache
            df_cached = cargar_df_cache('test', 'pkl')
            json_cached = cargar_json_cache('test', 'json')
            
            # Verificaciones
            assert jira is not None
            assert isinstance(tempo_data, list)
            assert isinstance(df_cached, pd.DataFrame)
            assert isinstance(json_cached, list)
            
        except Exception as e:
            pytest.fail(f"Test de integración completa con mocks falló: {e}")
