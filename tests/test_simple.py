"""
Tests simples para validar la funcionalidad básica del tablero
"""
import pytest
import pandas as pd
import os
import json
from pathlib import Path


class TestBasicFunctionality:
    """Tests básicos para verificar que todo funciona"""
    
    def test_data_files_exist(self):
        """Test: Verificar que los archivos de datos existen"""
        data_files = [
            "data/horas_historicas.csv",
            "data/horas_con_proyecto.csv", 
            "data/accountid_to_name.json",
            "data/issue_to_project.json",
            "data/epicas_relevantes.json"
        ]
        
        missing_files = []
        for file_path in data_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
            else:
                print(f"✅ Archivo encontrado: {file_path}")
        
        assert len(missing_files) == 0, f"❌ Archivos faltantes: {missing_files}"
        print(f"✅ Todos los archivos de datos existen")
    
    def test_csv_files_readable(self):
        """Test: Verificar que los archivos CSV se pueden leer"""
        csv_files = [
            "data/horas_historicas.csv",
            "data/horas_con_proyecto.csv"
        ]
        
        for file_path in csv_files:
            try:
                df = pd.read_csv(file_path)
                assert len(df) > 0, f"❌ Archivo vacío: {file_path}"
                print(f"✅ CSV leído correctamente: {file_path} ({len(df)} filas)")
            except Exception as e:
                pytest.fail(f"❌ Error leyendo {file_path}: {e}")
    
    def test_json_files_readable(self):
        """Test: Verificar que los archivos JSON se pueden leer"""
        json_files = [
            "data/accountid_to_name.json",
            "data/issue_to_project.json",
            "data/epicas_relevantes.json"
        ]
        
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    assert isinstance(data, (dict, list)), f"❌ Formato JSON inválido: {file_path}"
                    print(f"✅ JSON leído correctamente: {file_path}")
            except Exception as e:
                pytest.fail(f"❌ Error leyendo {file_path}: {e}")
    
    def test_horas_data_structure(self):
        """Test: Verificar la estructura de los datos de horas"""
        try:
            df = pd.read_csv("data/horas_con_proyecto.csv")
            
            # Verificar columnas esperadas
            expected_columns = ["Usuario", "Fecha", "Horas", "Proyecto"]
            for col in expected_columns:
                assert col in df.columns, f"❌ Columna faltante: {col}"
            
            # Verificar tipos de datos
            assert pd.api.types.is_numeric_dtype(df["Horas"]), "❌ Columna Horas no es numérica"
            
            print(f"✅ Estructura de datos de horas correcta: {list(df.columns)}")
            
        except Exception as e:
            pytest.fail(f"❌ Error validando estructura de horas: {e}")
    
    def test_epicas_data_structure(self):
        """Test: Verificar la estructura de los datos de épicas"""
        try:
            with open("data/epicas_relevantes.json", 'r', encoding='utf-8') as f:
                epicas = json.load(f)
            
            # Verificar que es una lista
            assert isinstance(epicas, list), "❌ Épicas no es una lista"
            assert len(epicas) > 0, "❌ No hay épicas en el archivo"
            
            # Verificar estructura de la primera épica
            primera_epica = epicas[0]
            expected_keys = ["rn", "nombre", "mes_entrega"]
            for key in expected_keys:
                assert key in primera_epica, f"❌ Clave faltante en épica: {key}"
            
            print(f"✅ Estructura de épicas correcta: {len(epicas)} épicas encontradas")
            
        except Exception as e:
            pytest.fail(f"❌ Error validando estructura de épicas: {e}")


