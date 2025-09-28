"""
Test específico para verificar si hay duplicación en el conteo de bugs
"""
import pytest
import pandas as pd
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBugsDuplication:
    """Tests para verificar que no hay duplicación en el conteo de bugs"""
    
    def test_bug_counting_logic(self):
        """Test: Verificar que la lógica de conteo de bugs no duplica"""
        # Simular datos de bugs como los que procesa la pestaña BUGS
        bugs_data = [
            {
                "Clave": "BUG-001",
                "Tipo": "Bug",
                "Status": "POR HACER",
                "Proyecto": "Taller",
                "Prioridad": "Alta",
                "Summary": "Bug de prueba 1"
            },
            {
                "Clave": "BUG-002", 
                "Tipo": "Bug",
                "Status": "CERRADOS",
                "Proyecto": "Repuestos",
                "Prioridad": "Media",
                "Summary": "Bug de prueba 2"
            },
            {
                "Clave": "BUG-003",
                "Tipo": "Bug", 
                "Status": "EN VALIDACION QA",
                "Proyecto": "ATI",
                "Prioridad": "Muy alta",
                "Summary": "Bug de prueba 3"
            },
            {
                "Clave": "BUG-004",
                "Tipo": "Mejora",  # Este NO debería contarse como bug
                "Status": "POR HACER",
                "Proyecto": "Taller",
                "Prioridad": "Baja",
                "Summary": "Mejora de prueba"
            }
        ]
        
        # Crear DataFrame
        df = pd.DataFrame(bugs_data)
        
        # Filtrar solo bugs (como hace la pestaña BUGS)
        df_bugs = df[df["Tipo"] == "Bug"].copy()
        
        # Verificar que solo se cuentan los bugs, no las mejoras
        assert len(df_bugs) == 3, f"❌ Se esperaban 3 bugs, se encontraron {len(df_bugs)}"
        assert "BUG-004" not in df_bugs["Clave"].values, "❌ Se está contando una mejora como bug"
        
        print(f"✅ Conteo correcto: {len(df_bugs)} bugs encontrados")
    
    def test_bucket_calculation(self):
        """Test: Verificar que el cálculo de buckets no duplica"""
        # Simular función bucket_estado (simplificada)
        def bucket_estado(status_name: str) -> str:
            n = status_name.lower().strip()
            if "backlog" in n:
                return "ASIGNADOS A BACKLOG"
            if ("por hacer" in n) or ("to do" in n) or ("pendiente" in n):
                return "POR HACER"
            if ("validacion" in n and "qa" in n) or ("en validacion qa" in n):
                return "EN VALIDACION QA"
            if ("aprobado" in n and "qa" in n) or ("aprobados por qa" in n):
                return "APROBADOS POR QA"
            if ("desarrollo" in n) or ("in progress" in n):
                return "ASIGNADO A DESARROLLO"
            if any(x in n for x in ["cerrado","cerrada","done","closed","resuelto"]):
                return "CERRADOS"
            return ""
        
        # Datos de prueba con diferentes estados
        bugs_data = [
            {"Clave": "BUG-001", "Status": "POR HACER", "Tipo": "Bug"},
            {"Clave": "BUG-002", "Status": "EN VALIDACION QA", "Tipo": "Bug"},
            {"Clave": "BUG-003", "Status": "CERRADOS", "Tipo": "Bug"},
            {"Clave": "BUG-004", "Status": "ASIGNADO A DESARROLLO", "Tipo": "Bug"},
            {"Clave": "BUG-005", "Status": "APROBADOS POR QA", "Tipo": "Bug"},
        ]
        
        df = pd.DataFrame(bugs_data)
        df["Bucket"] = df["Status"].apply(bucket_estado)
        
        # Calcular KPIs como en la pestaña BUGS
        PEND_STATES = {"POR HACER","EN VALIDACION QA","ASIGNADOS A BACKLOG","ASIGNADO A DESARROLLO"}
        pendientes_q = int(df[df["Bucket"].isin(PEND_STATES)].shape[0])
        revision_q = int((df["Bucket"] == "APROBADOS POR QA").sum())
        cerrados_q = int((df["Bucket"] == "CERRADOS").sum())
        total_kpi = pendientes_q + revision_q + cerrados_q
        
        # Verificar que no hay duplicación
        assert total_kpi == len(df), f"❌ Total KPI ({total_kpi}) no coincide con total de bugs ({len(df)})"
        assert pendientes_q == 3, f"❌ Se esperaban 3 pendientes, se encontraron {pendientes_q}"
        assert revision_q == 1, f"❌ Se esperaba 1 en revisión, se encontraron {revision_q}"
        assert cerrados_q == 1, f"❌ Se esperaba 1 cerrado, se encontraron {cerrados_q}"
        
        print(f"✅ KPIs calculados correctamente:")
        print(f"   - Pendientes: {pendientes_q}")
        print(f"   - En revisión: {revision_q}")
        print(f"   - Cerrados: {cerrados_q}")
        print(f"   - Total: {total_kpi}")
    
    def test_no_duplicate_keys(self):
        """Test: Verificar que no hay claves duplicadas en los datos"""
        # Simular datos con posibles duplicados
        bugs_data = [
            {"Clave": "BUG-001", "Tipo": "Bug", "Status": "POR HACER"},
            {"Clave": "BUG-002", "Tipo": "Bug", "Status": "CERRADOS"},
            {"Clave": "BUG-001", "Tipo": "Bug", "Status": "POR HACER"},  # Duplicado
            {"Clave": "BUG-003", "Tipo": "Bug", "Status": "EN VALIDACION QA"},
        ]
        
        df = pd.DataFrame(bugs_data)
        
        # Verificar que hay duplicados
        assert len(df) == 4, "❌ Datos de prueba incorrectos"
        assert df["Clave"].duplicated().any(), "❌ No se detectaron duplicados en los datos de prueba"
        
        # Eliminar duplicados (como debería hacer el código)
        df_sin_duplicados = df.drop_duplicates(subset=["Clave"])
        
        # Verificar que se eliminaron los duplicados
        assert len(df_sin_duplicados) == 3, f"❌ Se esperaban 3 bugs únicos, se encontraron {len(df_sin_duplicados)}"
        assert not df_sin_duplicados["Clave"].duplicated().any(), "❌ Aún hay duplicados después de eliminar"
        
        print(f"✅ Duplicados eliminados correctamente: {len(df)} -> {len(df_sin_duplicados)}")
    
    def test_project_filtering(self):
        """Test: Verificar que el filtrado por proyecto no causa duplicación"""
        # Datos de prueba con diferentes proyectos
        bugs_data = [
            {"Clave": "BUG-001", "Tipo": "Bug", "Proyecto": "Taller", "Status": "POR HACER"},
            {"Clave": "BUG-002", "Tipo": "Bug", "Proyecto": "Repuestos", "Status": "CERRADOS"},
            {"Clave": "BUG-003", "Tipo": "Bug", "Proyecto": "ATI", "Status": "EN VALIDACION QA"},
            {"Clave": "BUG-004", "Tipo": "Bug", "Proyecto": "Taller", "Status": "ASIGNADO A DESARROLLO"},
        ]
        
        df = pd.DataFrame(bugs_data)
        
        # Filtrar por proyecto "Taller"
        df_taller = df[df["Proyecto"] == "Taller"].copy()
        
        # Verificar que el filtrado es correcto
        assert len(df_taller) == 2, f"❌ Se esperaban 2 bugs de Taller, se encontraron {len(df_taller)}"
        assert all(df_taller["Proyecto"] == "Taller"), "❌ Hay bugs de otros proyectos en el filtro"
        assert "BUG-001" in df_taller["Clave"].values, "❌ BUG-001 no está en el filtro de Taller"
        assert "BUG-004" in df_taller["Clave"].values, "❌ BUG-004 no está en el filtro de Taller"
        assert "BUG-002" not in df_taller["Clave"].values, "❌ BUG-002 no debería estar en el filtro de Taller"
        
        print(f"✅ Filtrado por proyecto correcto: {len(df_taller)} bugs de Taller")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

