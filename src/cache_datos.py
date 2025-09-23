import os
import pandas as pd
import json
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(__file__), '../data/cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_path(nombre: str, ext: str = 'csv') -> str:
    """Devuelve la ruta completa para un archivo de cache dado un nombre base y extensión."""
    return os.path.join(CACHE_DIR, f"{nombre}.{ext}")

def guardar_df_cache(df: pd.DataFrame, nombre: str):
    """Guarda un DataFrame en cache como CSV."""
    path = cache_path(nombre, 'csv')
    df.to_csv(path, index=False)

def cargar_df_cache(nombre: str) -> pd.DataFrame:
    """Carga un DataFrame desde cache (CSV). Lanza FileNotFoundError si no existe."""
    path = cache_path(nombre, 'csv')
    return pd.read_csv(path)

def guardar_json_cache(data, nombre: str):
    """Guarda un objeto como JSON en cache."""
    path = cache_path(nombre, 'json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def cargar_json_cache(nombre: str):
    """Carga un objeto JSON desde cache. Lanza FileNotFoundError si no existe."""
    path = cache_path(nombre, 'json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def cache_actualizado(nombre: str, max_horas: int = 24) -> bool:
    """Verifica si el cache está actualizado (por defecto, menos de 24h)."""
    path = cache_path(nombre, 'csv')
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime) < timedelta(hours=max_horas)

# Puedes agregar más funciones según necesidades específicas (por ejemplo, para limpiar cache viejo)