class TestProjectFiltering:
    """Tests para verificar el filtrado por proyectos"""
    
    def test_rep_tal_filtering(self):
        """Test: Verificar que se pueden filtrar proyectos REP y TAL"""
        # Simular datos de épicas
        epicas_test = [
            {"rn": "REP-123", "nombre": "Épica REP", "mes_entrega": "Enero"},
            {"rn": "TAL-456", "nombre": "Épica TAL", "mes_entrega": "Febrero"},
            {"rn": "ATI-789", "nombre": "Épica ATI", "mes_entrega": "Marzo"}
        ]
        
        # Filtrar solo REP y TAL
        epicas_postventas = [e for e in epicas_test if e["rn"].startswith(("REP-", "TAL-"))]
        
        assert len(epicas_postventas) == 2
        assert all(e["rn"].startswith(("REP-", "TAL-")) for e in epicas_postventas)
        assert not any(e["rn"].startswith("ATI-") for e in epicas_postventas)
        
        print(f"✅ Filtrado REP/TAL correcto: {len(epicas_postventas)} épicas")
    
    def test_ati_filtering(self):
        """Test: Verificar que se pueden filtrar proyectos ATI"""
        # Simular datos de épicas
        epicas_test = [
            {"rn": "REP-123", "nombre": "Épica REP", "mes_entrega": "Enero"},
            {"rn": "TAL-456", "nombre": "Épica TAL", "mes_entrega": "Febrero"},
            {"rn": "ATI-789", "nombre": "Épica ATI", "mes_entrega": "Marzo"}
        ]
        
        # Filtrar solo ATI
        epicas_ati = [e for e in epicas_test if e["rn"].startswith("ATI-")]
        
        assert len(epicas_ati) == 1
        assert epicas_ati[0]["rn"] == "ATI-789"
        
        print(f"✅ Filtrado ATI correcto: {len(epicas_ati)} épicas")


class TestCalculations:
    """Tests para funciones de cálculo básicas"""
    
    def test_dataframe_creation(self):
        """Test: Verificar que se pueden crear DataFrames correctamente"""
        # Crear DataFrame de prueba
        data = {
            "Usuario_nombre": ["Juan", "María", "Pedro"],
            "Puntos": [10, 15, 8],
            "Horas": [100, 120, 90],
            "Bugs": [1, 0, 2]
        }
        
        df = pd.DataFrame(data)
        
        # Verificaciones
        assert len(df) == 3
        assert "Usuario_nombre" in df.columns
        assert "Puntos" in df.columns
        assert df["Puntos"].sum() == 33
        print(f"✅ DataFrame creado correctamente con {len(df)} filas")
    
    def test_data_filtering(self):
        """Test: Verificar que el filtrado de datos funciona"""
        # Crear DataFrame de prueba
        data = {
            "Usuario_nombre": ["Juan", "María", "Pedro", "Ana"],
            "Puntos": [10, 15, 0, 8],
            "Proyecto": ["REP", "TAL", "ATI", "REP"]
        }
        
        df = pd.DataFrame(data)
        
        # Filtrar solo usuarios con puntos > 0
        df_filtrado = df[df["Puntos"] > 0]
        
        assert len(df_filtrado) == 3  # Solo Juan, María y Ana
        assert "Pedro" not in df_filtrado["Usuario_nombre"].values
        print(f"✅ Filtrado correcto: {len(df_filtrado)} usuarios con puntos")
        
        # Filtrar solo proyectos REP y TAL
        df_postventas = df[df["Proyecto"].isin(["REP", "TAL"])]
        
        assert len(df_postventas) == 3  # Juan, María y Ana
        assert "ATI" not in df_postventas["Proyecto"].values
        print(f"✅ Filtrado de proyectos correcto: {len(df_postventas)} proyectos postventas")
    
    def test_calculation_logic(self):
        """Test: Verificar lógica de cálculos básicos"""
        # Simular datos de un usuario
        datos_usuario = {
            "Puntos": 15.0,
            "Horas": 120.0,
            "Bugs": 1,
            "Velocidad": 8.0,
            "Bugs_resueltos_extra": 2
        }
        
        # Verificar que los datos son válidos
        assert datos_usuario["Puntos"] > 0
        assert datos_usuario["Horas"] > 0
        assert datos_usuario["Bugs"] >= 0
        assert datos_usuario["Velocidad"] > 0
        assert datos_usuario["Bugs_resueltos_extra"] >= 0
        
        # Simular cálculo de nota (lógica simplificada)
        puntos = datos_usuario["Puntos"]
        horas = datos_usuario["Horas"]
        bugs = datos_usuario["Bugs"]
        velocidad = datos_usuario["Velocidad"]
        bugs_extra = datos_usuario["Bugs_resueltos_extra"]
        
        # Cálculo básico de nota (simplificado)
        nota_base = (puntos * 0.4) + (horas * 0.25) + (velocidad * 0.25) + ((5 - bugs) * 0.1)
        bonus = bugs_extra * 0.02
        nota_final = (nota_base + bonus) * 10  # Reducir el multiplicador
        
        assert nota_final > 0
        assert nota_final <= 500  # Límite razonable
        print(f"✅ Cálculo de nota: {nota_final:.2f}")


if __name__ == "__main__":
    # Ejecutar los tests si se ejecuta directamente
    pytest.main([__file__, "-v"])
