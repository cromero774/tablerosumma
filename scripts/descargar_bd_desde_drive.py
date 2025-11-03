#!/usr/bin/env python3
"""
Script para descargar la base de datos desde Google Drive
Se ejecuta automáticamente si la BD no existe en Render
"""
import os
import urllib.request
import sys

def descargar_bd_desde_google_drive():
    """
    Descargar la base de datos desde Google Drive
    Usa el ID del archivo de Google Drive
    """
    db_path = "data/tablero_completo.db"
    
    # Crear directorio si no existe
    os.makedirs("data", exist_ok=True)
    
    # Si ya existe, no descargar
    if os.path.exists(db_path):
        print(f"✅ Base de datos ya existe en {db_path}")
        return True
    
    # ID del archivo de Google Drive (lo obtendrás cuando subas el archivo)
    # Ejemplo: https://drive.google.com/file/d/1ABC123xyz/view
    # El ID sería: 1ABC123xyz
    file_id = os.getenv("GOOGLE_DRIVE_FILE_ID")
    
    if not file_id:
        print("⚠️ GOOGLE_DRIVE_FILE_ID no configurado. La BD se creará vacía.")
        return False
    
    try:
        print("📥 Descargando base de datos desde Google Drive...")
        
        # URL directa para descargar (formato: https://drive.google.com/uc?export=download&id=FILE_ID)
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        # Descargar archivo
        urllib.request.urlretrieve(download_url, db_path)
        
        # Verificar que se descargó correctamente
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            print(f"✅ Base de datos descargada exitosamente ({size_mb:.2f} MB)")
            return True
        else:
            print("❌ Error: La descarga falló o el archivo está vacío")
            return False
            
    except Exception as e:
        print(f"❌ Error descargando desde Google Drive: {e}")
        print("💡 La BD se creará vacía y necesitarás sincronizarla manualmente")
        return False


if __name__ == "__main__":
    success = descargar_bd_desde_google_drive()
    sys.exit(0 if success else 1)

