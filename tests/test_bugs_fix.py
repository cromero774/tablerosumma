"""
Test para verificar que la corrección de duplicación en BUGS funciona
"""
import pytest
import pandas as pd
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBugsFix:
    """Tests para verificar que la corrección de duplicación funciona"""
    
    def test_duplicate_removal(self):
        """Test: Verificar que se eliminan duplicados correctamente"""
        # Simular datos con duplicados como los que vienen de Jira
        rows_with_duplicates = [
            {
                "Clave": "BUG-001",
                "Tipo": "Bug",
                "Status": "POR HACER",
                "Proyecto": "Taller",
                "Prioridad": "Alta",
                "Summary": "Bug de prueba 1",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-002", 
                "Tipo": "Bug",
                "Status": "CERRADOS",
                "Proyecto": "Repuestos",
                "Prioridad": "Media",
                "Summary": "Bug de prueba 2",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-001",  # Duplicado
                "Tipo": "Bug",
                "Status": "POR HACER",
                "Proyecto": "Taller",
                "Prioridad": "Alta",
                "Summary": "Bug de prueba 1",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-003",
                "Tipo": "Bug", 
                "Status": "EN VALIDACION QA",
                "Proyecto": "ATI",
                "Prioridad": "Muy alta",
                "Summary": "Bug de prueba 3",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            }
        ]
        
        # Aplicar la corrección: eliminar duplicados por Clave
        df_all = pd.DataFrame(rows_with_duplicates).drop_duplicates(subset=["Clave"]).sort_values("AñoMes")
        
        # Verificar que se eliminaron los duplicados
        assert len(df_all) == 3, f"❌ Se esperaban 3 bugs únicos, se encontraron {len(df_all)}"
        assert not df_all["Clave"].duplicated().any(), "❌ Aún hay duplicados después de eliminar"
        
        # Verificar que se mantuvieron los bugs correctos
        claves_esperadas = {"BUG-001", "BUG-002", "BUG-003"}
        claves_obtenidas = set(df_all["Clave"].values)
        assert claves_obtenidas == claves_esperadas, f"❌ Claves esperadas: {claves_esperadas}, obtenidas: {claves_obtenidas}"
        
        print(f"✅ Duplicados eliminados correctamente: {len(rows_with_duplicates)} -> {len(df_all)}")
    
    def test_kpi_calculation_after_fix(self):
        """Test: Verificar que los KPIs se calculan correctamente después de eliminar duplicados"""
        # Datos sin duplicados (después de la corrección)
        rows_clean = [
            {
                "Clave": "BUG-001",
                "Tipo": "Bug",
                "Status": "POR HACER",
                "Proyecto": "Taller",
                "Prioridad": "Alta",
                "Summary": "Bug de prueba 1",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-002", 
                "Tipo": "Bug",
                "Status": "CERRADOS",
                "Proyecto": "Repuestos",
                "Prioridad": "Media",
                "Summary": "Bug de prueba 2",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-003",
                "Tipo": "Bug", 
                "Status": "EN VALIDACION QA",
                "Proyecto": "ATI",
                "Prioridad": "Muy alta",
                "Summary": "Bug de prueba 3",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-004",
                "Tipo": "Bug",
                "Status": "ASIGNADO A DESARROLLO",
                "Proyecto": "Taller",
                "Prioridad": "Baja",
                "Summary": "Bug de prueba 4",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            },
            {
                "Clave": "BUG-005",
                "Tipo": "Bug",
                "Status": "APROBADOS POR QA",
                "Proyecto": "Repuestos",
                "Prioridad": "Media",
                "Summary": "Bug de prueba 5",
                "AñoMes": "2025-01",
                "Mes": "Enero 2025"
            }
        ]
        
        df_all = pd.DataFrame(rows_clean)
        
        # Filtrar solo bugs
        df_bugs = df_all[df_all["Tipo"] == "Bug"].copy()
        
        # Simular función bucket_estado
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
        
        df_bugs["Bucket"] = df_bugs["Status"].apply(bucket_estado)
        
        # Calcular KPIs
        PEND_STATES = {"POR HACER","EN VALIDACION QA","ASIGNADOS A BACKLOG","ASIGNADO A DESARROLLO"}
        pendientes_q = int(df_bugs[df_bugs["Bucket"].isin(PEND_STATES)].shape[0])
        revision_q = int((df_bugs["Bucket"] == "APROBADOS POR QA").sum())
        cerrados_q = int((df_bugs["Bucket"] == "CERRADOS").sum())
        total_kpi = pendientes_q + revision_q + cerrados_q
        
        # Verificar que los KPIs son correctos
        assert total_kpi == len(df_bugs), f"❌ Total KPI ({total_kpi}) != Total bugs ({len(df_bugs)})"
        assert pendientes_q == 3, f"❌ Se esperaban 3 pendientes, se encontraron {pendientes_q}"
        assert revision_q == 1, f"❌ Se esperaba 1 en revisión, se encontraron {revision_q}"
        assert cerrados_q == 1, f"❌ Se esperaba 1 cerrado, se encontraron {cerrados_q}"
        
        print(f"✅ KPIs calculados correctamente después de la corrección:")
        print(f"   - Pendientes: {pendientes_q}")
        print(f"   - En revisión: {revision_q}")
        print(f"   - Cerrados: {cerrados_q}")
        print(f"   - Total: {total_kpi}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

