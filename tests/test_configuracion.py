"""
Tests para src/utils/configuracion.py
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.utils.configuracion import (
    MAPEO_TEM, RESUMEN_A_PROYECTO, PROYECTOS_POSTVENTA, PROYECTOS_ATI,
    cargar_epicas_relevantes, cargar_datos_historicos, cargar_issues_jira_cache,
    cargar_datos_principales, configurar_sidebar, aplicar_estilos_css
)

class TestConstantes:
    """Tests para las constantes de configuración"""
    
    def test_mapeo_tem_estructura(self):
        """Verificar que MAPEO_TEM tiene la estructura correcta"""
        assert isinstance(MAPEO_TEM, dict)
        assert "TEM-1" in MAPEO_TEM
        assert isinstance(MAPEO_TEM["TEM-1"], tuple)
        assert len(MAPEO_TEM["TEM-1"]) == 2
    
    def test_resumen_a_proyecto_estructura(self):
        """Verificar que RESUMEN_A_PROYECTO tiene la estructura correcta"""
        assert isinstance(RESUMEN_A_PROYECTO, dict)
        assert "MAIPU - SUMMA - ESCRITURA RF POSVENTA" in RESUMEN_A_PROYECTO
        assert RESUMEN_A_PROYECTO["MAIPU - SUMMA - ESCRITURA RF POSVENTA"] == "AFUS"
    
    def test_proyectos_postventa_estructura(self):
        """Verificar que PROYECTOS_POSTVENTA es una lista"""
        assert isinstance(PROYECTOS_POSTVENTA, list)
        assert len(PROYECTOS_POSTVENTA) > 0
    
    def test_proyectos_ati_estructura(self):
        """Verificar que PROYECTOS_ATI es una lista"""
        assert isinstance(PROYECTOS_ATI, list)
        assert len(PROYECTOS_ATI) > 0

class TestFuncionesConfiguracion:
    """Tests para las funciones de configuración"""
    
    @patch('src.utils.configuracion.cargar_json_cache')
    def test_cargar_epicas_relevantes(self, mock_cargar_json):
        """Test para cargar_epicas_relevantes"""
        mock_data = [
            {"rn": "ATI-1", "nombre": "Test", "mes_entrega": "Enero"}
        ]
        mock_cargar_json.return_value = mock_data
        
        result = cargar_epicas_relevantes()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["rn"] == "ATI-1"
    
    @patch('src.utils.configuracion.cargar_df_cache')
    def test_cargar_datos_historicos(self, mock_cargar_df):
        """Test para cargar_datos_historicos"""
        mock_df = pd.DataFrame({
            'Fecha': ['2024-01-01', '2024-01-02'],
            'Proyecto': ['ATI', 'ATI'],
            'Horas': [8, 6]
        })
        mock_cargar_df.return_value = mock_df
        
        result = cargar_datos_historicos()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'Fecha' in result.columns
    
    @patch('src.utils.configuracion.cargar_df_cache')
    def test_cargar_datos_principales(self, mock_cargar_df):
        """Test para cargar_datos_principales"""
        mock_df = pd.DataFrame({
            'Fecha_dt': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'Proyecto': ['ATI', 'ATI'],
            'Horas': [8, 6]
        })
        mock_cargar_df.return_value = mock_df
        
        result = cargar_datos_principales()
        
        assert isinstance(result, pd.DataFrame)
        assert 'Año' in result.columns
        assert 'Mes' in result.columns
        assert result['Año'].iloc[0] == 2024
        assert result['Mes'].iloc[0] == 1
    
    def test_configurar_sidebar(self):
        """Test para configurar_sidebar"""
        # Esta función principalmente configura Streamlit, 
        # verificar que no lanza errores
        try:
            configurar_sidebar()
            assert True
        except Exception:
            pytest.fail("configurar_sidebar no debería lanzar errores")
    
    def test_aplicar_estilos_css(self):
        """Test para aplicar_estilos_css"""
        # Esta función aplica CSS a Streamlit,
        # verificar que no lanza errores
        try:
            aplicar_estilos_css()
            assert True
        except Exception:
            pytest.fail("aplicar_estilos_css no debería lanzar errores")
