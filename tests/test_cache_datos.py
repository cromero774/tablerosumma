import os
import pandas as pd
import json
import tempfile
from cache_datos import guardar_df_cache, cargar_df_cache, guardar_json_cache, cargar_json_cache, cache_actualizado

def test_guardar_y_cargar_df_cache():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    nombre = 'test_df_cache'
    guardar_df_cache(df, nombre)
    df2 = cargar_df_cache(nombre)
    assert df.equals(df2)

def test_guardar_y_cargar_json_cache():
    data = {'x': 1, 'y': [2, 3]}
    nombre = 'test_json_cache'
    guardar_json_cache(data, nombre)
    data2 = cargar_json_cache(nombre)
    assert data == data2

def test_cache_actualizado():
    df = pd.DataFrame({'a': [1]})
    nombre = 'test_cache_time'
    guardar_df_cache(df, nombre)
    assert cache_actualizado(nombre, max_horas=1)
    # Simular archivo viejo cambiando mtime
    path = os.path.join(os.path.dirname(__file__), '../data/cache', f'{nombre}.csv')
    os.utime(path, (0, 0))
    assert not cache_actualizado(nombre, max_horas=1)
