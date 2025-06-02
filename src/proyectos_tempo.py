import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pandas as pd

# Cargar variables de entorno
load_dotenv()
TEMPO_TOKEN = os.getenv("TEMPO_TOKEN")

# Fechas (últimos 3 meses, podés cambiarlo)
hoy = datetime.now().date()
tres_meses_atras = hoy - timedelta(days=90)

fecha_inicio = tres_meses_atras.strftime("%Y-%m-%d")
fecha_fin = hoy.strftime("%Y-%m-%d")

headers = {
    "Authorization": f"Bearer {TEMPO_TOKEN}",
    "Accept": "application/json"
}

def get_tempo_worklogs(from_date, to_date, limit=1000):
    url = f"https://api.tempo.io/4/worklogs?from={from_date}&to={to_date}&limit={limit}"
    worklogs = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print("Error en la API Tempo:", response.text)
            break
        data = response.json()
        worklogs.extend(data.get("results", []))
        url = data.get("metadata", {}).get("next", None)
    return worklogs

def obtener_proyectos_de_worklogs(worklogs):
    proyectos = {}
    for w in worklogs:
        issue = w.get("issue", {})
        proyecto_id = issue.get("id")
        proyecto_key = issue.get("key")
        # Muchas veces el "project" está como key, no como nombre
        if proyecto_id:
            proyectos[proyecto_id] = proyecto_key
    return proyectos

if __name__ == "__main__":
    print(f"Buscando worklogs entre {fecha_inicio} y {fecha_fin}...")
    worklogs = get_tempo_worklogs(fecha_inicio, fecha_fin)
    print(f"Total de worklogs descargados: {len(worklogs)}")

    proyectos = obtener_proyectos_de_worklogs(worklogs)
    print("\n=== IDs de Proyecto y sus keys (nombres cortos) ===")
    for id_proy, key_proy in proyectos.items():
        print(f"ID: {id_proy} \t Key/NOMBRE: {key_proy}")

    # Si querés ver todas las combinaciones únicas:
    # Armá un DataFrame (opcional)
    df = pd.DataFrame([
        {"ID Proyecto": w.get("issue", {}).get("id"), 
         "Key Proyecto": w.get("issue", {}).get("key"),
         "Resumen": w.get("issue", {}).get("summary", "")
        }
        for w in worklogs if w.get("issue", {}).get("id")
    ])
    print("\nResumen tabulado (únicos):")
    print(df.drop_duplicates(subset=["ID Proyecto"]))
