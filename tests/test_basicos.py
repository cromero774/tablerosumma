"""
Tests básicos y simplificados para el tablero SUMMA
"""

import pytest
import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestEstructuraBasica:
    """Tests para la estructura básica del proyecto"""
    
    def test_archivos_principales_existen(self):
        """Verificar que existen los archivos principales"""
        archivos_esperados = [
            'tablero.py',
            'src/__init__.py',
            'src/tabs/__init__.py',
            'src/utils/__init__.py',
            'requirements.txt'
        ]
        
        for archivo in archivos_esperados:
            assert os.path.exists(archivo), f"El archivo {archivo} no existe"
    
    def test_directorios_existen(self):
        """Verificar que existen los directorios principales"""
        directorios_esperados = [
            'src',
            'src/tabs',
            'src/utils',
            'tests'
        ]
        
        for directorio in directorios_esperados:
            assert os.path.exists(directorio), f"El directorio {directorio} no existe"
            assert os.path.isdir(directorio), f"{directorio} no es un directorio"

class TestImportsBasicos:
    """Tests básicos para imports"""
    
    def test_import_tablero_principal(self):
        """Verificar que se puede importar el tablero principal"""
        try:
            import tablero
            assert hasattr(tablero, 'main')
        except ImportError as e:
            pytest.fail(f"No se pudo importar tablero.py: {e}")
    
    def test_import_modulos_src(self):
        """Verificar que se pueden importar los módulos básicos de src"""
        try:
            from src import jira_conexion
            from src import tempo_conexion
            from src import cache_datos
            assert True
        except ImportError as e:
            pytest.fail(f"No se pudieron importar módulos de src: {e}")
    
    def test_import_utils(self):
        """Verificar que se pueden importar las utilidades"""
        try:
            from src.utils import configuracion
            assert hasattr(configuracion, 'MAPEO_TEM')
            assert hasattr(configuracion, 'PROYECTOS_ATI')
            assert hasattr(configuracion, 'PROYECTOS_POSTVENTA')
        except ImportError as e:
            pytest.fail(f"No se pudo importar src.utils.configuracion: {e}")

class TestPestanasBasicas:
    """Tests básicos para las pestañas"""
    
    def test_todas_las_pestanas_se_importan(self):
        """Verificar que todas las pestañas se pueden importar"""
        pestanas = [
            'bugs', 'desarrollo_ati', 'desarrollo_postventas',
            'entregables_ati', 'entregables_postventas', 'gantt',
            'historico_ati', 'historico_postventa', 'horas_ati',
            'horas_postventas', 'velocidad_devs'
        ]
        
        for pestaña in pestanas:
            try:
                module = __import__(f'src.tabs.{pestaña}', fromlist=[''])
                assert module is not None
            except ImportError as e:
                pytest.fail(f"No se pudo importar src.tabs.{pestaña}: {e}")
    
    def test_funciones_mostrar_existen(self):
        """Verificar que las funciones mostrar_* existen en cada pestaña"""
        pestanas_funciones = {
            'bugs': 'mostrar_bugs',
            'desarrollo_ati': 'mostrar_desarrollo_ati',
            'desarrollo_postventas': 'mostrar_desarrollo_postventas',
            'entregables_ati': 'mostrar_entregables_ati',
            'entregables_postventas': 'mostrar_entregables_postventas',
            'gantt': 'mostrar_gantt',
            'historico_ati': 'mostrar_historico_ati',
            'historico_postventa': 'mostrar_historico_postventa',
            'horas_ati': 'mostrar_horas_ati',
            'horas_postventas': 'mostrar_horas_postventas',
            'velocidad_devs': 'mostrar_velocidad_devs'
        }
        
        for pestaña, funcion in pestanas_funciones.items():
            try:
                module = __import__(f'src.tabs.{pestaña}', fromlist=[funcion])
                assert hasattr(module, funcion), f"La función {funcion} no existe en {pestaña}"
            except ImportError as e:
                pytest.fail(f"No se pudo importar {pestaña}: {e}")

class TestConfiguracionBasica:
    """Tests básicos para la configuración"""
    
    def test_constantes_configuracion(self):
        """Verificar que las constantes de configuración están definidas"""
        try:
            from src.utils.configuracion import (
                MAPEO_TEM, RESUMEN_A_PROYECTO, 
                PROYECTOS_POSTVENTA, PROYECTOS_ATI
            )
            
            # Verificar tipos
            assert isinstance(MAPEO_TEM, dict)
            assert isinstance(RESUMEN_A_PROYECTO, dict)
            assert isinstance(PROYECTOS_POSTVENTA, list)
            assert isinstance(PROYECTOS_ATI, list)
            
            # Verificar que no están vacíos
            assert len(MAPEO_TEM) > 0
            assert len(RESUMEN_A_PROYECTO) > 0
            assert len(PROYECTOS_POSTVENTA) > 0
            assert len(PROYECTOS_ATI) > 0
            
        except ImportError as e:
            pytest.fail(f"No se pudo importar constantes de configuración: {e}")
    
    def test_funciones_configuracion_existen(self):
        """Verificar que las funciones de configuración existen"""
        try:
            from src.utils.configuracion import (
                cargar_epicas_relevantes, cargar_datos_historicos,
                cargar_issues_jira_cache, cargar_datos_principales,
                configurar_sidebar, aplicar_estilos_css
            )
            
            # Verificar que son funciones
            assert callable(cargar_epicas_relevantes)
            assert callable(cargar_datos_historicos)
            assert callable(cargar_issues_jira_cache)
            assert callable(cargar_datos_principales)
            assert callable(configurar_sidebar)
            assert callable(aplicar_estilos_css)
            
        except ImportError as e:
            pytest.fail(f"No se pudo importar funciones de configuración: {e}")

class TestFuncionalidadBasica:
    """Tests básicos de funcionalidad"""
    
    def test_tablero_tiene_funcion_main(self):
        """Verificar que el tablero tiene la función main"""
        try:
            import tablero
            assert hasattr(tablero, 'main')
            assert callable(tablero.main)
        except ImportError as e:
            pytest.fail(f"No se pudo importar tablero: {e}")
    
    def test_modularizacion_completa(self):
        """Verificar que la modularización está completa"""
        # Verificar que el tablero principal existe
        assert os.path.exists('tablero.py')
        
        # Verificar que las pestañas están en src/tabs/
        pestanas = [
            'bugs.py', 'desarrollo_ati.py', 'desarrollo_postventas.py',
            'entregables_ati.py', 'entregables_postventas.py', 'gantt.py',
            'historico_ati.py', 'historico_postventa.py', 'horas_ati.py',
            'horas_postventas.py', 'velocidad_devs.py'
        ]
        
        for pestaña in pestanas:
            archivo = f'src/tabs/{pestaña}'
            assert os.path.exists(archivo), f"El archivo {archivo} no existe"
    
    def test_estructura_imports_correcta(self):
        """Verificar que la estructura de imports es correcta"""
        try:
            # Verificar que el tablero principal se puede importar
            import tablero
            
            # Verificar que tiene las importaciones de las pestañas
            codigo_tablero = open('tablero.py', 'r', encoding='utf-8').read()
            
            # Verificar que importa las pestañas
            assert 'from src.tabs.' in codigo_tablero
            assert 'from src.utils.configuracion' in codigo_tablero
            
        except Exception as e:
            pytest.fail(f"Error verificando estructura de imports: {e}")
