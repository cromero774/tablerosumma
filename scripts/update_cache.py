#!/usr/bin/env python3
"""
Script para actualizar automáticamente el cache del tablero
Ejecuta las funciones de carga de datos y genera pre-cálculos
"""

import os
import sys
import pickle
from datetime import datetime, timedelta
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

# Importar las funciones del tablero
from src.jira_conexion import JiraAPI
from dotenv import load_dotenv

def main():
    """Función principal para actualizar el cache"""
    print("🚀 Iniciando actualización automática de cache...")
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Configurar conexión a Jira
    jira_url = os.getenv("JIRA_URL")
    jira_user = os.getenv("JIRA_USER") 
    jira_token = os.getenv("JIRA_TOKEN")
    
    if not all([jira_url, jira_user, jira_token]):
        print("❌ Error: Faltan variables de entorno de Jira")
        return False
    
    try:
        # Crear conexión a Jira
        jira = JiraAPI(jira_url, jira_user, jira_token)
        print("✅ Conexión a Jira establecida")
        
        # Importar funciones del tablero
        from tablero import cargar_datos_velocidad, generar_pre_calculos_velocidad
        
        # Configurar fechas (últimos 6 meses)
        fecha_fin = datetime.now().strftime("%Y-%m-%d")
        fecha_inicio = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        
        print(f"📅 Actualizando cache desde {fecha_inicio} hasta {fecha_fin}")
        
        # Cargar datos de velocidad (esto generará pre-cálculos automáticamente)
        historias, bugs = cargar_datos_velocidad(
            jira, 
            fecha_inicio, 
            fecha_fin, 
            "Todos", 
            True  # Force refresh
        )
        
        print(f"✅ Cache actualizado: {len(historias)} historias, {len(bugs)} bugs")
        
        # Verificar que se generaron pre-cálculos
        cache_file = f"data/cache/velocidad_data_Todos_{fecha_inicio}_{fecha_fin}.pkl"
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
                if 'pre_calculos' in cache_data:
                    print("✅ Pre-cálculos generados correctamente")
                else:
                    print("⚠️ Cache generado sin pre-cálculos")
        
        print("🎉 Actualización completada exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error durante la actualización: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
