"""
Tests para verificar que todos los imports funcionan correctamente
"""

import pytest
import sys
import os

# Agregar el directorio raíz al path para los imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestImportsPrincipales:
    """Tests para imports del archivo principal"""
    
    def test_import_tablero_principal(self):
        """Verificar que se puede importar el tablero principal"""
        try:
            import tablero
            assert hasattr(tablero, 'main')
        except ImportError as e:
            pytest.fail(f"No se pudo importar tablero.py: {e}")
    
    def test_import_modulos_src(self):
        """Verificar que se pueden importar los módulos de src"""
        try:
            from src.jira_conexion import get_jira
            from src.tempo_conexion import tempo_get
            from src.cache_datos import cargar_df_cache, guardar_df_cache
            assert True
        except ImportError as e:
            pytest.fail(f"No se pudieron importar módulos de src: {e}")

class TestImportsTabs:
    """Tests para imports de las pestañas"""
    
    def test_import_todas_las_tabs(self):
        """Verificar que se pueden importar todas las pestañas"""
        tabs_esperadas = [
            'horas_postventas', 'desarrollo_postventas', 'entregables_postventas',
            'historico_postventa', 'horas_ati', 'desarrollo_ati', 'entregables_ati',
            'historico_ati', 'bugs', 'velocidad_devs', 'gantt'
        ]
        
        for tab in tabs_esperadas:
            try:
                module = __import__(f'src.tabs.{tab}', fromlist=['mostrar_' + tab.replace('_', '_')])
                # Verificar que tiene la función mostrar correspondiente
                func_name = f'mostrar_{tab}'
                assert hasattr(module, func_name), f"El módulo {tab} no tiene la función {func_name}"
            except ImportError as e:
                pytest.fail(f"No se pudo importar src.tabs.{tab}: {e}")

class TestImportsUtils:
    """Tests para imports de utilidades"""
    
    def test_import_configuracion(self):
        """Verificar que se puede importar configuracion"""
        try:
            from src.utils.configuracion import (
                MAPEO_TEM, RESUMEN_A_PROYECTO, PROYECTOS_POSTVENTA, PROYECTOS_ATI,
                cargar_epicas_relevantes, cargar_datos_historicos, cargar_issues_jira_cache,
                cargar_datos_principales, configurar_sidebar, aplicar_estilos_css
            )
            assert True
        except ImportError as e:
            pytest.fail(f"No se pudo importar src.utils.configuracion: {e}")
    
    def test_import_utilidades(self):
        """Verificar que se puede importar utilidades"""
        try:
            from src.utils import utilidades
            assert True
        except ImportError as e:
            pytest.fail(f"No se pudo importar src.utils.utilidades: {e}")

class TestEstructuraModular:
    """Tests para verificar la estructura modular"""
    
    def test_estructura_directorios(self):
        """Verificar que existen todos los directorios necesarios"""
        directorios_esperados = [
            'src',
            'src/tabs',
            'src/utils',
            'tests'
        ]
        
        for directorio in directorios_esperados:
            assert os.path.exists(directorio), f"El directorio {directorio} no existe"
    
    def test_archivos_init(self):
        """Verificar que existen los archivos __init__.py necesarios"""
        archivos_init_esperados = [
            'src/__init__.py',
            'src/tabs/__init__.py',
            'src/utils/__init__.py',
            'tests/__init__.py'
        ]
        
        for archivo in archivos_init_esperados:
            assert os.path.exists(archivo), f"El archivo {archivo} no existe"
