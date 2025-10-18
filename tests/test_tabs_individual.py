"""
Tests unitarios para cada pestaña individual
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestTabBugs:
    """Tests para la pestaña de Bugs"""
    
    @patch('src.tabs.bugs.get_jira')
    @patch('src.tabs.bugs.cache_path')
    @patch('src.tabs.bugs.cargar_epicas_relevantes')
    def test_mostrar_bugs_funciona(self, mock_cargar_epicas, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_bugs"""
        from src.tabs.bugs import mostrar_bugs
        
        # Setup mocks
        mock_cargar_epicas.return_value = []
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_bugs([], [])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_bugs falló: {e}")

class TestTabVelocidadDevs:
    """Tests para la pestaña de Velocidad de Devs"""
    
    @patch('src.tabs.velocidad_devs.get_jira')
    @patch('src.tabs.velocidad_devs.cache_path')
    def test_mostrar_velocidad_devs_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_velocidad_devs"""
        from src.tabs.velocidad_devs import mostrar_velocidad_devs
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_velocidad_devs(pd.DataFrame(), [], [])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_velocidad_devs falló: {e}")

class TestTabDesarrolloATI:
    """Tests para la pestaña de Desarrollo ATI"""
    
    @patch('src.tabs.desarrollo_ati.get_jira')
    @patch('src.tabs.desarrollo_ati.cache_path')
    def test_mostrar_desarrollo_ati_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_desarrollo_ati"""
        from src.tabs.desarrollo_ati import mostrar_desarrollo_ati
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_desarrollo_ati([])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_desarrollo_ati falló: {e}")

class TestTabDesarrolloPostventas:
    """Tests para la pestaña de Desarrollo Postventas"""
    
    @patch('src.tabs.desarrollo_postventas.get_jira')
    @patch('src.tabs.desarrollo_postventas.cache_path')
    def test_mostrar_desarrollo_postventas_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_desarrollo_postventas"""
        from src.tabs.desarrollo_postventas import mostrar_desarrollo_postventas
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_desarrollo_postventas([])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_desarrollo_postventas falló: {e}")

class TestTabEntregablesATI:
    """Tests para la pestaña de Entregables ATI"""
    
    @patch('src.tabs.entregables_ati.get_jira')
    @patch('src.tabs.entregables_ati.cache_path')
    def test_mostrar_entregables_ati_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_entregables_ati"""
        from src.tabs.entregables_ati import mostrar_entregables_ati
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_entregables_ati([])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_entregables_ati falló: {e}")

class TestTabEntregablesPostventas:
    """Tests para la pestaña de Entregables Postventas"""
    
    @patch('src.tabs.entregables_postventas.get_jira')
    @patch('src.tabs.entregables_postventas.cache_path')
    def test_mostrar_entregables_postventas_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_entregables_postventas"""
        from src.tabs.entregables_postventas import mostrar_entregables_postventas
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_entregables_postventas([])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_entregables_postventas falló: {e}")

class TestTabHistoricoATI:
    """Tests para la pestaña de Histórico ATI"""
    
    @patch('src.tabs.historico_ati.get_jira')
    @patch('src.tabs.historico_ati.cache_path')
    def test_mostrar_historico_ati_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_historico_ati"""
        from src.tabs.historico_ati import mostrar_historico_ati
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_historico_ati([], [])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_historico_ati falló: {e}")

class TestTabHistoricoPostventa:
    """Tests para la pestaña de Histórico Postventa"""
    
    @patch('src.tabs.historico_postventa.get_jira')
    @patch('src.tabs.historico_postventa.cache_path')
    def test_mostrar_historico_postventa_funciona(self, mock_cache_path, mock_get_jira):
        """Test básico para mostrar_historico_postventa"""
        from src.tabs.historico_postventa import mostrar_historico_postventa
        
        # Setup mocks
        mock_cache_path.return_value = 'test_cache.pkl'
        mock_jira = MagicMock()
        mock_jira._get_json.return_value = {"issues": []}
        mock_get_jira.return_value = mock_jira
        
        # Test
        try:
            mostrar_historico_postventa([], [])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_historico_postventa falló: {e}")

class TestTabHorasATI:
    """Tests para la pestaña de Horas ATI"""
    
    def test_mostrar_horas_ati_funciona(self):
        """Test básico para mostrar_horas_ati"""
        from src.tabs.horas_ati import mostrar_horas_ati
        
        # Test
        try:
            mostrar_horas_ati()
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_horas_ati falló: {e}")

class TestTabHorasPostventas:
    """Tests para la pestaña de Horas Postventas"""
    
    def test_mostrar_horas_postventas_funciona(self):
        """Test básico para mostrar_horas_postventas"""
        from src.tabs.horas_postventas import mostrar_horas_postventas
        
        # Test
        try:
            mostrar_horas_postventas()
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_horas_postventas falló: {e}")

class TestTabGantt:
    """Tests para la pestaña de Gantt"""
    
    def test_mostrar_gantt_funciona(self):
        """Test básico para mostrar_gantt"""
        from src.tabs.gantt import mostrar_gantt
        
        # Test
        try:
            mostrar_gantt([])
            assert True
        except Exception as e:
            pytest.fail(f"mostrar_gantt falló: {e}")
