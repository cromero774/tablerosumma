#!/usr/bin/env python3
"""
Script para actualizar la base de datos y prepararla para subir a Google Drive
Incluye: sincronización completa, compresión (opcional), y verificación
"""
import os
import sys
import subprocess
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_completa import TableroDatabase

def obtener_tamaño_archivo(ruta):
    """Obtener tamaño del archivo en MB"""
    if os.path.exists(ruta):
        size_bytes = os.path.getsize(ruta)
        size_mb = size_bytes / (1024 * 1024)
        return size_bytes, size_mb
    return 0, 0

def main():
    print("🔄 Actualización de Base de Datos para Render")
    print("=" * 50)
    
    db_path = "data/tablero_completo.db"
    
    # Verificar tamaño actual
    size_bytes, size_mb = obtener_tamaño_archivo(db_path)
    if size_bytes > 0:
        print(f"📊 Tamaño actual: {size_mb:.2f} MB ({size_bytes:,} bytes)")
    else:
        print("⚠️  Base de datos no existe, se creará nueva")
    
    # Confirmar
    respuesta = input("\n¿Deseas sincronizar la base de datos ahora? (s/n): ")
    if respuesta.lower() != 's':
        print("❌ Operación cancelada")
        return 1
    
    # Crear instancia de la base de datos
    db = TableroDatabase(db_path)
    
    try:
        print("\n🔌 Conectando a la base de datos...")
        db.conectar()
        
        print("\n🚀 Iniciando sincronización completa...")
        print("⚠️  Esto puede tomar 40-60 minutos...")
        
        # Ejecutar sincronización completa
        db.sincronizacion_completa()
        
        # Verificar tamaño final
        size_bytes_final, size_mb_final = obtener_tamaño_archivo(db_path)
        print(f"\n✅ Sincronización completada!")
        print(f"📊 Tamaño final: {size_mb_final:.2f} MB ({size_bytes_final:,} bytes)")
        
        # Mostrar diferencia
        if size_bytes > 0:
            diferencia = size_mb_final - size_mb
            print(f"📈 Diferencia: {diferencia:+.2f} MB")
        
        print("\n📋 Próximos pasos:")
        print("1. Sube el archivo a Google Drive: data/tablero_completo.db")
        print("2. Obtén el ID del archivo de Google Drive")
        print("3. Actualiza la variable GOOGLE_DRIVE_FILE_ID en Render")
        print("4. Reinicia el servicio en Render")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error durante la sincronización: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        db.cerrar()

if __name__ == "__main__":
    exit(main())

