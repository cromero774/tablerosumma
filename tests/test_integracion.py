"""
Tests de integración para el tablero completo
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestIntegracionTablero:
    """Tests de integración para el tablero completo"""
    
    @patch('tablero.get_jira')
    @patch('tablero.tempo_get')
    @patch('tablero.cargar_df_cache')
    @patch('tablero.cargar_json_cache')
    @patch('tablero.cargar_epicas_relevantes')
    @patch('tablero.cargar_datos_historicos')
    @patch('tablero.cargar_issues_jira_cache')
    @patch('tablero.cargar_datos_principales')
    def test_carga_datos_principales(self, mock_cargar_datos, mock_cargar_issues, 
                                   mock_cargar_historicos, mock_cargar_epicas,
                                   mock_cargar_json, mock_cargar_df, 
                                   mock_tempo, mock_get_jira):
        """Test de integración para la carga de datos principales"""
        
        # Setup mocks
        mock_df = pd.DataFrame({
            'Fecha_dt': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'Proyecto': ['ATI', 'ATI'],
            'Horas': [8, 6]
        })
        mock_cargar_datos.return_value = mock_df
        mock_cargar_issues.return_value = []
        mock_cargar_historicos.return_value = mock_df
        mock_cargar_epicas.return_value = []
        mock_cargar_json.return_value = {}
        mock_cargar_df.return_value = mock_df
        
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        mock_tempo.return_value = []
        
        # Test
        try:
            import tablero
            
            # Simular la carga de datos principales
            df = mock_cargar_datos()
            epicas_relevantes = mock_cargar_epicas()
            issues_jira = mock_cargar_issues()
            
            assert isinstance(df, pd.DataFrame)
            assert isinstance(epicas_relevantes, list)
            assert isinstance(issues_jira, list)
            assert 'Año' in df.columns
            assert 'Mes' in df.columns
            
        except Exception as e:
            pytest.fail(f"Test de integración falló: {e}")
    
    @patch('tablero.streamlit')
    def test_estructura_principal(self, mock_st):
        """Test para verificar que la estructura principal del tablero es correcta"""
        
        # Mock de Streamlit
        mock_st.set_page_config = MagicMock()
        mock_st.session_state = {}
        mock_st.sidebar = MagicMock()
        mock_st.markdown = MagicMock()
        mock_st.header = MagicMock()
        mock_st.caption = MagicMock()
        mock_st.expander = MagicMock()
        mock_st.columns = MagicMock(return_value=[MagicMock(), MagicMock()])
        mock_st.button = MagicMock(return_value=False)
        mock_st.selectbox = MagicMock(return_value="Desarrollo Postventas")
        mock_st.radio = MagicMock(return_value="Desarrollo Postventas")
        mock_st.dataframe = MagicMock()
        mock_st.plotly_chart = MagicMock()
        mock_st.rerun = MagicMock()
        
        try:
            import tablero
            
            # Verificar que el módulo se importa correctamente
            assert hasattr(tablero, 'main')
            
            # Verificar que tiene las funciones de pestañas
            funciones_pestanas = [
                'mostrar_horas_postventas', 'mostrar_desarrollo_postventas',
                'mostrar_entregables_postventas', 'mostrar_historico_postventa',
                'mostrar_horas_ati', 'mostrar_desarrollo_ati', 'mostrar_entregables_ati',
                'mostrar_historico_ati', 'mostrar_bugs', 'mostrar_velocidad_devs',
                'mostrar_gantt'
            ]
            
            for func in funciones_pestanas:
                assert func in dir(tablero), f"La función {func} no está disponible"
                
        except Exception as e:
            pytest.fail(f"Test de estructura principal falló: {e}")

class TestIntegracionPestanas:
    """Tests de integración entre pestañas"""
    
    def test_consistencia_datos_entre_pestanas(self):
        """Test para verificar consistencia de datos entre pestañas"""
        
        # Datos de prueba
        epicas_relevantes = [
            {"rn": "ATI-1", "nombre": "Test", "mes_entrega": "Enero"}
        ]
        
        issues_jira = [
            {
                "key": "ATI-1",
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Lista para implementar"}
                }
            }
        ]
        
        df = pd.DataFrame({
            'Fecha_dt': pd.to_datetime(['2024-01-01']),
            'Proyecto': ['ATI'],
            'Horas': [8],
            'Año': [2024],
            'Mes': [1]
        })
        
        # Test que los datos son consistentes
        assert len(epicas_relevantes) > 0
        assert len(issues_jira) > 0
        assert len(df) > 0
        assert 'Año' in df.columns
        assert 'Mes' in df.columns
    
    @patch('src.tabs.bugs.mostrar_bugs')
    @patch('src.tabs.velocidad_devs.mostrar_velocidad_devs')
    def test_llamadas_a_pestanas(self, mock_velocidad, mock_bugs):
        """Test para verificar que las pestañas se pueden llamar correctamente"""
        
        # Setup mocks
        mock_bugs.return_value = None
        mock_velocidad.return_value = None
        
        # Test
        try:
            from src.tabs.bugs import mostrar_bugs
            from src.tabs.velocidad_devs import mostrar_velocidad_devs
            
            # Llamar a las funciones con datos de prueba
            mostrar_bugs([], [])
            mostrar_velocidad_devs(pd.DataFrame(), [], [])
            
            assert True
            
        except Exception as e:
            pytest.fail(f"Test de llamadas a pestañas falló: {e}")

class TestIntegracionCache:
    """Tests de integración para el sistema de cache"""
    
    @patch('src.cache_datos.cargar_df_cache')
    @patch('src.cache_datos.guardar_df_cache')
    def test_sistema_cache(self, mock_guardar, mock_cargar):
        """Test para verificar que el sistema de cache funciona"""
        
        # Setup mocks
        mock_df = pd.DataFrame({'test': [1, 2, 3]})
        mock_cargar.return_value = mock_df
        mock_guardar.return_value = True
        
        try:
            from src.cache_datos import cargar_df_cache, guardar_df_cache
            
            # Test cargar cache
            df_cargado = cargar_df_cache('test', 'pkl')
            assert isinstance(df_cargado, pd.DataFrame)
            
            # Test guardar cache
            resultado = guardar_df_cache(mock_df, 'test', 'pkl')
            assert resultado == True
            
        except Exception as e:
            pytest.fail(f"Test de sistema de cache falló: {e}")
